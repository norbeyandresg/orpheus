import os
import re
import json
from typing import Callable, Dict, List, Optional, Set
from dotenv import load_dotenv
from yt_dlp import YoutubeDL
from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth.credentials import OAuthCredentials
from postprocessors import BeetsPostProcessor
from logger_setup import setup_logger

# Initialize logger
logger = setup_logger("Orpheus")

# load environment variables
load_dotenv()


class Orpheus:
    ytmusic: YTMusic
    library_path: str
    archive: Set
    m3u8_tracks: List[Dict]

    def __init__(self) -> None:
        # load credentials
        _client_id = os.environ.get("YTM_CLIENT_ID", "")
        _client_secret = os.environ.get("YTM_CLIENT_SECRET", "")
        _creds = OAuthCredentials(client_id=_client_id, client_secret=_client_secret)

        # init client
        self.ytmusic = YTMusic("browser.json")

        # set library path
        self.library_path = os.environ.get(
            "LIBRARY_PATH", "/Users/norbey/Music/Library"
        )
        self.m3u8_base_path = os.environ.get(
            "M3U8_BASE_PATH", "/storage/external_sd/Music"
        )

        # set playlist paths
        self.fiio_playlist_path = os.environ.get(
            "FIIO_PLAYLIST_PATH", os.path.expanduser("~/Music/Playlists/fiio")
        )
        self.library_playlist_path = os.environ.get(
            "LIBRARY_PLAYLIST_PATH", os.path.expanduser("~/Music/Playlists/library")
        )
        self.navidrone_playlist_path = os.environ.get(
            "NAVIDRONE_PLAYLIST_PATH", os.path.expanduser("~/Music/Playlists/navidrone")
        )

        # ensure playlist paths exist
        os.makedirs(self.fiio_playlist_path, exist_ok=True)
        os.makedirs(self.library_playlist_path, exist_ok=True)
        os.makedirs(self.navidrone_playlist_path, exist_ok=True)

        # registry file tracking combined ("blend") playlists and their sources
        self.blends_path = os.environ.get(
            "BLENDS_PATH", os.path.join(os.getcwd(), "blends.json")
        )

        self.archive = set()
        self.m3u8_tracks = []

    def load_blends(self) -> Dict[str, Dict]:
        """Load the registry of combined ("blend") playlists.

        Returns a mapping of blend name -> {"sources": List[str]}, where each
        source is the name of an already-downloaded playlist.
        """
        if os.path.exists(self.blends_path):
            try:
                with open(self.blends_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Error reading blends registry: {e}")
        return {}

    def save_blend(self, name: str, source_playlist_names: List[str]) -> None:
        """Record (or update) a blend's source definition."""
        blends = self.load_blends()
        blends[name] = {"sources": source_playlist_names}
        with open(self.blends_path, "w") as f:
            json.dump(blends, f, indent=2)

    def load_download_archive(self) -> None:
        archive_path = f"{self.library_path}/download_archive.txt"
        if os.path.exists(archive_path):
            with open(archive_path, "r") as f:
                self.archive = set(f.read().replace("youtube", "").strip().split())

    def update_download_archive(self) -> None:
        with open(f"{self.library_path}/download_archive.txt", "w") as f:
            lines = [f"youtube {track_id}\n" for track_id in self.archive]
            f.writelines(lines)

    def get_playlists(self) -> List[Dict]:
        return self.ytmusic.get_library_playlists()

    def get_playlist_details(self, playlist_id: str) -> Dict:
        return self.ytmusic.get_playlist(playlistId=playlist_id, limit=None)

    def get_local_playlists(self) -> List[str]:
        """Return the names of already-downloaded playlists (from the library
        .m3u8 files), excluding any registered blends."""
        if not os.path.exists(self.library_playlist_path):
            return []
        blend_names = set(self.load_blends().keys())
        names = [
            os.path.splitext(f)[0]
            for f in os.listdir(self.library_playlist_path)
            if f.endswith(".m3u8")
        ]
        return sorted(n for n in names if n not in blend_names)

    def _parse_m3u8_tracks(self, playlist_name: str) -> List[Dict]:
        """Parse the library .m3u8 file for a playlist into track dicts of
        {videoId, title, duration_seconds}."""
        playlist_file = os.path.join(
            self.library_playlist_path, f"{playlist_name}.m3u8"
        )
        tracks: List[Dict] = []
        if not os.path.exists(playlist_file):
            logger.error(f"Playlist file not found: {playlist_file}")
            return tracks

        title = None
        duration = "-1"
        with open(playlist_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line == "#EXTM3U":
                    continue
                if line.startswith("#EXTINF:"):
                    # format: #EXTINF:<duration>,<title>
                    meta = line[len("#EXTINF:") :]
                    duration, _, title = meta.partition(",")
                elif not line.startswith("#"):
                    video_id = os.path.splitext(os.path.basename(line))[0]
                    tracks.append(
                        {
                            "videoId": video_id,
                            "title": title,
                            "duration_seconds": duration,
                        }
                    )
                    title, duration = None, "-1"
        return tracks

    def combine_local_playlists(
        self, name: str, source_playlist_names: List[str]
    ) -> None:
        """Create a new blend .m3u8 by mixing already-downloaded playlists.

        Tracks are merged across the source playlists, de-duplicated by
        videoId while preserving first-seen order, then written out in all
        three .m3u8 variants under the blend ``name``.
        """
        seen: Set[str] = set()
        combined: List[Dict] = []

        for source in source_playlist_names:
            logger.info(f"Mixing in tracks from playlist: {source}")
            for track in self._parse_m3u8_tracks(source):
                video_id = track.get("videoId")
                if video_id and video_id not in seen:
                    seen.add(video_id)
                    combined.append(track)

        logger.info(f"Creating blend '{name}' with {len(combined)} tracks")
        self.m3u8_tracks = combined
        self.create_m3u8_playlist_file(name)
        self.save_blend(name, source_playlist_names)

    def update_local_blend(
        self, name: str, source_playlist_names: List[str] | None = None
    ) -> None:
        """Regenerate an existing blend from its (possibly updated) source
        playlists. If ``source_playlist_names`` is omitted, the sources
        recorded in the blends registry are used."""
        if source_playlist_names is None:
            blend = self.load_blends().get(name)
            if not blend:
                raise ValueError(
                    f"No recorded sources for blend '{name}'; "
                    "pass source_playlist_names explicitly."
                )
            source_playlist_names = blend.get("sources", [])

        self.combine_local_playlists(name, source_playlist_names)

    def create_m3u8_playlist_file(self, playlist_name: str) -> None:
        # Generate Fiio version
        fiio_file = os.path.join(self.fiio_playlist_path, f"{playlist_name}.m3u8")
        with open(fiio_file, "w") as f:
            f.write("#EXTM3U\n")
            for track in self.m3u8_tracks:
                f.write(
                    f"#EXTINF:{track.get('duration_seconds', '-1')},{track.get('title')}\n"
                )
                f.write(f"{self.m3u8_base_path}/{track.get('videoId')}.mp3\n")

        # Generate Library version
        library_file = os.path.join(self.library_playlist_path, f"{playlist_name}.m3u8")
        with open(library_file, "w") as f:
            f.write("#EXTM3U\n")
            for track in self.m3u8_tracks:
                f.write(
                    f"#EXTINF:{track.get('duration_seconds', '-1')},{track.get('title')}\n"
                )
                f.write(f"{self.library_path}/{track.get('videoId')}.mp3\n")

        # Generate Navidrone version
        navidrone_file = os.path.join(
            self.navidrone_playlist_path, f"{playlist_name}.m3u8"
        )
        with open(navidrone_file, "w") as f:
            f.write("#EXTM3U\n")
            for track in self.m3u8_tracks:
                f.write(
                    f"#EXTINF:{track.get('duration_seconds', '-1')},{track.get('title')}\n"
                )
                f.write(f"/music/Library/{track.get('videoId')}.mp3\n")

        self.m3u8_tracks = []

    def get_ydl_opts(self, quiet: bool = False) -> Dict:
        opts = {
            "format": "bestaudio/best",
            "outtmpl": f"{self.library_path}/%(id)s.%(ext)s",
            "ignoreerrors": True,
            "writethumbnail": True,
            "noplaylist": True,
            "download_archive": f"{self.library_path}/download_archive.txt",
            "remote_components": ["ejs:github"],
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                },
                {
                    "key": "EmbedThumbnail",
                },
                {
                    "key": "FFmpegMetadata",
                },
            ],
            "postprocessor_args": {
                "thumbnailsconvertor+ffmpeg_o": ["-c:v", "mjpeg", "-vf", "crop=ih:ih"],
                "metadata+ffmpeg_o": ["-metadata", "genre="],
            },
            "sleep_interval": 5,
            "max_sleep_interval": 10,
        }

        # Use cookies if available to bypass 429/bot detection
        cookies_path = os.path.join(os.getcwd(), "cookies.txt")
        if os.path.exists(cookies_path):
            opts["cookiefile"] = cookies_path
            logger.info(f"Using cookies from: {cookies_path}")

        # In quiet mode (the TUI) keep yt-dlp off stdout, which would corrupt a
        # full-screen display. Route its output to our logger instead.
        if quiet:
            opts["quiet"] = True
            opts["no_warnings"] = True
            opts["noprogress"] = True
            opts["logger"] = logger

        return opts

    def download_playlist_tracks(
        self,
        playlist: dict,
        on_progress: Optional[Callable[[int, int], None]] = None,
        quiet: bool = False,
    ) -> None:
        """Download every track in ``playlist``.

        ``on_progress`` (if given) is called with (completed, total) after each
        track so a caller such as the TUI can render a progress bar. ``quiet``
        suppresses yt-dlp's own stdout output.
        """
        tracks = playlist.get("tracks", [])
        total = len(tracks)
        base_url = "https://www.youtube.com/watch?v="

        logger.info(f"Processing {total} tracks from playlist {playlist.get('title')}")
        with YoutubeDL(self.get_ydl_opts(quiet=quiet)) as ydl:
            ydl.add_post_processor(BeetsPostProcessor())
            for index, track in enumerate(tracks, start=1):
                ydl.download(f"{base_url}{track.get('videoId')}")
                # Store track metadata for playlist generation
                self.m3u8_tracks.append(
                    {
                        "videoId": track.get("videoId"),
                        "title": track.get("title"),
                        "duration_seconds": track.get("duration_seconds", "-1"),
                    }
                )
                if on_progress is not None:
                    on_progress(index, total)

    def remove_playlist(self, name: str) -> None:
        """Delete a playlist/blend's local .m3u8 files from every variant
        directory and drop it from the blends registry if present."""
        for path in (
            self.fiio_playlist_path,
            self.library_playlist_path,
            self.navidrone_playlist_path,
        ):
            playlist_file = os.path.join(path, f"{name}.m3u8")
            if os.path.exists(playlist_file):
                try:
                    os.remove(playlist_file)
                    logger.info(f"Removed playlist file: {playlist_file}")
                except OSError as e:
                    logger.error(f"Error removing {playlist_file}: {e}")

        blends = self.load_blends()
        if name in blends:
            del blends[name]
            with open(self.blends_path, "w") as f:
                json.dump(blends, f, indent=2)
            logger.info(f"Removed blend '{name}' from registry")

    def cleanup_missing_tracks_from_playlist(self, playlist: dict) -> None:
        self.load_download_archive()
        upstream_tracks = {track.get("videoId") for track in playlist.get("tracks", [])}
        local_tracks = set()

        # load from library playlist (which has local paths)
        playlist_file = os.path.join(
            self.library_playlist_path, f"{playlist.get('title')}.m3u8"
        )
        if os.path.exists(playlist_file):
            with open(playlist_file, "r") as f:
                lines = f.readlines()
                for line in lines:
                    if "#EXT" not in line and line.strip():
                        # Extract ID from path: /path/to/ID.mp3 -> ID
                        filename = os.path.basename(line.strip())
                        track_id = os.path.splitext(filename)[0]
                        local_tracks.add(track_id)

        missing_tracks = local_tracks - upstream_tracks

        logger.info(f"Removing {len(missing_tracks)} tracks from playlist {playlist.get('title')}")

        # Only scan directory if there are actually missing tracks to remove
        if missing_tracks:
            with os.scandir(self.library_path) as entries:
                for entry in entries:
                    if entry.is_file() and entry.name.endswith(".mp3"):
                        track_id = os.path.splitext(entry.name)[0]
                        if track_id in missing_tracks:
                            try:
                                os.remove(entry.path)
                                if track_id in self.archive:
                                    self.archive.remove(track_id)
                                logger.info(f"Deleted: {entry.path}")
                            except Exception as e:
                                logger.error(f"Error deleting {entry.path}: {e}")
                    else:
                        pass

        self.update_download_archive()

    def cleanup_removed_playlists(self) -> None:
        """Removes local .m3u8 files that are no longer in the upstream library."""
        logger.info("Cleaning up removed playlists...")
        try:
            upstream_playlists = self.get_playlists()
            upstream_titles = {
                p.get("title") for p in upstream_playlists if p.get("title")
            }

            # Cleanup all playlist directories
            for path in [
                self.fiio_playlist_path,
                self.library_playlist_path,
                self.navidrone_playlist_path,
            ]:
                if not os.path.exists(path):
                    continue
                local_m3u8_files = [f for f in os.listdir(path) if f.endswith(".m3u8")]

                for m3u8_file in local_m3u8_files:
                    playlist_title = os.path.splitext(m3u8_file)[0]
                    if playlist_title not in upstream_titles:
                        try:
                            file_path = os.path.join(path, m3u8_file)
                            os.remove(file_path)
                            logger.info(
                                f"Removed local playlist file (not found upstream): {file_path}"
                            )
                        except Exception as e:
                            logger.error(f"Error removing playlist file {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error during playlist cleanup: {e}")
