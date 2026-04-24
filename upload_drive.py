import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")


def auth_youtube():
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def auth_drive():
    scope = ["https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("client_secret.json", scope)
    gauth = GoogleAuth()
    gauth.credentials = creds
    return GoogleDrive(gauth)


def read_global_notes(drive):
    file_list = drive.ListFile({"q": f"'{DRIVE_FOLDER_ID}' in parents and trashed=false"}).GetList()
    notes_files = [f for f in file_list if f["title"] == "global_notes.txt"]
    if not notes_files:
        return "Auto Upload", "Default Description", ["shorts"]
    notes_files[0].GetContentFile("global_notes.txt")
    title, description, tags = "Auto Upload", "", []
    with open("global_notes.txt", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("TITLE:"):
                title = line.replace("TITLE:", "").strip()
            elif line.startswith("DESCRIPTION:"):
                description = line.replace("DESCRIPTION:", "").strip()
            elif line.startswith("TAGS:"):
                tags = [t.strip() for t in line.replace("TAGS:", "").split(",")]
    return title, description, tags


def get_drive_videos(drive):
    file_list = drive.ListFile({"q": f"'{DRIVE_FOLDER_ID}' in parents and trashed=false"}).GetList()
    return [f for f in file_list if f["title"].endswith(".mp4")]


def upload_video(youtube, file_path, title, description, tags):
    request_body = {
        "snippet": {"title": title, "description": description, "tags": tags, "categoryId": "22"},
        "status": {"privacyStatus": "public"},
    }
    media = MediaFileUpload(file_path, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)
    request.execute()


def main():
    # Verify token.json exists and is valid before doing anything
    if not os.path.exists("token.json"):
        raise FileNotFoundError("token.json not found — TOKEN_JSON secret was not written correctly")
    with open("token.json", "r") as f:
        content = f.read().strip()
    if not content:
        raise ValueError("token.json is empty — TOKEN_JSON secret is blank")
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"token.json is not valid JSON: {e}\nContent preview: {content[:100]}")

    print("token.json OK")

    youtube = auth_youtube()
    drive = auth_drive()
    title, description, tags = read_global_notes(drive)
    videos = get_drive_videos(drive)

    if not videos:
        print("No videos found in Drive folder.")
        return

    file = videos[0]
    local_filename = file["title"]
    file.GetContentFile(local_filename)

    try:
        upload_video(youtube, local_filename, title, description, tags)
        print(f"Uploaded: {local_filename}")
        file.Delete()
    except HttpError as e:
        print(f"Upload error: {e}")
    finally:
        if os.path.exists(local_filename):
            os.remove(local_filename)


if __name__ == "__main__":
    main()
