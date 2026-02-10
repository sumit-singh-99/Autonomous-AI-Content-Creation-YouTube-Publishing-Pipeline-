import google.genai as genai
from google.genai import types
from pydub import AudioSegment
from io import BytesIO
import os
from dotenv import load_dotenv

load_dotenv()

# Your API Key
API_KEY = os.getenv("GEMINI_API_KEY")

def generate_script_and_speech(topic, output_file_name="generated_video_audio.mp3"):
    try:
        # Step 1: Initialize the API Client with your API Key
        client = genai.Client(api_key=API_KEY)

        # Prompt for script generation
        script_prompt = f"""
        You are a professional scriptwriter for short, engaging social media videos (like TikTok or YouTube Shorts).
        Write a 30-second video script about the topic: "{topic}".
        The script should be fast-paced, use a conversational tone, and have a clear call to action at the end.
        It should include dialogue for two speakers, "Joe" and "Jane", with a description of their emotions.
        Format the script with speaker names and emotions, like this:

        [JANE, excitedly]: Hello everyone!
        [JOE, confused]: Why are you so happy?
        """

        # Step 2: Generate the script using the text generation model
        script_response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=script_prompt
        )

        if not script_response or not script_response.text:
            print("Failed to generate script.")
            return

        script_text = script_response.text
        print("Generated Script:\n", script_text)

        # Separate the dialogue from the emotional cues for TTS
        lines = script_text.strip().split('\n')
        dialogue_only = [line.split(']: ', 1)[1] for line in lines if ']: ' in line]
        tts_text = " ".join(dialogue_only)
        
        # Use the Gemini TTS model to generate speech
        tts_prompt = f"TTS the following text with conversational and energetic tones: {tts_text}"
        
        # Step 3: Use the correct syntax for SpeechConfig
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
            print("Failed to generate speech.")
            return
            
        audio_data = tts_response.candidates[0].content.parts[0].inline_data.data

        # Step 4: Convert and save the audio as an MP3 file
        # CRITICAL FIX: The audio data is a RAW PCM stream, not a standard WAV file.
        # You must explicitly tell pydub the format, sample rate, and channels.
        audio_segment = AudioSegment.from_file(
            BytesIO(audio_data),
            format="raw",          # Specify 'raw' format
            frame_rate=24000,      # The API's sample rate is 24kHz
            channels=1,            # The API output is mono
            sample_width=2         # The API output is 16-bit (2 bytes per sample)
        )
        
        # Export the audio to an MP3 file
        audio_segment.export(output_file_name, format="mp3")

        print(f"Successfully generated audio and saved to {output_file_name}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    content_topic = "the future of renewable energy"
    generate_script_and_speech(content_topic)