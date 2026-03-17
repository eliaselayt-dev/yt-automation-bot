import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# YouTube scopes
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")

# Authenticate YouTube using token.json (with refresh_token)
def auth_youtube():
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    youtube = build("youtube", "v3", credentials=creds)
    return youtube

# Authenticate Google Drive
def auth_drive():
    # PyDrive expects a file, not a string
    gauth = GoogleAuth()
    gauth.LoadClientConfigFile("client_secret.json")  # service account JSON
    gauth.LocalWebserverAuth()
    return GoogleDrive(gauth)

# Read global notes from Drive folder
def read_global_notes(drive):
    file_list = drive.ListFile({'q': f"'{DRIVE_FOLDER_ID}' in parents and trashed=false"}).GetList()
    notes_file = [f for f in file_list if f['title'] == "global_notes.txt"]
    if not notes_file:
        return "Automated Upload", "Default Description", ["shorts"]
    notes_file[0].GetContentFile("global_notes.txt")
    title, description, tags = "Automated Upload", "", []
    with open("global_notes.txt", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("TITLE:"):
                title = line.replace("TITLE:", "").strip()
            elif line.startswith("DESCRIPTION:"):
                description = line.replace("DESCRIPTION:", "").strip()
            elif line.startswith("TAGS:"):
                tags = [t.strip() for t in line.replace("TAGS:", "").strip().split(",")]
    return title, description, tags

# Get videos in Drive folder
def get_drive_videos(drive):
    file_list = drive.ListFile({'q': f"'{DRIVE_FOLDER_ID}' in parents and trashed=false"}).GetList()
    return [f for f in file_list if f['title'].endswith(".mp4")]

# Upload video to YouTube
def upload_video(youtube, file_path, title, description, tags):
    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22",
        },
        "status": {"privacyStatus": "public"},
    }
    media = MediaFileUpload(file_path)
    request = youtube.videos().insert(
        part="snippet,status", body=request_body, media_body=media
    )
    request.execute()

def main():
    # Authenticate
    youtube = auth_youtube()
    drive = auth_drive()

    # Read notes
    title, description, tags = read_global_notes(drive)

    # Get videos
    videos = get_drive_videos(drive)
    if not videos:
        print("No videos found in Drive folder.")
        return

    # Upload first video
    file = videos[0]
    file.GetContentFile(file['title'])
    try:
        upload_video(youtube, file['title'], title, description, tags)
        print(f"✅ Uploaded: {file['title']}")
        file.Delete()  # remove from Drive
    except HttpError as e:
        print("❌ Upload error:", e)
    finally:
        if os.path.exists(file['title']):
            os.remove(file['title'])

if __name__ == "__main__":
    main()
