import os
import re
import shutil
import random
import requests
import numpy as np

import pysrt
import ffmpeg

from faster_whisper import WhisperModel
from moviepy.editor import (
    VideoFileClip,
    TextClip,
    CompositeVideoClip,
    AudioFileClip,
    CompositeAudioClip,
    concatenate_audioclips,
    ImageClip
)

# ✅ Configure ImageMagick for MoviePy
from moviepy.config import change_settings

IMAGEMAGICK_PATH = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"

if os.path.exists(IMAGEMAGICK_PATH):
    change_settings({"IMAGEMAGICK_BINARY": IMAGEMAGICK_PATH})
else:
    print("⚠️ ImageMagick not found.")


# ===============================
# AUTO STICKER SYSTEM (ADDED)
# ===============================

TEMP_ASSETS = "temp_assets"
os.makedirs(TEMP_ASSETS, exist_ok=True)

WORD_TO_EMOJI = {
    "egg": "1f95a",
    "banana": "1f34c",
    "fire": "1f525",
    "money": "1f4b0",
    "love": "2764",
    "laugh": "1f602",
    "happy": "1f600",
    "sad": "1f622",
}


def download_emoji_png(code, name):

    url = f"https://twemoji.maxcdn.com/v/latest/72x72/{code}.png"
    path = f"{TEMP_ASSETS}/{name}.png"

    if not os.path.exists(path):
        try:
            r = requests.get(url, timeout=10)

            if r.status_code == 200:
                with open(path, "wb") as f:
                    f.write(r.content)
        except:
            return None

    return path


def get_sticker_for_word(word):

    word = word.lower().strip()

    if word in WORD_TO_EMOJI:
        return download_emoji_png(WORD_TO_EMOJI[word], word)

    return None


def animated_sticker(path, start, duration, video_w, video_h):

    clip = ImageClip(path, transparent=True)

    base_size = int(video_h * 0.22)

    clip = clip.resize(height=base_size)

    x = random.randint(int(video_w * 0.2), int(video_w * 0.6))
    y = random.randint(int(video_h * 0.1), int(video_h * 0.3))

    def zoom(t):
        return 1 + 0.25 * np.sin(8 * t)

    def jitter(t):
        return (
            x + random.randint(-6, 6),
            y + random.randint(-6, 6)
        )

    clip = (
        clip
        .set_start(start)
        .set_duration(duration)
        .resize(lambda t: zoom(t))
        .set_position(lambda t: jitter(t))
    )

    return clip


# ===============================
# YOUR ORIGINAL FUNCTIONS
# ===============================

def split_text_into_chunks(text, max_words=3):

    words = text.split()

    return [
        " ".join(words[i:i + max_words])
        for i in range(0, len(words), max_words)
    ]


def generate_subtitled_video(video_path,
                             output_path="final_output.mp4",
                             platform="tiktok"):

    base_name = os.path.splitext(os.path.basename(video_path))[0]

    audio_path = f"{base_name}_audio.mp3"
    srt_path = f"{base_name}_subtitles.srt"

    # 1️⃣ Extract audio
    print("🎧 Extracting audio fast with FFmpeg...")

    (
        ffmpeg
        .input(video_path)
        .output(audio_path, ac=1, ar=16000, vn=None, loglevel="quiet")
        .overwrite_output()
        .run()
    )

    # 2️⃣ Load Whisper
    print("⚡ Loading faster-whisper model...")

    model = WhisperModel("base", device="cpu", compute_type="int8")

    print("🧠 Transcribing audio...")

    segments, _ = model.transcribe(
        audio_path,
        beam_size=1,
        language="en",
        task="transcribe"
    )

    # 3️⃣ Generate SRT
    print("📝 Generating subtitles...")

    subs = pysrt.SubRipFile()
    index = 1

    for seg in segments:

        start_s = seg.start
        end_s = seg.end

        text = seg.text.strip()

        chunks = split_text_into_chunks(text, max_words=3)

        total_time = end_s - start_s
        per_chunk_time = total_time / len(chunks)

        for i, chunk in enumerate(chunks):

            chunk_start = start_s + (i * per_chunk_time)
            chunk_end = start_s + ((i + 1) * per_chunk_time)

            subs.append(
                pysrt.SubRipItem(
                    index=index,
                    start=pysrt.SubRipTime(seconds=chunk_start),
                    end=pysrt.SubRipTime(seconds=chunk_end),
                    text=chunk
                )
            )

            index += 1

    subs.save(srt_path, encoding="utf-8")

    # 4️⃣ Aspect ratio fix
    print("🎬 Adjusting aspect ratio...")

    video_clip = VideoFileClip(video_path)

    width, height = video_clip.size

    if platform.lower() in ["tiktok", "shorts", "youtube"]:
        target_ratio = 9 / 16
    else:
        target_ratio = width / height

    current_ratio = width / height

    if abs(current_ratio - target_ratio) > 0.01:

        if target_ratio > current_ratio:

            new_height = int(width / target_ratio)
            y1 = (height - new_height) // 2

            video_clip = video_clip.crop(y1=y1, y2=y1 + new_height)

        else:

            new_width = int(height * target_ratio)
            x1 = (width - new_width) // 2

            video_clip = video_clip.crop(x1=x1, x2=x1 + new_width)

    # 5️⃣ Subtitles + Stickers (EXTENDED)
    print("🔥 Rendering centered subtitles...")

    fontsize = int(video_clip.h * 0.085)
    stroke_w = int(video_clip.h * 0.006)

    subs = pysrt.open(srt_path, encoding="utf-8")

    subtitle_clips = []
    sticker_clips = []   # ADDED

    for sub in subs:

        txt = sub.text.replace("\n", " ")

        start = sub.start.ordinal / 1000.0
        end = sub.end.ordinal / 1000.0

        duration = end - start

        # Original subtitle
        txt_clip = (
            TextClip(
                txt,
                fontsize=fontsize,
                font="Arial-Bold",
                color="yellow",
                stroke_color="black",
                stroke_width=stroke_w,
                method="caption",
                size=(video_clip.w * 0.88, None),
                align="center"
            )
            .set_position(("center", "center"))
            .set_start(start)
            .set_duration(duration)
        )

        subtitle_clips.append(txt_clip)

        # ADDED: keyword → sticker
        words = re.findall(r"\w+", txt.lower())

        for w in words:

            img = get_sticker_for_word(w)

            if img and os.path.exists(img):

                sticker = animated_sticker(
                    img,
                    start,
                    min(1.5, duration),
                    video_clip.w,
                    video_clip.h
                )

                sticker_clips.append(sticker)

    final = CompositeVideoClip(
        [video_clip] + subtitle_clips + sticker_clips
    )

    # 6️⃣ Export
    print("💾 Exporting final video...")

    final.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=video_clip.fps,
        threads=4,
        preset="medium"
    )

    # 7️⃣ Cleanup
    for f in [audio_path, srt_path]:
        if os.path.exists(f):
            os.remove(f)

    if os.path.exists(TEMP_ASSETS):
        shutil.rmtree(TEMP_ASSETS)

    print(f"✅ Final video exported: {output_path}")

    return output_path


# ===============================
# YOUR ORIGINAL MUSIC FUNCTION
# ===============================

def add_background_music_to_video(video_path,
                                  sound_path,
                                  output_path="final_with_sound.mp4",
                                  volume=0.1):

    print("🎵 Adding background sound effect...")

    video = VideoFileClip(video_path)

    original_audio = video.audio
    bg_audio = AudioFileClip(sound_path)

    if bg_audio.duration < video.duration:

        n_loops = int(video.duration // bg_audio.duration) + 1

        bg_audio = concatenate_audioclips([bg_audio] * n_loops)

    bg_audio = bg_audio.subclip(0, video.duration).volumex(volume)

    if original_audio:
        final_audio = CompositeAudioClip([original_audio.volumex(1.0), bg_audio])
    else:
        final_audio = bg_audio

    temp_audio = "temp_mixed_audio.mp3"

    final_audio.write_audiofile(
        temp_audio,
        fps=44100,
        nbytes=2,
        codec="mp3",
        bitrate="192k"
    )

    video.close()
    bg_audio.close()
    final_audio.close()

    print("🎬 Merging final video and audio with FFmpeg...")

    video_input = ffmpeg.input(video_path)
    audio_input = ffmpeg.input(temp_audio)

    (
        ffmpeg
        .output(
            video_input,
            audio_input,
            output_path,
            vcodec="copy",
            acodec="aac",
            audio_bitrate="192k",
            ac=2,
            strict="experimental",
            shortest=None,
            loglevel="quiet"
        )
        .overwrite_output()
        .run()
    )

    if os.path.exists(temp_audio):
        os.remove(temp_audio)

    print(f"✅ Final video with background sound exported: {output_path}")

    return output_path


# ===============================
# YOUR ORIGINAL MAIN
# ===============================

if __name__ == "__main__":

    # final_video = generate_subtitled_video(
    #     video_path="final_contextual_short.mp4",
    #     output_path="final_tiktok_video.mp4",
    #     platform="tiktok"
    # )
    # print("🎬 Subtitled video generated:", final_video)

    final = add_background_music_to_video(
        video_path="final_tiktok_video.mp4",
        sound_path="background_music.mp3",
        output_path="final_tiktok_video_with_background_music.mp4",
        volume=0.3
    )

    print("🎵 Video with background music:", final)
