#!/usr/bin/env python3
import sys
from art import text2art
from orpheus import Orpheus
from logger_setup import setup_logger

# Initialize logger
logger = setup_logger("OrpheusSync")

def main():
    # We still print the ASCII art to stdout for manual runs
    print(text2art("Orpheus Sync", "italic"))
    
    logger.info("Starting Orpheus Sync...")
    
    try:
        orp = Orpheus()
        logger.info("Orpheus initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing Orpheus: {e}")
        sys.exit(1)

    try:
        upstream_playlists = orp.get_playlists()
        logger.info(f"Found {len(upstream_playlists)} playlists in library")
    except Exception as e:
        logger.error(f"Error loading playlists: {e}")
        sys.exit(1)

    if not upstream_playlists:
        logger.warning("No playlists found in your library.")
        return

    for p in upstream_playlists:
        title = p.get("title", "Unknown")
        p_id = p.get("playlistId")
        
        logger.info(f"--- Syncing Playlist: {title} ({p_id}) ---")
        
        try:
            logger.info(f"Fetching details for {title}...")
            playlist = orp.get_playlist_details(p_id)
            
            orp.download_playlist_tracks(playlist)
            orp.cleanup_missing_tracks_from_playlist(playlist)
            orp.create_m3u8_playlist_file(title)
            logger.info(f"Successfully synced playlist: {title}")
            
        except Exception as e:
            logger.error(f"Error syncing playlist {title}: {e}")

    # Regenerate custom blends now that their source playlists are up to date
    blends = orp.load_blends()
    if blends:
        logger.info(f"Updating {len(blends)} custom blend(s)...")
        for name in blends:
            try:
                orp.update_local_blend(name)
                logger.info(f"Updated blend: {name}")
            except Exception as e:
                logger.error(f"Error updating blend {name}: {e}")

    logger.info("Performing final cleanup...")
    try:
        orp.cleanup_removed_playlists()
        logger.info("Sync process completed successfully!")
    except Exception as e:
        logger.error(f"Error during final cleanup: {e}")

if __name__ == "__main__":
    main()
