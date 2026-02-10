import os
import time
import mimetypes
import pickle
import requests
import google.generativeai as genai
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# ================= CONFIG =================
ACCESS_TOKEN = "EAALsyyhhqSoBPqZB1QVM5lnwcZCIwD6BgpDRxbspl1zn4ibV0EndRSLt2dXZBZBKjxTmXdOhB8eFndNlIW97REp61hyzZAjiEXZCT2joVAMMAnuXcIZAt4TMglDZCioCuNmWO0dAcITCGNVp9szARnTwGiNTORKATzXLzGKULSZCYX0SpZAHTeZCeKWdjn0SrFPAqJSCpSD4bZA67pSjijFFZC0LZCEVGYy3X4OGdZAYqo6u5zSW3ewZAwZDZD"  # 🔑 Instagram Graph API Access Token
IG_USER_ID = "17841406642456975"  # Example: your Instagram Business ID
GEMINI_API_KEY = "AIzaSyDjOrA3xsyOvXstVc8-iimJP5VEIEOwWFc"   # 🔑 Your Gemini API key
VIDEO_FOLDER = "ContentVideos"
CLIENT_SECRET_FILE = "client_secret.json"  # Path to your Google OAuth credentials
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DRIVE_FOLDER_NAME = "InstagramUploads"
# ==========================================


# ---------- GEMINI CAPTION GENERATION ----------
def generate_gemini_caption(topic: str):
    """Generate a caption + hashtags using Gemini API"""
    genai.configure(api_key=GEMINI_API_KEY)
    prompt = f"""
    Generate a catchy Instagram caption and 10-15 trendy hashtags for a Reel about:
    '{topic}'.
    Format the response as:
    Caption: <your caption>
    Hashtags: #tag1 #tag2 ...
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    text = response.text.strip()

    caption, hashtags = "", ""
    if "Caption:" in text:
        parts = text.split("Hashtags:")
        caption = parts[0].replace("Caption:", "").strip()
        hashtags = parts[1].strip() if len(parts) > 1 else ""
    else:
        caption = text

    full_caption = f"{caption}\n\n{hashtags}"
    print(f"\n📝 Generated Caption:\n{full_caption}\n")
    return full_caption


# ---------- GOOGLE DRIVE UPLOAD ----------
def authenticate_google_drive():
    creds = None
    if os.path.exists("token_drive.pickle"):
        with open("token_drive.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token_drive.pickle", "wb") as token:
            pickle.dump(creds, token)

    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, folder_name):
    """Get or create a folder on Google Drive"""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
    folders = results.get("files", [])

    if folders:
        return folders[0]["id"]
    else:
        file_metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
        folder = service.files().create(body=file_metadata, fields="id").execute()
        print(f"📁 Created new folder '{folder_name}' on Google Drive.")
        return folder.get("id")


def upload_to_gdrive(video_path):
    """Upload the latest video to Google Drive and return its public link"""
    print("⏫ Uploading video to Google Drive...")
    service = authenticate_google_drive()
    folder_id = get_or_create_folder(service, DRIVE_FOLDER_NAME)

    file_name = os.path.basename(video_path)
    mime_type = mimetypes.guess_type(video_path)[0] or "video/mp4"

    file_metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaFileUpload(video_path, mimetype=mime_type, resumable=True)

    uploaded_file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = uploaded_file.get("id")

    # Make file public
    service.permissions().create(fileId=file_id, body={"role": "reader", "type": "anyone"}).execute()

    # Get direct link
    file = service.files().get(fileId=file_id, fields="webContentLink").execute()
    direct_link = file.get("webContentLink")
    print(f"✅ Uploaded successfully to Google Drive!")
    print(f"🔗 Direct Download Link: {direct_link}")
    return direct_link


# ---------- INSTAGRAM UPLOAD ----------
def upload_instagram_reel(video_url, caption):
    """Upload video to Instagram Reels via Graph API with retry until processed"""
    print("🎥 Creating Instagram Reel container...")

    creation_id = None
    max_attempts = 10
    wait_sec = 10

    for attempt in range(max_attempts):
        resp = requests.post(f"https://graph.facebook.com/v24.0/{IG_USER_ID}/media",
                             data={"media_type": "REELS",
                                   "video_url": video_url,
                                   "caption": caption,
                                   "access_token": ACCESS_TOKEN})
        data = resp.json()
        if resp.status_code == 200 and "id" in data:
            creation_id = data["id"]
            print(f"✅ Container created | Creation ID: {creation_id}")
            break
        print(f"⏳ Video not ready yet. Retrying in {wait_sec} seconds... ({attempt+1}/{max_attempts})")
        time.sleep(wait_sec)

    if not creation_id:
        print("❌ Failed to create Instagram Reel container after multiple attempts.")
        return

    # Wait until video is processed
    print("⏳ Waiting for video processing...")
    status_url = f"https://graph.facebook.com/v24.0/{creation_id}"
    for attempt in range(20):  # max ~100 seconds
        time.sleep(5)
        check = requests.get(status_url, params={"fields": "status_code", "access_token": ACCESS_TOKEN}).json()
        status = check.get("status_code", "UNKNOWN")
        print(f"   → Status: {status}")
        if status == "FINISHED":
            break
        elif status == "ERROR":
            print("❌ Video processing failed on Instagram.")
            return
    else:
        print("⚠️ Video not ready after waiting. Try increasing wait time.")
        return

    # Publish Reel
    print("📢 Publishing Reel...")
    publish_resp = requests.post(f"https://graph.facebook.com/v24.0/{IG_USER_ID}/media_publish",
                                 data={"creation_id": creation_id, "access_token": ACCESS_TOKEN})
    publish_data = publish_resp.json()

    if "id" in publish_data:
        print(f"🎉 Reel published successfully! Post ID: {publish_data['id']}")
    else:
        print(f"⚠️ Publishing issue: {publish_data}")


# ---------- MAIN ----------
if __name__ == "__main__":
    if not os.path.exists(VIDEO_FOLDER):
        print(f"❌ Folder '{VIDEO_FOLDER}' not found!")
        exit()

    videos = [f for f in os.listdir(VIDEO_FOLDER)
              if f.lower().endswith(('.mp4', '.mov', '.mkv'))]
    if not videos:
        print(f"❌ No video files found in '{VIDEO_FOLDER}'!")
        exit()

    latest_video = max(videos, key=lambda f: os.path.getmtime(os.path.join(VIDEO_FOLDER, f)))
    video_path = os.path.join(VIDEO_FOLDER, latest_video)
    print(f"🎬 Using latest video: {latest_video}")

    topic = "Brain Power"  # Can automate topic extraction
    caption = generate_gemini_caption(topic)

    # Upload video to Google Drive
    direct_url = upload_to_gdrive(video_path)

    # Upload to Instagram
    if direct_url:
        upload_instagram_reel(direct_url, caption)

    print("\n✅ Fully automated Instagram Reel upload finished.")


# ---------- GEMINI CAPTION GENERATION ----------
def generate_gemini_caption(topic: str):
    """Generate a caption + hashtags using Gemini API"""
    genai.configure(api_key=GEMINI_API_KEY)
    prompt = f"""
    Generate a catchy Instagram caption and 10-15 trendy hashtags for a Reel about:
    '{topic}'.
    Format the response as:
    Caption: <your caption>
    Hashtags: #tag1 #tag2 ...
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    text = response.text.strip()

    caption, hashtags = "", ""
    if "Caption:" in text:
        parts = text.split("Hashtags:")
        caption = parts[0].replace("Caption:", "").strip()
        hashtags = parts[1].strip() if len(parts) > 1 else ""
    else:
        caption = text

    full_caption = f"{caption}\n\n{hashtags}"
    print(f"\n📝 Generated Caption:\n{full_caption}\n")
    return full_caption


# ---------- GOOGLE DRIVE UPLOAD ----------
def authenticate_google_drive():
    """Authenticate user and return Drive API service"""
    creds = None
    if os.path.exists("token_drive.pickle"):
        with open("token_drive.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token_drive.pickle", "wb") as token:
            pickle.dump(creds, token)

    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, folder_name):
    """Get or create a folder on Google Drive"""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
    folders = results.get("files", [])

    if folders:
        return folders[0]["id"]
    else:
        file_metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
        folder = service.files().create(body=file_metadata, fields="id").execute()
        print(f"📁 Created new folder '{folder_name}' on Google Drive.")
        return folder.get("id")


def upload_to_gdrive(video_path):
    """Upload the latest video to Google Drive and return its public link"""
    print("⏫ Uploading video to Google Drive...")
    service = authenticate_google_drive()
    folder_id = get_or_create_folder(service, DRIVE_FOLDER_NAME)

    file_name = os.path.basename(video_path)
    mime_type = mimetypes.guess_type(video_path)[0] or "video/mp4"

    file_metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaFileUpload(video_path, mimetype=mime_type, resumable=True)

    uploaded_file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = uploaded_file.get("id")

    # Make file public
    service.permissions().create(fileId=file_id, body={"role": "reader", "type": "anyone"}).execute()

    # Get direct links
    file = service.files().get(fileId=file_id, fields="webViewLink, webContentLink").execute()
    direct_link = file.get("webContentLink")
    print(f"✅ Uploaded successfully to Google Drive!")
    print(f"🔗 Direct Download Link: {direct_link}")
    return direct_link


# ---------- INSTAGRAM UPLOAD ----------
def upload_instagram_reel(video_url, caption):
    """Upload video to Instagram Reels via Graph API"""
    print("🎥 Creating Instagram Reel container...")

    url = f"https://graph.facebook.com/v24.0/{IG_USER_ID}/media"
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": ACCESS_TOKEN
    }

    resp = requests.post(url, data=params)
    data = resp.json()
    if resp.status_code != 200 or "id" not in data:
        print(f"❌ Upload failed: {data}")
        return

    creation_id = data["id"]
    print(f"✅ Container created | Creation ID: {creation_id}")

    # 🕐 Wait until Instagram finishes processing
    print("⏳ Waiting for video processing...")
    status_url = f"https://graph.facebook.com/v24.0/{creation_id}"
    status = "IN_PROGRESS"
    for attempt in range(20):  # up to ~100 seconds
        time.sleep(5)
        check = requests.get(status_url, params={
            "fields": "status_code",
            "access_token": ACCESS_TOKEN
        }).json()
        status = check.get("status_code", "UNKNOWN")
        print(f"   → Status: {status}")
        if status == "FINISHED":
            break
        elif status == "ERROR":
            print("❌ Video processing failed on Instagram.")
            return

    if status != "FINISHED":
        print("⚠️ Video not ready after waiting. Try increasing wait time.")
        return

    # ✅ Publish Reel
    print("📢 Publishing Reel...")
    publish_url = f"https://graph.facebook.com/v24.0/{IG_USER_ID}/media_publish"
    publish_resp = requests.post(publish_url, data={
        "creation_id": creation_id,
        "access_token": ACCESS_TOKEN
    })
    publish_data = publish_resp.json()

    if "id" in publish_data:
        print(f"🎉 Reel published successfully! Post ID: {publish_data['id']}")
    else:
        print(f"⚠️ Publishing issue: {publish_data}")

# ---------- MAIN ----------
if __name__ == "__main__":
    if not os.path.exists(VIDEO_FOLDER):
        print(f"❌ Folder '{VIDEO_FOLDER}' not found!")
        exit()

    videos = [f for f in os.listdir(VIDEO_FOLDER)
              if f.lower().endswith(('.mp4', '.mov', '.mkv'))]
    if not videos:
        print(f"❌ No video files found in '{VIDEO_FOLDER}'!")
        exit()

    latest_video = max(videos, key=lambda f: os.path.getmtime(os.path.join(VIDEO_FOLDER, f)))
    video_path = os.path.join(VIDEO_FOLDER, latest_video)
    print(f"🎬 Using latest video: {latest_video}")

    topic = "Glaciers"
    caption = generate_gemini_caption(topic)

    # Upload video to Google Drive
    direct_url = upload_to_gdrive(video_path)

    # Upload to Instagram
    if direct_url:
        upload_instagram_reel(direct_url, caption)

    print("\n✅ Fully automated Instagram Reel upload finished.")
