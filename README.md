# Healthy Stop Video Automation

An automated video generation pipeline for the "Healthy Stop" YouTube channel, focusing on fitness, nutrition, and healthy lifestyle content. This tool creates engaging short-form videos (TikTok, YouTube Shorts, Instagram Reels) by generating scripts, speech, visuals, and subtitles programmatically.

## Features

- **AI-Powered Script Generation**: Uses Google Gemini to create educational, motivating scripts about fitness and health topics.
- **Text-to-Speech**: Converts scripts to natural-sounding audio using Gemini's TTS with a professional fitness coach voice.
- **Visual Content Creation**: Downloads relevant stock video clips from Pexels API based on script content.
- **Video Editing**: Automatically edits clips, adds subtitles, background music, and thumbnails using MoviePy.
- **YouTube Upload**: Seamlessly uploads completed videos to YouTube with custom thumbnails.
- **Topic Management**: Intelligent topic selection to avoid repetition and maintain content variety.
- **Subtitling**: Generates synchronized subtitles with animated stickers for better engagement.

## Prerequisites

- Python 3.8 or higher
- FFmpeg (for video processing)
- ImageMagick (for text overlays)
- YouTube Data API credentials (client_secret.json)
- API Keys for:
  - Google Gemini API
  - Pexels API

## Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/yourusername/healthy-stop-automation.git
   cd healthy-stop-automation
   ```

2. **Create a virtual environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Install system dependencies**:
   - Download and install FFmpeg from https://ffmpeg.org/
   - Download and install ImageMagick from https://imagemagick.org/

5. **Set up API credentials**:
   - Obtain API keys for Google Gemini and Pexels
   - Create a `.env` file in the project root:
     ```
     GEMINI_API_KEY=your_gemini_api_key_here
     GEMINI_API_KEY_VIDEO=your_video_gemini_key_here
     PEXELS_API_KEY=your_pexels_api_key_here
     ```
   - Place your `client_secret.json` file in the project root for YouTube API access

## Setup

1. **Configure ImageMagick path** (in `transcribe.py`):
   Update the `IMAGEMAGICK_PATH` variable with your ImageMagick installation path.

2. **YouTube Authentication**:
   Run the upload script once to authenticate with YouTube API. This will generate `token.pickle` for future use.

3. **Background Music**:
   Place your background music file as `background_music.mp3` in the project root.

## Usage

### Basic Video Generation

Run the main pipeline:

```bash
python test.py
```

This will:

1. Select a health/fitness topic using AI
2. Generate a script and audio narration
3. Download contextual video clips
4. Create a segmented video with changing visuals
5. Add subtitles and background music
6. Upload to YouTube

### Individual Components

- **Script and Speech Generation**:

  ```python
  from Voice import generate_script_and_speech
  script, tts_text, duration = generate_script_and_speech("Protein Powder")
  ```

- **Video Creation**:

  ```python
  from Video import generate_script_and_speech, download_pexels_videos, create_final_video
  # Full pipeline in Video.py
  ```

- **Transcription and Subtitling**:

  ```python
  from transcribe import generate_subtitled_video
  subtitled_video = generate_subtitled_video("input_video.mp4")
  ```

- **Topic Selection**:
  ```python
  from test import select_topic_using_gemini
  topic = select_topic_using_gemini()
  ```

## Project Structure

```
Main_YT_Automation/
├── .env                    # Environment variables (API keys)
├── .gitignore             # Git ignore rules
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── client_secret.json     # YouTube API credentials
├── token.pickle           # YouTube authentication token
├── background_music.mp3   # Background audio file
├── Voice.py               # Script and TTS generation
├── Video.py               # Video creation pipeline
├── VideoGeneration.py     # Image generation (experimental)
├── test.py                # Main automation pipeline
├── transcribe.py          # Audio transcription and subtitling
├── Overlay.py             # Text overlay utilities
├── Upload.py              # YouTube upload functionality
├── thumbnail.py           # Thumbnail generation
├── InstaUploadSetup.py    # Instagram upload setup
├── __init__.py
├── downloaded_clips/      # Temporary video clips
├── logs/                  # Application logs
├── temp_assets/           # Temporary assets
├── thumbnails/            # Generated thumbnails
└── used_topics.txt        # Track used topics
```

## Configuration

### Environment Variables

- `GEMINI_API_KEY`: Primary Gemini API key for script generation and TTS
- `GEMINI_API_KEY_VIDEO`: Secondary Gemini API key for video-related tasks
- `PEXELS_API_KEY`: Pexels API key for stock video downloads

### Key Parameters (in test.py)

- `SEGMENT_TARGET_SEC`: Duration for each video segment (default: 3 seconds)
- `RESOLUTION`: Video resolution (default: 1080x1920 for portrait)
- `FPS`: Frames per second (default: 24)

## Troubleshooting

### Common Issues

1. **API Quota Exceeded**:
   - Gemini API has rate limits. Wait or upgrade your plan.
   - Check usage at https://ai.dev/rate-limit

2. **Video Processing Errors**:
   - Ensure FFmpeg is installed and in PATH
   - Check video file formats and durations

3. **YouTube Upload Failures**:
   - Verify `client_secret.json` is valid
   - Re-authenticate if `token.pickle` is corrupted

4. **ImageMagick Errors**:
   - Update the path in `transcribe.py`
   - Ensure ImageMagick is installed correctly

### Logs

Check `logs/` directory for detailed error logs. Enable debug logging by modifying the logging configuration in the scripts.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit a pull request

## License

This project is proprietary software. All rights reserved.

## Disclaimer

This tool is for educational and personal use. Ensure compliance with API terms of service and platform policies when uploading content. The authors are not responsible for misuse or violations of platform guidelines.

## Support

For issues or questions, please open an issue on the GitHub repository or contact the maintainers.
