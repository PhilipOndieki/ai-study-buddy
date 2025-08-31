import custom_types.payload
from constants import INSTAGRAM_BASE_URL, INSTAGRAM_MESSAGES_ENDPOINT
import requests

class Instagram:
    access_token: str
    
    def __init__(self, access_token: str):
        self.access_token = access_token
    def send_text(self, text: str, recipient_id: str):
        url = f"{INSTAGRAM_BASE_URL}{INSTAGRAM_MESSAGES_ENDPOINT}"
        payload = {
            "recipient": {
                "id": recipient_id
            },
            "message": {
                "text": text
            }
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error sending message: {response.status_code} - {response.text}")
        
    @staticmethod
    def process_payload(payload: dict) -> custom_types.payload.InstagramPayload:
        try:
            return custom_types.payload.InstagramPayload(**payload)
        except Exception as e:
            raise ValueError(f"Invalid payload: {e}")

        
        