# overlay.py

import os
import tempfile
import subprocess
from google import genai
import textwrap
import shutil

THUMBNAIL_DIR = "thumbnails"

# ---------------------------
# ⚡ Set ImageMagick executable path here
# Example: r"C:\Program Files\ImageMagick-7.1.1-Q16\magick.exe"
IMAGEMAGICK_PATH = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"


# ---------------------------
# Step 1: Generate Hook Text
# ---------------------------
def generate_hook_text(topic: str, api_key: str) -> str:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            topic,
            "Create an engaging hook text for a thumbnail and video. "
            "You can use emojis."
            "Response one line only. Max 6-8 words."
        ]
    )
    return response.text.strip()


# ---------------------------
# Step 2: Overlay Text on Image (ImageMagick)
# ---------------------------
def overlay_text_on_image(image_path: str, text: str, output_path: str):
    if not os.path.exists(image_path):
        print(f"❌ Error: Image not found: {image_path}")
        return

    # Wrap text (2 lines max)
    lines = textwrap.wrap(text, width=20)
    text_wrapped = "\n".join(lines)

    # ImageMagick draw command
    cmd = [
        IMAGEMAGICK_PATH, image_path,
        "-gravity", "center",
        "-fill", "Black",
        "-stroke", "black",
        "-strokewidth", "5",
        "-undercolor", "rgba(255,255,255,0.8)",
        "-font", "Arial-Bold",
        "-pointsize", "100",
        "-annotate", "+0+0", text_wrapped,
        output_path
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"✅ Thumbnail with text saved: {output_path}")
    except FileNotFoundError:
        print("❌ ImageMagick not found. Check IMAGEMAGICK_PATH.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to overlay text on image: {e.stderr.decode()}")

# ---------------------------
# Step 3: Overlay Text on Video (ImageMagick + FFmpeg)
# ---------------------------
def overlay_text_on_video(video_path: str, text: str, output_path: str, duration_sec: int = None):
    """
    Overlay text directly on the video using FFmpeg's drawtext.
    duration_sec: if specified, text appears only for first N seconds; else full video.
    """
    if not os.path.exists(video_path):
        print(f"❌ Error: Video not found: {video_path}")
        return

    # Wrap text for max 20 chars per line
    import textwrap
    lines = textwrap.wrap(text, width=20)
    text_wrapped = "\\n".join(lines)  # FFmpeg needs \n escaped

    # Prepare drawtext filter
    drawtext_filter = (
        f"drawtext=fontfile=C\\:/Windows/Fonts/arialbd.ttf:text='{text_wrapped}':"
        "fontcolor=lightblue:fontsize=90:borderw=4:bordercolor=black:"
        "x=(w-text_w)/2:y=(h-text_h)/2"
    )
    if duration_sec is not None:
        drawtext_filter += f":enable='lte(t,{duration_sec})'"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", drawtext_filter,
        "-c:a", "copy",
        output_path
    ]

    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"✅ Video with overlay text saved: {output_path}")

def append_thumbnail_to_video_with_audio(video_path: str, thumbnail_path: str, output_path: str, last_frame_sec: int = 1):
    """
    Append the thumbnail image as a 1-second video at the end of the original video,
    while keeping the original audio unaffected.
    """
    import os
    import tempfile
    import subprocess

    if not os.path.exists(video_path):
        print(f"❌ Error: Video not found: {video_path}")
        return
    if not os.path.exists(thumbnail_path):
        print(f"❌ Error: Thumbnail not found: {thumbnail_path}")
        return

    # Temp file for thumbnail video with silent audio
    temp_thumb_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name

    # 1️⃣ Convert thumbnail image to 1-second video with silent audio
    cmd_thumb = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", thumbnail_path,
        "-f", "lavfi",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", str(last_frame_sec),
        "-vf", "scale=1080:1920",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        temp_thumb_video
    ]
    subprocess.run(cmd_thumb, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 2️⃣ Concatenate original video + thumbnail video
    # Create a temp file listing videos for ffmpeg
    concat_list = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt")
    concat_list.write(f"file '{os.path.abspath(video_path)}'\n")
    concat_list.write(f"file '{os.path.abspath(temp_thumb_video)}'\n")
    concat_list.close()

    # Use ffmpeg concat demuxer
    cmd_concat = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list.name,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        output_path
    ]
    subprocess.run(cmd_concat, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Cleanup
    os.remove(temp_thumb_video)
    os.remove(concat_list.name)

    print(f"✅ Final video saved with thumbnail appended: {output_path}")
# ---------------------------
# Main Function
# ---------------------------
if __name__ == "__main__":
    API_KEY = "AIzaSyCjS_eao0IarL5JOyT_aof_3eHnxNCcOMY"  # 🔑 Replace with your Gemini API key
    TOPIC = "The Future of Renewable Energy"

    THUMBNAIL_PATH = f"{THUMBNAIL_DIR}/thumbnail.jpg"
    OUTPUT_THUMBNAIL_PATH = f"{THUMBNAIL_DIR}/thumbnail_with_text.jpg"
    VIDEO_PATH = "final_tiktok_video.mp4"
    OUTPUT_VIDEO_PATH = "final_video_with_text.mp4"

    # 1️⃣ Generate hook text
    hook_text = generate_hook_text(TOPIC, API_KEY)
    print(f"🧠 Generated Hook Text: {hook_text}")

    # 2️⃣ Overlay on thumbnail (ImageMagick)
    overlay_text_on_image(THUMBNAIL_PATH, hook_text, OUTPUT_THUMBNAIL_PATH)

    append_thumbnail_to_video_with_audio(VIDEO_PATH, OUTPUT_THUMBNAIL_PATH, OUTPUT_VIDEO_PATH, last_frame_sec=1)
    
