import PIL.Image
from google import genai
from google.genai import types
from io import BytesIO
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

prompt = """
    Show me a picture of a nano banana dish in a fancy restaurant with a Gemini theme
  """

response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=[prompt],
)

for part in response.candidates[0].content.parts:
  if part.text is not None:
    print(part.text)
  elif part.inline_data is not None:
    image = PIL.Image.open(BytesIO(part.inline_data.data))
    image.save(f"generated_image.png")