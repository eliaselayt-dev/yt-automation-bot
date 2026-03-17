import os
import json
import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

# ===== CONFIG =====
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")

SCOPES_DRIVE = ['https://www.googleapis.com/auth/drive']
SCOPES_YT = ["https://www.googleapis.com/auth/youtube.upload"]

# ===== AUTH DRIVE (SERVICE ACCOUNT) =====
def auth_drive():
    credentials = service_account.Credentials.from_service_account_file(
        "service_account.json",
        scopes=SCOPES_DRIVE
    )
    return build("drive", "v3", credentials=credentials)

# ===== AUTH YOUTUBE =====
def auth_youtube():
    with open("token.json", "rb") as f:
        creds = pickle.load(f)
    return build("youtube", "v3", credentials=creds)

# ===== GET VIDEOS =====
def get_videos(drive):
    query = f"'{DRIVE_FOLDER_ID}' in parents and mimeType='video/mp4'"
    results = drive.files().list(q=query).execute()
    return results.get("files", [])

# ===== DOWNLOAD VIDEO =====
def download_video(drive, file_id, name):
    request = drive.files().get_media(fileId=file_id)
    with open(name, "wb") as f:
        f.write(request.execute())

# ===== UPLOAD YOUTUBE =====
def upload(youtube, path):
    body = {
        "snippet": {
            "title": "Auto Upload",
            "description": "Automation",
            "categoryId": "22"
        },
        "status": {"privacyStatus": "public"}
    }
    media = MediaFileUpload(path)
    youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()

# ===== MAIN =====
def main():
    drive = auth_drive()
    yt = auth_youtube()

    videos = get_videos(drive)
    if not videos:
        print("No videos")
        return

    v = videos[0]
    name = v["name"]

    download_video(drive, v["id"], name)
    upload(yt, name)

    drive.files().delete(fileId=v["id"]).execute()
    os.remove(name)

    print("Uploaded:", name)

if __name__ == "__main__":
    main()
