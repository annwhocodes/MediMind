import requests
from dotenv import load_dotenv
import os  # <== missing in your snippet

load_dotenv()

# Get the actual values from environment
api_key = os.getenv("GOOGLE_API_KEY")
cse_id = os.getenv("GOOGLE_CSE_ID")

url = "https://www.googleapis.com/customsearch/v1"
params = {
    "q": "test search",
    "key": api_key,
    "cx": cse_id
}

response = requests.get(url, params=params)
print(response.status_code)
print(response.json())
