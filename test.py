import google.genai as genai
from google.genai import types
from pydub import AudioSegment
from io import BytesIO
import os
import requests
import json
import random
import re
import math
import shutil
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    concatenate_videoclips,
    ColorClip,
    ImageClip,
    vfx
)
from moviepy.video.fx.all import loop as loop_clip
from transcribe import generate_subtitled_video, add_background_music_to_video
from thumbnail import download_pexels_images
from Overlay import generate_hook_text, overlay_text_on_image, append_thumbnail_to_video_with_audio
from Upload import upload_to_youtube
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")   # 🔑 Your Gemini API key
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")   # 🔑 Your Pexels API key
VIDEO_CLIPS_DIR = "downloaded_clips"
FINAL_VIDEO_FILE = "final_contextual_short.mp4"
AUDIO_FILE = "generated_audio.mp3"
THUMBNAIL_PATH = "thumbnails/thumbnail.jpg"
OUTPUT_THUMBNAIL_PATH = "thumbnails/thumbnail_with_text.jpg"
VIDEO_PATH = "final_tiktok_video.mp4"
OUTPUT_VIDEO_PATH = "final_video_with_text.mp4"
SEGMENT_TARGET_SEC = 3  # desired per-frame change (approx)
RESOLUTION = (1080, 1920)  # portrait
FPS = 24
BACKGROUND_MUSIC = "background_music.mp3"

os.makedirs(VIDEO_CLIPS_DIR, exist_ok=True)


# ============================
# 1) SCRIPT & TTS generation
# ============================
def generate_script_and_speech(topic):
    """
    Returns:
      - script_text (the full Gemini script)
      - tts_text (the combined narrator text used for TTS)
      - audio_duration_sec (float)
    """
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        script_prompt = f"""
                You are a professional scriptwriter for a fitness and healthy lifestyle YouTube & short-form content channel called "Healthy Stop".

                Write a **30-second fast-paced, informational, science-backed** social media script about:
                "{topic}"

                Audience:
                - Teenagers starting fitness
                - Adults trying to lose fat, gain strength, and build healthy habits
                - Busy people looking for simple, realistic health advice

                The tone should be:
                - Beginner-friendly (basic knowledge level)
                - Educational but motivating
                - Simple global English (no complex words)
                - Practical and realistic
                - Confident fitness-coach style

                Content rules:
                - Avoid medical or scientific jargon
                - Focus on workouts, nutrition, fat loss, muscle building, or healthy habits
                - Keep it short, punchy, and clear
                - No fluff, only useful information
                - Suitable for Instagram Reels, Shorts, and YouTube Shorts

                Format exactly like this:
                [NARRATOR]: line 1
                [NARRATOR]: line 2
                """


        script_response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=script_prompt
        )

        if not script_response or not getattr(script_response, "text", None):
            raise Exception("Failed to generate script.")

        script_text = script_response.text.strip()
        print("\n📝 Generated Script:\n", script_text)

        # Extract narrator lines and create the tts_text (single concatenated text)
        dialogue_pattern = r'\[NARRATOR\]: (.*?)(?:\n|$)'
        dialogue_matches = re.findall(dialogue_pattern, script_text, re.MULTILINE)
        tts_lines = [m.strip() for m in dialogue_matches if m.strip()]
        tts_text = " ".join(tts_lines)

        if not tts_text:
            raise Exception("No valid narrator lines found for TTS.")

        # TTS request (Gemini preview-tts)
        tts_prompt = f"""
            Convert the following text into a **male fitness influencer-style voice**.

            Voice traits:
            - energetic and engaging
            - confident and motivating
            - fast-paced but clear
            - globally understandable English
            - professional fitness coach tone
            - friendly, encouraging, and authoritative
            - suitable for short-form fitness content

            Avoid regional accents. Make it sound like a top-tier male health coach motivating a global audience.

            Text: {tts_text}
            """
        tts_response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=tts_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Orus")
                    )
                )
            )
        )

        if not tts_response or not getattr(tts_response, "candidates", None):
            raise Exception("Failed to generate speech (no candidates).")

        # Extract raw audio bytes (same approach as your original)
        audio_data = tts_response.candidates[0].content.parts[0].inline_data.data
        narration_audio = AudioSegment.from_file(BytesIO(audio_data), format="raw",
                                               frame_rate=24000, channels=1, sample_width=2)
        audio_duration_sec = len(narration_audio) / 1000.0
        print(f"🎧 Narration generated ({audio_duration_sec:.2f}s)")

        mixed = narration_audio

        # --- 5️⃣ Export final combined audio ---
        mixed.export(AUDIO_FILE, format="mp3", bitrate="192k")
        print(f"✅ Final TTS with background music saved: {AUDIO_FILE}")

        return script_text, tts_text, audio_duration_sec

    except Exception as e:
        print("❌ Error in generate_script_and_speech:", e)
        return "", "", 0.0


# ============================
# 2) Split TTS text into segments mapped to time windows
# ============================
def split_text_into_time_segments(tts_text, audio_duration, segment_target_sec=SEGMENT_TARGET_SEC):
    """
    Splits tts_text into N segments where N = ceil(audio_duration / segment_target_sec).
    Returns list of tuples: (segment_text, segment_duration_sec)
    Each segment gets a portion of the text proportionally by characters.
    Last segment_duration may be shorter to exactly match audio.
    """
    if not tts_text:
        return []

    n_segments = int(math.ceil(audio_duration / segment_target_sec))
    if n_segments <= 0:
        n_segments = 1

    total_chars = len(tts_text)
    segments = []
    for i in range(n_segments):
        start_char = int((i * total_chars) / n_segments)
        end_char = int(((i + 1) * total_chars) / n_segments) if i < n_segments - 1 else total_chars
        seg_text = tts_text[start_char:end_char].strip()
        if i < n_segments - 1:
            seg_dur = segment_target_sec
        else:
            seg_dur = max(0.1, audio_duration - segment_target_sec * (n_segments - 1))
        segments.append((seg_text if seg_text else tts_text, seg_dur))
    return segments


# ============================
# 3) Gemini visual keywords generation (topic-boosted)
# ============================
def generate_visual_keywords_for_segment(segment_text, topic, max_keywords=3):
    """
    Ask Gemini to provide 1-3 short visual keywords for a text segment.
    We bias the prompt to include the main topic so results remain relevant.
    Fallback returns top words from the segment.
    """
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""
        You are selecting concise visual search keywords for stock videos.
        The main topic is: "{topic}".
        For this narration segment:
        "{segment_text}"
        Return a JSON array of 1 to {max_keywords} short keywords (each 1-3 words),
        prioritized to be visually useful and relevant to the main topic.
        Example: ["solar panels", "sunset", "wind turbine"]
        Return only the JSON array.
        """
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = response.text.strip()
        # Try to parse JSON array
        try:
            keywords = json.loads(text)
            if isinstance(keywords, list) and keywords:
                return [k.strip() for k in keywords][:max_keywords]
        except Exception:
            # fallback: take top nouns/words heuristically
            pass

    except Exception as e:
        print("⚠️ Gemini keyword generation failed:", e)

    # Fallback heuristic: take up to 2-3 important words from the segment + topic
    words = re.findall(r'\w+', segment_text)
    candidates = []
    for w in words:
        if len(w) > 3 and w.lower() not in {"about", "which", "there", "they", "we", "you", "this"}:
            candidates.append(w.lower())
        if len(candidates) >= (max_keywords - 1):
            break
    # ensure topic is first preference
    keywords_fallback = [topic] + candidates[: max_keywords - 1]
    return keywords_fallback


# ============================
# 4) Download best-matching Pexels clip for given keywords
# ============================
def download_pexels_clip_for_segment(keywords, topic, prefer_topic=True):
    headers = {"Authorization": PEXELS_API_KEY}

    queries = []
    if prefer_topic:
        queries.append(f"{topic} {' '.join(keywords)}".strip())
    queries.append(" ".join(keywords).strip())
    queries.append(topic)

    for q in queries:
        if not q:
            continue

        url = f"https://api.pexels.com/videos/search?query={requests.utils.quote(q)}&orientation=portrait&per_page=6"

        try:
            resp = requests.get(url, headers=headers, timeout=20)
        except Exception as e:
            print("⚠️ Pexels request failed:", e)
            continue

        if resp.status_code != 200:
            continue

        data = resp.json()
        videos = data.get("videos") or []
        if not videos:
            continue

        random.shuffle(videos)
        for video in videos:
            file_url = next((f["link"] for f in video.get("video_files", []) if f.get("file_type") == "video/mp4"), None)
            if not file_url:
                continue

            safe_name = "_".join([re.sub(r'\W+', '', k) for k in (keywords[:2] or [topic])])
            file_path = os.path.join(VIDEO_CLIPS_DIR, f"{safe_name}_{video['id']}.mp4")

            try:
                with requests.get(file_url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(file_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                return file_path
            except Exception as e:
                print("⚠️ Failed to download clip:", e)
                continue

    return None

# ============================
# 5) Build final video with per-segment clips (changes every ~3s)
# ============================
def create_segmented_contextual_video(topic, tts_text, audio_path, audio_duration):
    segments = split_text_into_time_segments(
        tts_text, audio_duration, SEGMENT_TARGET_SEC
    )
    if not segments:
        print("❌ No segments could be created.")
        return False

    audio_clip = AudioFileClip(audio_path)
    final_clips = []

    for idx, (seg_text, seg_dur) in enumerate(segments):
        print(f"\n🔸 Segment {idx + 1}/{len(segments)} — target {seg_dur:.2f}s")

        keywords = generate_visual_keywords_for_segment(seg_text, topic)
        clip_path = download_pexels_clip_for_segment(keywords, topic)

        try:
            if not clip_path:
                raise Exception("No clip found")

            clip = VideoFileClip(clip_path)

            # FIX 1: normalize FPS
            clip = clip.set_fps(FPS)

            # Duration handling
            if clip.duration > seg_dur + 0.05:
                start = random.uniform(0, max(0, clip.duration - seg_dur))
                clip = clip.subclip(start, start + seg_dur)
            elif clip.duration < seg_dur - 0.05:
                clip = loop_clip(clip, duration=seg_dur)
            else:
                clip = clip.subclip(0, min(clip.duration, seg_dur))

            # FIX 2: force resolution
            clip = clip.resize(RESOLUTION)

            # FIX 3: force exact duration
            clip = clip.set_duration(seg_dur)

            final_clips.append(clip)

        except Exception as e:
            print("⚠️ Clip error, using placeholder:", e)
            placeholder = (
                ColorClip(size=RESOLUTION, color=(20, 20, 20), duration=seg_dur)
                .set_fps(FPS)
            )
            final_clips.append(placeholder)

    if not final_clips:
        print("❌ No final clips created.")
        return False

    print("\n⏱ Concatenating clips...")
    final_video = concatenate_videoclips(final_clips, method="compose")

    final_video = (
        final_video
        .set_audio(audio_clip)
        .set_duration(audio_duration)
        .set_fps(FPS)
    )

    print(f"\n💾 Writing final video to: {FINAL_VIDEO_FILE}")

    # FIX 4: FFmpeg stability (Windows-safe)
    final_video.write_videofile(
        FINAL_VIDEO_FILE,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        bitrate="4000k",
        threads=2,
        temp_audiofile="temp-audio.m4a",
        remove_temp=True
    )

    audio_clip.close()
    for c in final_clips:
        try:
            c.close()
        except Exception:
            pass

    print("✅ Contextual segmented video created.")
    return True



def select_topic_using_gemini():
    """
    Use Gemini to select a trending or interesting topic for the video.
    Ensures topics are not repeated too frequently (max 2–3 repeats allowed).
    Returns:
        - topic (str): The selected topic name.
    """
    example_topic_list = [
        "Protein Powder", "Intermittent Fasting", "Muscle Building", "Fat Loss",
        "Healthy Snacks", "Workout Routines", "Gut Health", "Hydration Tips",
        "Sleep and Fitness", "Meal Prep", "Cardio Workouts", "Strength Training",
        "Nutrition Myths", "Superfoods", "Weight Gain", "Healthy Habits",
        "Diet Plans", "Exercise Motivation", "Recovery Tips", "Mental Health Fitness"
    ]

    used_topics_file = "used_topics.txt"

    # Load previously used topics
    if os.path.exists(used_topics_file):
        with open(used_topics_file, "r", encoding="utf-8") as f:
            used_topics = [line.strip() for line in f if line.strip()]
    else:
        used_topics = []

    try:
        # ✅ Create Gemini client (as in your reference function)
        client = genai.Client(api_key=GEMINI_API_KEY)

        prompt = f"""
        You are an expert social media content curator for a fitness and healthy lifestyle YouTube & short-form content channel called "Healthy Stop".

        Suggest 1 unique, fascinating, and engaging video topic suitable for short educational and motivating videos.

        Audience:
        - Teenagers starting fitness
        - Adults trying to lose fat, gain strength, and build healthy habits
        - Busy people looking for simple, realistic health advice

        The topic should be:
        - Beginner-friendly (basic knowledge level)
        - Educational but motivating
        - Simple global English (no complex words)
        - Practical and realistic
        - Confident fitness-coach style

        Content focus:
        - Workouts, nutrition, fat loss, muscle building, or healthy habits
        - Avoid medical or scientific jargon
        - Keep it short, punchy, and clear
        - No fluff, only useful information
        - Suitable for Instagram Reels, Shorts, and YouTube Shorts

        Select topics that are likely to trend or capture wide interest, similar in tone and spirit to these examples:
        {', '.join(example_topic_list)}.

        Avoid exact repetition of topics already used (listed below),
        but you may repeat 1–2 of them occasionally if it feels natural.

        Already used topics: {', '.join(used_topics[-15:])}

        ⚠️ Return only the topic name, in one or two words — no punctuation, no explanation, no numbering.
        """

        # ✅ Use same correct model call pattern as your working function
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )

        if not response or not getattr(response, "text", None):
            raise Exception("No topic returned by Gemini.")

        topic = response.text.strip().replace('"', '').replace('.', '').title()

        # ✅ Handle too many repeats
        if used_topics.count(topic) >= 3:
            available = [t for t in example_topic_list if used_topics.count(t) < 3]
            topic = random.choice(available if available else example_topic_list)

        # ✅ Save the new topic
        with open(used_topics_file, "a", encoding="utf-8") as f:
            f.write(topic + "\n")

        print(f"✅ Selected topic: {topic}")
        return topic

    except Exception as e:
        print(f"⚠️ Error using Gemini: {e}")
        topic = random.choice(example_topic_list)
        print(f"Using fallback topic: {topic}")
        return topic

# ============================
# 6) MAIN pipeline
# ============================
if __name__ == "__main__":
    topic = select_topic_using_gemini()
    # 1) script + TTS
    script_text, tts_text, audio_duration = generate_script_and_speech(topic)

    if audio_duration <= 0 or not tts_text:
        print("❌ Audio generation failed. Aborting pipeline.")
    else:
        # 2) build segmented contextual video (changes ~every SEGMENT_TARGET_SEC)
        ok = create_segmented_contextual_video(topic, tts_text, AUDIO_FILE, audio_duration)
        if ok:
            print("🎬 Video creation complete.")

            # 3) add subtitles using existing transcribe/generation (keeps your original behavior)
            if os.path.exists(FINAL_VIDEO_FILE):
                final_video_with_subs = generate_subtitled_video(
                    video_path=FINAL_VIDEO_FILE,
                    output_path="final_tiktok_video.mp4",
                    platform="tiktok"
                )
                print("🔤 Subtitled video:", final_video_with_subs)

            if os.path.exists("final_tiktok_video.mp4"):
                final = add_background_music_to_video(
                    video_path="final_tiktok_video.mp4",
                    sound_path="background_music.mp3",
                    output_path="final_tiktok_video_with_background_music.mp4",
                    volume=0.6
                )
                print("🎵 Video with background music:", final) 

            if os.path.exists("final_tiktok_video_with_background_music.mp4"):
                video_id = upload_to_youtube(
                    video_path="final_tiktok_video_with_background_music.mp4",
                    thumbnail_path=OUTPUT_THUMBNAIL_PATH if os.path.exists(OUTPUT_THUMBNAIL_PATH) else THUMBNAIL_PATH,
                    topic=script_text
                )
                print("📤 Uploaded video ID:", video_id)                       

        else:
            print("⚠️ Contextual video generation failed or returned nothing. Check logs.")

    # 7) cleanup temporary downloads
    if os.path.exists(VIDEO_CLIPS_DIR):
        try:
            shutil.rmtree(VIDEO_CLIPS_DIR)
            print("🧹 Temporary clip folder cleaned.")
        except Exception as e:
            print("⚠️ Cleanup failed:", e)
