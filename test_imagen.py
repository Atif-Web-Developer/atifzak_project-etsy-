import requests
import json

import os

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}"

payload = {
    "instances": [
        {
            "prompt": "A professional, photorealistic mockup of a blank white t-shirt."
        }
    ],
    "parameters": {
        "sampleCount": 1,
        "aspectRatio": "1:1",
        "outputMimeType": "image/jpeg"
    }
}

headers = {
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    print("Status Code:", response.status_code)
    print("Response JSON:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print("Error:", e)
