import google.genai as genai
from google.genai import types
from pydub import AudioSegment
from io import BytesIO
import os
import requests
import json
import random
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
import re
from transcribe import generate_subtitled_video
from thumbnail import download_pexels_images
from Overlay import generate_hook_text, overlay_text_on_image, overlay_text_on_video, append_thumbnail_to_video_with_audio
import shutil
from Upload import upload_to_youtube
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY_VIDEO")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
VIDEO_CLIPS_DIR = "downloaded_clips"
FINAL_VIDEO_FILE = "final_short.mp4"
AUDIO_FILE = "generated_audio.mp3"
CLIP_DURATION = 3 # Length of each individual video clip in seconds
THUMBNAIL_PATH = "thumbnails/thumbnail.jpg"
OUTPUT_THUMBNAIL_PATH = "thumbnails/thumbnail_with_text.jpg"
VIDEO_PATH = "final_tiktok_video.mp4"
OUTPUT_VIDEO_PATH = "final_video_with_text.mp4"

# Ensure the download directory exists
if not os.path.exists(VIDEO_CLIPS_DIR):
    os.makedirs(VIDEO_CLIPS_DIR)

def generate_script_and_speech(topic):
    """Generates a short video script and converts the dialogue to speech."""
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        script_prompt = f"""
        You are a professional scriptwriter for short, engaging social media videos.
        Write a 30-second video script about the topic: "{topic}".
        The script should be fast-paced, use a conversational tone, and have a clear call to action.
        Do Not specifically give any visual generation just narrators dailgoues. Do not suggest scenes and visuals.
        The scrpit should always start with a question such as "Did you know..." or "Do you know...".
        Content should contain new and research driven information.
        It should highlight new experiments, discoveries, or lesser-known facts about the topic.
        It should include dialogue for a single narrator. Format the script like this, with a clear label for the spoken parts:

        [NARRATOR]: Did you know?! the need of Renewable energy in this era is rising ?.
        [NARRATOR]: Solar, wind, and hydro are changing the game.
        [NARRATOR]: Don't forget to like and subscribe for more content like this!
        """
        script_response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=script_prompt
        )

        if not script_response or not script_response.text:
            raise Exception("Failed to generate script.")

        script_text = script_response.text
        print("Generated Script:\n", script_text)
        
        # --- CRITICAL FIX: Extract only the dialogue using regex ---
        # The pattern looks for text after a closing bracket and colon
        dialogue_pattern = r'\]: (.*?)(?:\n|$)'
        dialogue_matches = re.findall(dialogue_pattern, script_text, re.MULTILINE)
        
        if not dialogue_matches:
            print("No dialogue found in the script. Generating silence.")
            tts_text = ""
        else:
            tts_text = " ".join(match.strip() for match in dialogue_matches)
        
        if not tts_text.strip():
            print("Dialogue is empty after parsing. Generating silence.")
            tts_text = " " # A space to prevent an API error on empty text
        
        tts_prompt = f"TTS the following text with a conversational and energetic tone: {tts_text}"
        
        tts_response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=tts_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name='Kore'
                        )
                    )
                )
            )
        )
        
        if not tts_response or not tts_response.candidates:
            raise Exception("Failed to generate speech.")
            
        audio_data = tts_response.candidates[0].content.parts[0].inline_data.data
        audio_segment = AudioSegment.from_file(BytesIO(audio_data), format="raw", frame_rate=24000, channels=1, sample_width=2)
        audio_segment.export(AUDIO_FILE, format="mp3")
        
        return len(audio_segment) / 1000

    except Exception as e:
        print(f"An error occurred during script/speech generation: {e}")
        return 0

def download_pexels_videos(topic, video_duration_secs):
    """Downloads a series of videos from Pexels based on the script's topic and total duration."""
    headers = {'Authorization': PEXELS_API_KEY}
    
    # Calculate how many video clips we need
    num_clips_needed = int(video_duration_secs / CLIP_DURATION) + 1
    print(f"Audio is {video_duration_secs:.2f} seconds long. Need ~{num_clips_needed} clips.")

    videos = []
    page = 1
    while len(videos) < num_clips_needed:
        url = f"https://api.pexels.com/videos/search?query={topic}&orientation=portrait&per_page=80&page={page}"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Pexels API error: {response.status_code}, {response.text}")
            break
        
        data = response.json()
        if not data['videos']:
            print("No more videos found for this topic.")
            break
            
        videos.extend(data['videos'])
        page += 1

    downloaded_clips = []
    # Shuffle the videos to get a random assortment
    random.shuffle(videos)
    
    download_count = 0
    for video in videos:
        if download_count >= num_clips_needed:
            break
            
        # Get the URL of a high-quality MP4 file
        video_url = next((f['link'] for f in video['video_files'] if f['file_type'] == 'video/mp4' and f['quality'] == 'hd'), None)
        
        if video_url:
            file_path = os.path.join(VIDEO_CLIPS_DIR, f"clip_{video['id']}.mp4")
            print(f"Downloading video from {video_url}...")
            
            try:
                with open(file_path, 'wb') as f:
                    response = requests.get(video_url, stream=True)
                    response.raise_for_status()
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                downloaded_clips.append(file_path)
                download_count += 1
            except Exception as e:
                print(f"Failed to download video {video['id']}: {e}")
    
    return downloaded_clips

def create_final_video(video_clips_paths, audio_file_path):
    """Edits and merges video clips with the generated audio using MoviePy."""
    if not video_clips_paths:
        print("No video clips to create video.")
        return False

    try:
        # Load the audio clip to get its duration
        audio_clip = AudioFileClip(audio_file_path)
        audio_duration = audio_clip.duration
        print(f"Audio duration: {audio_duration:.2f} seconds")

        # Load and process each video clip
        video_clips = []
        current_video_time = 0

        for clip_path in video_clips_paths:
            if current_video_time >= audio_duration:
                break

            clip = VideoFileClip(clip_path)

            # Trim to desired CLIP_DURATION
            if clip.duration > CLIP_DURATION:
                start_time = random.uniform(0, clip.duration - CLIP_DURATION)
                clip = clip.subclip(start_time, start_time + CLIP_DURATION)

            # Resize to 1080x1920 (portrait)
            clip = clip.resize((1080, 1920))

            video_clips.append(clip)
            current_video_time += clip.duration

        # If total video time > audio, trim last clip
        total_video_time = sum([c.duration for c in video_clips])
        if total_video_time > audio_duration:
            excess_time = total_video_time - audio_duration
            last_clip = video_clips[-1]
            video_clips[-1] = last_clip.subclip(0, last_clip.duration - excess_time)
            print(f"Trimmed last clip by {excess_time:.2f} seconds to match audio")

        # Concatenate clips using 'compose' to avoid FPS/resolution issues
        final_video_clip = concatenate_videoclips(video_clips, method="compose")

        # Set audio and force video duration = audio duration
        final_video_clip = final_video_clip.set_audio(audio_clip)
        final_video_clip = final_video_clip.set_duration(audio_duration)

        # Write the final video
        print(f"Writing final video to {FINAL_VIDEO_FILE}...")
        final_video_clip.write_videofile(FINAL_VIDEO_FILE, fps=24, codec="libx264", audio_codec="aac")

        # Close clips to free memory
        for clip in video_clips:
            clip.close()
        audio_clip.close()

        print("✅ Video creation successful!")
        return True

    except Exception as e:
        print(f"An error occurred during video editing: {e}")
        return False

# --- Main Execution ---
if __name__ == "__main__":
    topic = "wars"
    
    # Generate the script and speech, and get the audio duration
    audio_duration = generate_script_and_speech(topic)
    
    if audio_duration > 0:
        # Download video clips based on the audio duration
        clips_to_download = download_pexels_videos(topic, audio_duration)
        
        if clips_to_download:
            # Create the final video
            create_final_video(clips_to_download, AUDIO_FILE)
            print("Video creation pipeline complete!")
        else:
            print("No clips downloaded. Video creation aborted.")
    else:
        print("Audio generation failed. Video creation aborted.")

    if os.path.exists(FINAL_VIDEO_FILE):
        final = generate_subtitled_video(
            video_path=FINAL_VIDEO_FILE,
            output_path="final_tiktok_video.mp4",
            platform="tiktok"  # or "youtube"
        )
        print(f"🎉 Done! Output video saved at: {final}")

    if os.path.exists("final_tiktok_video.mp4"):
        thumbnails = download_pexels_images(topic, num_images=1)
    
    hook_text = generate_hook_text(topic, GEMINI_API_KEY)
    print(f"Generated Hook Text: {hook_text}")

    overlay_text_on_image(THUMBNAIL_PATH, hook_text, OUTPUT_THUMBNAIL_PATH)

    # Overlay on video
    append_thumbnail_to_video_with_audio(VIDEO_PATH, OUTPUT_THUMBNAIL_PATH, OUTPUT_VIDEO_PATH, last_frame_sec=1)
    
    if os.path.exists("final_video_with_text.mp4"):
        video_id = upload_to_youtube("final_video_with_text.mp4", OUTPUT_THUMBNAIL_PATH, topic)
        print(f"Uploaded Video ID: {video_id}")

    if os.path.exists(VIDEO_CLIPS_DIR):
        shutil.rmtree(VIDEO_CLIPS_DIR)
        print("🧹 Temporary video clips directory removed.")


