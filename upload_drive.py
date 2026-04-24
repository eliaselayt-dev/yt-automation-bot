import os
import json
import re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/drive",
]
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")


def auth():
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return creds


def natural_sort_key(filename):
    """Sort filenames naturally so video_2.mp4 comes before video_10.mp4"""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r'(\d+)', filename)
    ]


def read_global_notes(drive_service):
    results = drive_service.files().list(
        q=f"'{DRIVE_FOLDER_ID}' in parents and trashed=false and name='global_notes.txt'",
        fields="files(id, name)"
    ).execute()
    files = results.get("files", [])

    if not files:
        return "Auto Upload", "Default Description", ["shorts"]

    file_id = files[0]["id"]
    content = drive_service.files().get_media(fileId=file_id).execute().decode("utf-8")

    title, description, tags = "Auto Upload", "", []
    for line in content.splitlines():
        if line.startswith("TITLE:"):
            title = line.replace("TITLE:", "").strip()
        elif line.startswith("DESCRIPTION:"):
            description = line.replace("DESCRIPTION:", "").strip()
        elif line.startswith("TAGS:"):
            tags = [t.strip() for t in line.replace("TAGS:", "").split(",")]

    return title, description, tags


def get_drive_videos(drive_service):
    """Get ALL videos from Drive with pagination, then sort naturally by filename."""
    all_files = []
    page_token = None

    while True:
        params = {
            "q": f"'{DRIVE_FOLDER_ID}' in parents and trashed=false and name contains '.mp4'",
            "fields": "nextPageToken, files(id, name)",
            "pageSize": 1000,
        }
        if page_token:
            params["pageToken"] = page_token

        results = drive_service.files().list(**params).execute()
        all_files.extend(results.get("files", []))
        page_token = results.get("nextPageToken")

        if not page_token:
            break

    # Natural sort: video_1, video_2 ... video_9, video_10, video_11 (not video_1, video_10, video_2)
    all_files.sort(key=lambda f: natural_sort_key(f["name"]))

    print(f"📂 Found {len(all_files)} videos. First 5 in order:")
    for i, f in enumerate(all_files[:5]):
        print(f"  {i+1}. {f['name']}")
    if len(all_files) > 5:
        print(f"  ... and {len(all_files) - 5} more")

    return all_files


def download_file(drive_service, file_id, filename):
    content = drive_service.files().get_media(fileId=file_id).execute()
    with open(filename, "wb") as f:
        f.write(content)


def delete_file(drive_service, file_id):
    drive_service.files().delete(fileId=file_id).execute()


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
    media = MediaFileUpload(file_path, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media,
    )
    request.execute()


def main():
    # Verify token.json
    if not os.path.exists("token.json"):
        raise FileNotFoundError("token.json not found")
    with open("token.json", "r") as f:
        content = f.read().strip()
    if not content:
        raise ValueError("token.json is empty")
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"token.json is not valid JSON: {e}")
    print("token.json OK")

    creds = auth()
    youtube = build("youtube", "v3", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    title, description, tags = read_global_notes(drive_service)
    print(f"Title: {title}, Tags: {tags}")

    videos = get_drive_videos(drive_service)
    if not videos:
        print("No videos found in Drive folder.")
        return

    # Always upload the FIRST file in sorted order (lowest number)
    file = videos[0]
    file_id = file["id"]
    filename = file["name"]

    print(f"\n⬇️  Downloading: {filename}")
    download_file(drive_service, file_id, filename)

    try:
        upload_video(youtube, filename, title, description, tags)
        print(f"✅ Uploaded to YouTube: {filename}")
        delete_file(drive_service, file_id)
        print(f"🗑️  Deleted from Drive: {filename}")
    except HttpError as e:
        print(f"❌ Upload error: {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)


if __name__ == "__main__":
    main()
