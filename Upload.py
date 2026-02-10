import os
import pickle
import time
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# === Dynamic Paths ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = os.path.join(BASE_DIR, "final_tiktok_video_with_background_music.mp4")
THUMB_PATH = os.path.join(BASE_DIR, "thumbnails", "thumbnail_with_text.jpg")

CREDENTIALS_FILE = os.path.join(BASE_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.pickle")

# === API Keys ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # 🔑 Your Gemini API key
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]

# === 🔥 Hardcoded Topic (edit this per video) ===
VIDEO_TOPIC = "Greatest inventions of the 21st century"

# === Authenticate YouTube ===
def authenticate_youtube():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080, prompt="consent")
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)

# === Generate Metadata using Gemini ===
def generate_metadata_with_gemini(topic):
    genai.configure(api_key=GEMINI_API_KEY)
    prompt = f"""
    You are an expert YouTube content strategist.
    Based on the Script "{topic}", generate the following:
    1️⃣ A catchy and clickable video title (under 90 characters, add #shorts)
    2️⃣ A compelling YouTube short description along with tags, also topic relevant queries for SEO.
    3️⃣ 5–8 highly relevant YouTube tags (comma-separated)
    Include more like different variations of topic questions and queries for SEO

    Format your answer EXACTLY like this:
    TITLE: ...
    DESCRIPTION: ...
    TAGS: ...
    """

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    text = response.text.strip()

    # === Parse output ===
    title, description, tags = "", "", []
    for line in text.splitlines():
        if line.startswith("TITLE:"):
            title = line.replace("TITLE:", "").strip()
        elif line.startswith("DESCRIPTION:"):
            description = line.replace("DESCRIPTION:", "").strip()
        elif line.startswith("TAGS:"):
            tags = [t.strip() for t in line.replace("TAGS:", "").split(",")]

    return title, description, tags

def wait_until_ready(youtube, video_id, max_retries=10):
    for i in range(max_retries):
        response = youtube.videos().list(part="status", id=video_id).execute()
        status = response["items"][0]["status"]["uploadStatus"]
        if status == "processed":
            print("✅ Video processed — ready for thumbnail upload.")
            return True
        print(f"⏳ Still processing... retry {i+1}/{max_retries}")
        time.sleep(5)
    print("⚠️ Video not processed yet, continuing anyway.")
    return False

# === Upload to YouTube ===
def upload_video(youtube, video_path, thumbnail_path, title, description, tags):
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "27",  # Entertainment
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    print(f"⏫ Uploading: {os.path.basename(video_path)}")
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    video_id = response["id"]
    print(f"✅ Uploaded successfully | Video ID: {video_id}")

    # === Wait before thumbnail upload ===
    print("⏳ Waiting 10 seconds before setting thumbnail...")
    time.sleep(10)
    wait_until_ready(youtube, video_id)

    # === Upload thumbnail ===
    if os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()
            print("🖼️ Thumbnail uploaded successfully!")
        except HttpError as e:
            print(f"❌ Thumbnail upload failed: {e}")
    else:
        print("⚠️ Thumbnail file not found — skipping thumbnail upload.")

    return video_id

# === Main Flow ===
def upload_to_youtube(video_path, thumbnail_path, topic):
    """
    Uploads a video to YouTube using an AI-generated title, description, and tags.

    Args:
        video_path (str): Path to the video file.
        thumbnail_path (str): Path to the thumbnail image.
        topic (str): The main topic of the video for metadata generation.
    """
    print("🔐 Authenticating YouTube...")
    youtube = authenticate_youtube()
    print("✅ Authenticated successfully.\n")

    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        return

    if not os.path.exists(thumbnail_path):
        print(f"⚠️ Thumbnail not found: {thumbnail_path}")
        return

    print(f"🤖 Generating metadata for topic: '{topic}' using Gemini...")
    title, description, tags = generate_metadata_with_gemini(topic)

    print(f"\n📝 Title: {title}")
    print(f"📄 Description:\n{description}")
    print(f"🏷️ Tags: {tags}\n")

    video_id = upload_video(youtube, video_path, thumbnail_path, title, description, tags)
    print("✅ Upload completed successfully!")

    return video_id

if __name__ == "__main__":
    VIDEO_TOPIC = "bats"
    upload_to_youtube(VIDEO_PATH, THUMB_PATH, VIDEO_TOPIC)
    print("🎉 All done!")


