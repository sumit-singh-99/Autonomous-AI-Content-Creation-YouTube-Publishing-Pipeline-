import os
import requests
import random
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")  # Put your valid API key here
THUMBNAIL_DIR = "thumbnails"

# Ensure the thumbnail directory exists
if not os.path.exists(THUMBNAIL_DIR):
    os.makedirs(THUMBNAIL_DIR)

def download_pexels_images(topic, num_images=5):
    """
    Downloads images from Pexels for a given topic and resizes them to 1080x1920.
    
    Args:
        topic (str): Search query for images.
        num_images (int): Number of images to download.
    
    Returns:
        list: Paths of downloaded and resized images.
    """
    headers = {'Authorization': PEXELS_API_KEY}
    downloaded_images = []
    page = 1
    images = []

    # Fetch images until we have enough
    while len(images) < num_images:
        url = f"https://api.pexels.com/v1/search?query={topic}&per_page=80&page={page}"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Pexels API error: {response.status_code}, {response.text}")
            break
        
        data = response.json()
        if not data.get('photos'):
            print("No more images found for this topic.")
            break
        
        images.extend(data['photos'])
        page += 1

    random.shuffle(images)

    for img in images:
        if len(downloaded_images) >= num_images:
            break

        img_url = img['src']['original']
        file_path = os.path.join(THUMBNAIL_DIR, f"thumbnail.jpg")

        try:
            response = requests.get(img_url, stream=True)
            response.raise_for_status()

            # Open image, resize to 1080x1920
            image = Image.open(BytesIO(response.content))
            image = image.resize((1080, 1920))
            image.save(file_path)
            downloaded_images.append(file_path)

            print(f"Downloaded and resized thumbnail: {file_path}")

        except Exception as e:
            print(f"Failed to download or process image {img['id']}: {e}")

    return downloaded_images

# --- Usage Example ---
if __name__ == "__main__":
    topic = "renewable energy"
    thumbnails = download_pexels_images(topic, num_images=1)
    print(f"Downloaded {len(thumbnails)} thumbnails.")
