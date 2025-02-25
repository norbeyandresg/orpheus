import os
import re

from dotenv import load_dotenv
from yt_dlp import YoutubeDL
from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth.credentials import OAuthCredentials
from postprocessors import AddTrackMetadataPP

# load environment variables
load_dotenv()


class Orpheus:
    def __init__(self):
        # load credentials
        _client_id = os.environ.get("YTM_CLIENT_ID", "")
        _client_secret = os.environ.get("YTM_CLIENT_SECRET", "")
        _creds = OAuthCredentials(client_id=_client_id, client_secret=_client_secret)

        # init client
        self.ytmusic = YTMusic("oauth.json", oauth_credentials=_creds)

        # set library path
        self.library_path = os.environ.get("LIBRARY_PATH", "./downloads")

        self.archive = set()
        self.m3u8_data = ["#EXTM3U\n"]

    def load_download_archive(self) -> None:
        with open(f"{self.library_path}/download_archive.txt", "r") as f:
            self.archive = set(f.read().replace("youtube", "").strip().split())

    def update_download_archive(self) -> None:
        with open(f"{self.library_path}/download_archive.txt", "w") as f:
            lines = [f"youtube {track_id}\n" for track_id in self.archive]
            f.writelines(lines)

    def get_playlists(self):
        return self.ytmusic.get_library_playlists()

    def get_playlist_details(self, playlist_id: str, limit=None):
        return self.ytmusic.get_playlist(playlist_id, limit=limit)

    def create_m3u8_playlist_file(self, playlist_name: str):
        with open(f"{self.library_path}/{playlist_name}.m3u8", "w") as f:
            f.writelines(self.m3u8_data)

    def get_ydl_opts(self):
        return {
            "format": "bestaudio/best",
            "outtmpl": f"{self.library_path}/%(id)s.%(ext)s",
            "ignoreerrors": True,
            "noplaylist": True,
            "download_archive": f"{self.library_path}/download_archive.txt",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }
            ],
        }

    def download_playlist_tracks(self, playlist: dict):
        tracks = playlist.get("tracks", [])
        base_url = "https://www.youtube.com/watch?v="

        with YoutubeDL(self.get_ydl_opts()) as ydl:
            ydl.add_post_processor(AddTrackMetadataPP(), when="post_process")

            for track in tracks:
                download_errors = ydl.download(f"{base_url}{track.get('videoId')}")
                if bool(download_errors):
                    print("download error: ", download_errors)
                else:
                    entry = [
                        f"#EXTINF:{track.get('duration_seconds', '-1')},{track.get('title')}\n",
                        f"{self.library_path}/{track.get('title')}.mp3\n",
                    ]
                    # self.m3u8_data.append(f"{track.get('title')}.mp3\n")
                    self.m3u8_data.extend(entry)

    def cleanup_missing_tracks(self, playlist: dict):
        upstream_tracks = {track.get("videoId") for track in playlist.get("tracks", [])}
        pattern = re.compile(r"\[(.*?)\]\.mp3$", re.IGNORECASE)

        with os.scandir(self.library_path) as entries:
            for entry in entries:
                if entry.is_file() and entry.name.lower().endswith(".mp3"):
                    match = pattern.search(entry.name)
                    if match:
                        track_id = match.group(1)
                        if track_id not in upstream_tracks:
                            try:
                                os.remove(entry.path)
                                self.archive.remove(track_id)
                                print(f"Deleted: {entry.path}")
                            except Exception as e:
                                print(f"Error deleting {entry.path}: {e}")
                    else:
                        print(f"Skipping file with unrecognized format: {entry.name}")


if __name__ == "__main__":
    o = Orpheus()
    # playlists = o.get_playlists()
    playlist = o.get_playlist_details("PLcG-71EYpgSrJFfhjnn1oU3GPHf2C3tqq")
    o.download_playlist_tracks(playlist)
    o.create_m3u8_playlist_file(playlist.get("title", "default"))
    o.load_download_archive()
    o.cleanup_missing_tracks(playlist)
    o.update_download_archive()
