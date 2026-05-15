#!/usr/bin/env python3
import sys
from art import text2art
from orpheus import Orpheus

def main():
    print(text2art("Orpheus Sync", "italic"))
    
    print("Initializing Orpheus...")
    try:
        orp = Orpheus()
        print("✔ Initialized")
    except Exception as e:
        print(f"✘ Error initializing Orpheus: {e}")
        sys.exit(1)

    print("Loading all user playlists...")
    try:
        upstream_playlists = orp.get_playlists()
        print(f"✔ Found {len(upstream_playlists)} playlists")
    except Exception as e:
        print(f"✘ Error loading playlists: {e}")
        sys.exit(1)

    if not upstream_playlists:
        print("No playlists found.")
        return

    print("Starting sync...")

    for p in upstream_playlists:
        title = p.get("title", "Unknown")
        p_id = p.get("playlistId")
        
        print(f"\n--- Syncing Playlist: {title} ({p_id}) ---")
        
        try:
            print(f"Fetching details for {title}...")
            playlist = orp.get_playlist_details(p_id)
            print("✔ Details fetched")
            
            orp.download_playlist_tracks(playlist)
            orp.cleanup_missing_tracks_from_playlist(playlist)
            orp.create_m3u8_playlist_file(title)
            
        except Exception as e:
            print(f"✘ Error syncing playlist {title}: {e}")

    print("\n--- Final Cleanup ---")
    try:
        orp.cleanup_removed_playlists()
        print("Done!")
    except Exception as e:
        print(f"✘ Error during final cleanup: {e}")

if __name__ == "__main__":
    main()
