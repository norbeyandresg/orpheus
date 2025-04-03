from yaspin import yaspin
from art import text2art
import questionary as qs
from orpheus import Orpheus
from typing import List


def main() -> None:
    print(text2art("Orpheus", "italic"))
    upstream_playlists: List[dict] = []

    with yaspin(text="loading user playlists"):
        o: Orpheus = Orpheus()
        upstream_playlists: List[dict] = o.get_playlists()

    playlist_ids = qs.checkbox(
        "Select the playlists you wanna sync...",
        choices=[
            qs.Choice(title=p.get("title"), value=p.get("playlistId"))
            for p in upstream_playlists
        ],
    ).ask()

    for p_id in playlist_ids:
        playlist = o.get_playlist_details(p_id)
        # playlists.append(playlist)
        o.download_playlist_tracks(playlist)
        o.create_m3u8_playlist_file(playlist.get("title", "default"))

    # o.cleanup_missing_tracks(playlists)


if __name__ == "__main__":
    main()
