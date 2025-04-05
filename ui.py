from yaspin import yaspin
from art import text2art
import questionary as qs
from orpheus import Orpheus
from typing import List

# Orpheus instance
with yaspin(text="Initializing Orpheus"):
    orp = Orpheus()


def get_user_playlists() -> List[str] | None:
    upstream_playlists = []

    with yaspin(text="loading user playlists"):
        upstream_playlists = orp.get_playlists()

    playlist_ids = qs.checkbox(
        "Select the playlists you wanna sync...",
        choices=[
            qs.Choice(title=p.get("title"), value=p.get("playlistId"))
            for p in upstream_playlists
        ],
    ).ask()

    return playlist_ids


def download_playlists(playlist_ids: List[str]) -> None:
    for p_id in playlist_ids:
        playlist = orp.get_playlist_details(p_id)
        # playlists.append(playlist)
        orp.download_playlist_tracks(playlist)
        orp.cleanup_missing_tracks_from_playlist(playlist)
        orp.create_m3u8_playlist_file(playlist.get("title", "default"))

    # o.cleanup_missing_tracks(playlists)


def main() -> None:
    print(text2art("Orpheus", "italic"))
    playlists_ids = get_user_playlists()
    if playlists_ids:
        download_playlists(playlists_ids)


if __name__ == "__main__":
    main()
