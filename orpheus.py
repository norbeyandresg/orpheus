import os
import re
from typing import Dict, List, Set
from dotenv import load_dotenv
from yt_dlp import YoutubeDL
from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth.credentials import OAuthCredentials
from postprocessors import AddTrackMetadataPP

# load environment variables
load_dotenv()


class Orpheus:
    ytmusic: YTMusic
    library_path: str
    archive: Set
    m3u8_data: List[str]

    def __init__(self) -> None:
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

    def get_playlists(self) -> List[Dict]:
        return self.ytmusic.get_library_playlists()

    def get_playlist_details(self, playlist_id: str) -> Dict:
        return self.ytmusic.get_playlist(playlistId=playlist_id, limit=None)

    def create_m3u8_playlist_file(self, playlist_name: str) -> None:
        with open(f"{self.library_path}/{playlist_name}.m3u8", "w") as f:
            f.writelines(self.m3u8_data)

        self.m3u8_data = ["#EXTM3U\n"]

    def get_ydl_opts(self) -> Dict:
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

    def download_playlist_tracks(self, playlist: dict) -> None:
        tracks = playlist.get("tracks", [])
        base_url = "https://www.youtube.com/watch?v="

        print(f"Processing {len(tracks)} from playlist {playlist.get('title')}")
        with YoutubeDL(self.get_ydl_opts()) as ydl:
            ydl.add_post_processor(AddTrackMetadataPP(), when="post_process")

            for track in tracks:
                ydl.download(f"{base_url}{track.get('videoId')}")
                entry = [
                    f"#EXTINF:{track.get('duration_seconds', '-1')},{track.get('title')}\n",
                    f"{self.library_path}/{track.get('title')} [{track.get('videoId')}].mp3\n",
                ]
                self.m3u8_data.extend(entry)

    def cleanup_missing_tracks_from_playlist(self, playlist: dict) -> None:
        self.load_download_archive()
        pattern = re.compile(r"\[(.*?)\]\.mp3$", re.IGNORECASE)
        upstream_tracks = {track.get("videoId") for track in playlist.get("tracks", [])}
        local_tracks = []

        # load local
        with open(f"{self.library_path}/{playlist.get('title')}.m3u8", "a+") as f:
            f.seek(0)
            lines = f.readlines()
            local_tracks = {
                line.replace("[", "]").split("]")[-2]
                for line in lines
                if "#EXT" not in line
            }

        missing_tracks = local_tracks - upstream_tracks

        print(f"Removing {len(missing_tracks)} tracks")
        with os.scandir(self.library_path) as entries:
            for entry in entries:
                if entry.is_file() and entry.name.lower().endswith(".mp3"):
                    match = pattern.search(entry.name)
                    if match:
                        track_id = match.group(1)
                        if track_id in missing_tracks:
                            try:
                                os.remove(entry.path)
                                self.archive.remove(track_id)
                                print(f"Deleted: {entry.path}")
                            except Exception as e:
                                print(f"Error deleting {entry.path}: {e}")
                    else:
                        print(f"Skipping file with unrecognized format: {entry.name}")

        self.update_download_archive()
