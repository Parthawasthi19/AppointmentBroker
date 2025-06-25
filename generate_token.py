# generate_token.py

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# This scope allows the app to read and write to the calendar.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def generate_google_token():
    """
    This function performs the Google OAuth2 flow.
    It will open a browser window for you to log in and authorize access.
    Upon success, it will create a 'token.json' file with your credentials.
    """
    creds = None
    
    # Check if a credentials.json file exists. This is required.
    if not os.path.exists("credentials.json"):
        print("Error: credentials.json file not found. Please download it from your Google Cloud Console.")
        return

    # This is the core of the interactive flow.
    # It uses your credentials.json to know which application is asking for permission.
    try:
        print("Starting Google Authentication flow...")
        print("A browser window will open for you to log in and grant permissions.")
        
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        # This line will start a local web server and open the browser.
        creds = flow.run_local_server(port=0)

        # Save the credentials for future use in the token.json file.
        with open("token.json", "w") as token:
            token.write(creds.to_json())
        
        print("\nSUCCESS! 'token.json' has been created successfully.")
        print("You can now close this script and proceed with the deployment steps.")

    except Exception as e:
        print(f"\nAn error occurred during the authentication process: {e}")

if __name__ == "__main__":
    generate_google_token()