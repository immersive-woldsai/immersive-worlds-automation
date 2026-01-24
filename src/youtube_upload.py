import os
from typing import List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_creds() -> Credentials:
    return Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )


def verify_auth() -> None:
    creds = _get_creds()
    creds.refresh(Request())


def _bool_env(name: str, default: str = "false") -> bool:
    v = os.getenv(name, default).strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def set_thumbnail(youtube, video_id: str, thumbnail_file: str) -> None:
    request = youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(thumbnail_file),
    )
    request.execute()
    print("[OK] Thumbnail set:", thumbnail_file, flush=True)


def upload_video(
    video_file: str,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy_status: str = "unlisted",
    category_id: str = "22",
    language: str = "en",
    thumbnail_file: Optional[str] = None,
) -> str:
    creds = _get_creds()

    # Fail fast if token is dead/revoked
    try:
        creds.refresh(Request())
    except Exception as e:
        print(
            "[ERROR] OAuth refresh failed. Token may be expired/revoked.\n"
            f"Reason: {e}",
            flush=True,
        )
        raise

    youtube = build("youtube", "v3", credentials=creds)
    notify_subscribers = _bool_env("YT_NOTIFY_SUBSCRIBERS", "false")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": category_id,
            "defaultLanguage": language,
            "defaultAudioLanguage": language,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_file, mimetype="video/mp4", resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
        notifySubscribers=notify_subscribers,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%", flush=True)

    video_id = response["id"]
    print("Uploaded video id:", video_id, flush=True)

    if thumbnail_file:
        try:
            if os.path.exists(thumbnail_file):
                set_thumbnail(youtube, video_id, thumbnail_file)
            else:
                print("[WARN] Thumbnail file not found:", thumbnail_file, flush=True)
        except Exception as e:
            print("[WARN] Thumbnail set failed:", e, flush=True)

    return video_id
