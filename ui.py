from yaspin import yaspin
from art import text2art
import questionary as qs
from orpheus import Orpheus
from typing import List
from logger_setup import setup_logger

# Initialize logger
logger = setup_logger("OrpheusUI")

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


def combine_playlists() -> None:
    local_playlists = orp.get_local_playlists()

    if len(local_playlists) < 2:
        logger.info("Need at least two downloaded playlists to combine")
        print("You need at least two downloaded playlists to combine.")
        return

    source_names = qs.checkbox(
        "Select two or more downloaded playlists to blend...",
        choices=[qs.Choice(title=name, value=name) for name in local_playlists],
    ).ask()

    if not source_names or len(source_names) < 2:
        logger.info("Combining playlists requires selecting at least two playlists")
        print("Please select at least two playlists to combine.")
        return

    name = qs.text("Name for the new blend:").ask()
    if not name:
        logger.info("No name provided for blend; aborting")
        return

    with yaspin(text=f"creating blend '{name}'"):
        orp.combine_local_playlists(name, source_names)

    logger.info(f"Combined {len(source_names)} playlists into blend '{name}'")
    print(f"Created blend '{name}'.")


def update_combined_playlist() -> None:
    blends = orp.load_blends()

    if not blends:
        logger.info("No blends recorded to update")
        print("No blends found. Create one first.")
        return

    name = qs.select(
        "Which blend do you want to update?",
        choices=[qs.Choice(title=n, value=n) for n in blends.keys()],
    ).ask()

    if not name:
        return

    with yaspin(text=f"updating blend '{name}'"):
        orp.update_local_blend(name)

    logger.info(f"Updated blend '{name}'")
    print(f"Updated blend '{name}'.")


def download_playlists(playlist_ids: List[str]) -> None:
    for p_id in playlist_ids:
        playlist = orp.get_playlist_details(p_id)
        logger.info(f"Syncing playlist: {playlist.get('title')}")
        orp.download_playlist_tracks(playlist)
        orp.cleanup_missing_tracks_from_playlist(playlist)
        orp.create_m3u8_playlist_file(playlist.get("title", "default"))


def sync_playlists() -> None:
    playlists_ids = get_user_playlists()
    if playlists_ids:
        logger.info(f"User selected {len(playlists_ids)} playlists to sync")
        download_playlists(playlists_ids)
        orp.cleanup_removed_playlists()
        logger.info("Manual sync completed")


def main() -> None:
    print(text2art("Orpheus", "italic"))

    action = qs.select(
        "What would you like to do?",
        choices=[
            qs.Choice(title="Sync playlists", value="sync"),
            qs.Choice(title="Blend downloaded playlists into a new one", value="combine"),
            qs.Choice(title="Update a blend", value="update"),
        ],
    ).ask()

    if action == "sync":
        sync_playlists()
    elif action == "combine":
        combine_playlists()
    elif action == "update":
        update_combined_playlist()


if __name__ == "__main__":
    main()
