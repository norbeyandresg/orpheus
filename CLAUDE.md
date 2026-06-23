# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Orpheus syncs a YouTube Music library to local audio files and `.m3u8` playlists. It pulls playlists from YT Music, downloads tracks with `yt-dlp`, tags them via `beets`, writes playlist files for three different players, and can mix downloaded playlists into "blends." A recently added feature pulls weekly discovery playlists from ListenBrainz.

## Environment & commands

- **Always use the project venv:** `~/.virtualenvs/orph` (not `/tmp` venvs, not system Python). Run code as `~/.virtualenvs/orph/bin/python <script>`.
- Install deps: `~/.virtualenvs/orph/bin/pip install -r requirements.txt`
- **Three entry points, same `Orpheus` core:**
  - `python tui.py` — the primary interface: full-screen keyboard-driven Rich dashboard. Use this to verify UI changes.
  - `python sync.py` — non-interactive: syncs *all* upstream playlists then regenerates all blends. This is the cron path.
  - `python ui.py` — legacy `questionary` menu. Kept working but not where new features go.
- Syntax check before claiming done: `~/.virtualenvs/orph/bin/python -m py_compile orpheus.py tui.py`
- **No test suite exists.** Don't claim tests pass. Verify by running the relevant entry point or by exercising a method directly (see below).

There is no linter config beyond a stray `.ruff_cache`; don't assume ruff is wired into a workflow.

## Architecture

**`orpheus.py` is the entire backend.** The `Orpheus` class owns the YT Music client, all download/sync/blend/cleanup logic, and external API calls. `tui.py`, `sync.py`, and `ui.py` are thin presentation layers — none of them should contain business logic. When adding a feature, the data-fetching/mutation method goes on `Orpheus`; the entry points only call it and render results. Methods on `Orpheus` are deliberately stateless w.r.t. `self` where possible (e.g. `get_listenbrainz_weekly_discovery` touches no instance state), which makes them callable in isolation for testing:
```
~/.virtualenvs/orph/bin/python -c "from orpheus import Orpheus; print(Orpheus.get_listenbrainz_weekly_discovery(Orpheus.__new__(Orpheus)))"
```
`Orpheus.__init__` constructs a live `YTMusic("browser.json")` client and makes playlist dirs, so methods needing auth require a real instance.

**The sync pipeline** (see `sync.py` for the canonical sequence per playlist):
`get_playlist_details` → `download_playlist_tracks` → `cleanup_missing_tracks_from_playlist` → `create_m3u8_playlist_file`. After all playlists, blends are regenerated via `update_local_blend`, then `cleanup_removed_playlists` deletes anything no longer upstream (but never deletes a registered blend).

**The three-variant `.m3u8` model is central and easy to get wrong.** Every playlist is written to *three* directories, identical except for the audio path prefix each line points at — because the same library is consumed by three players on different mounts:
- `fiio` → prefix `M3U8_BASE_PATH` (e.g. an SD card path like `/storage/external_sd/Music`)
- `library` → prefix `LIBRARY_PATH` (local download dir)
- `navidrone` → its own prefix
Files are named `<videoId>.mp3`; the YouTube videoId is the stable identity for a track everywhere (download archive, m3u8 lines, de-dup). Any code that writes or edits playlists must keep all three variants in sync — `create_m3u8_playlist_file`, `combine_local_playlists`, and `remove_playlist` all loop over the three paths for this reason.

**Blends** are saved playlists composed from already-downloaded local playlists. The registry is `blends.json` (`{name: {"sources": [...]}}`). `combine_local_playlists` parses the source `.m3u8` files, merges + de-dups by videoId (first-seen order), and writes the three variants. Blends are *derived* — they're never downloaded directly and are regenerated from sources on every sync. `cleanup_removed_playlists` checks the registry so a blend survives even when it has no upstream YT Music equivalent.

**Download/tagging** runs through `yt-dlp` (`get_ydl_opts` + `download_playlist_tracks`), with `BeetsPostProcessor` (in `postprocessors.py`) shelling out to `beets` for metadata after each download. `download_archive.txt` (in `LIBRARY_PATH`) lets yt-dlp skip already-downloaded tracks.

**Two distinct "remove" operations** (don't conflate them): `remove_playlist` deletes only the `.m3u8` files (+ blend registry entry), leaving the `.mp3` audio on disk; `remove_playlist_downloads` deletes the audio *and* the `.m3u8` files, but first protects any videoId still referenced by another local playlist/blend so it won't break them. Because videoIds are shared across playlists/blends, never delete an audio file without checking the other `.m3u8` files first.

**Weekly discovery → Discovery playlist.** `get_listenbrainz_weekly_discovery` hits the public API at `https://api.listenbrainz.org/1`: list `…/user/<user>/playlists/createdfor`, pick the newest playlist whose `source_patch == "weekly-exploration"`, then fetch `…/playlist/<mbid>` for tracks (the listing endpoint omits them). It returns title/week/mbid/tracks plus `is_current`/`current_week` (computed against this week's Monday, since the fetched playlist can lag if ListenBrainz hasn't regenerated yet). Username defaults to `tom-bombadil`, override with `LISTENBRAINZ_USER`.

The TUI "Sync weekly discovery" action then offers to **overwrite a YouTube Music playlist** with this list: `resolve_tracks_to_ytmusic` searches each (artist, title) → a videoId (lossy; misses are logged and skipped), and `overwrite_ytmusic_playlist` removes *all* existing items from the target playlist and adds the resolved ones. The target defaults to a playlist named `discovery` (override with `DISCOVERY_PLAYLIST_NAME`). This is the only write-back to YouTube Music in the codebase — everything else is read + local download.

**Sync ignore list.** `Orpheus.sync_ignore` (the discovery playlist + "episodes for later") is excluded from full/automated sync — `is_ignored_for_sync(title)` is checked in `sync.py` and `action_full_sync`. The manual "Sync playlists" picker is *not* filtered, so those playlists can still be downloaded deliberately.

## TUI conventions (`tui.py`)

- Rendering is pure `state -> renderable`; a raw-key loop (`readchar`) drives input. No async, no widget framework.
- A menu item is a dict in the `MENU` list (`{key, label, desc, action}`); `handle_key` dispatches single-char keys to it. To add a feature: write an `action_*(loop, orp)` function, then add one `MENU` entry. That's the whole wiring.
- Actions interact with the user through `_Loop` helpers: `select_one`, `select_many`, `text_input`, `confirm`, and `show_list` (read-only scrollable modal). Reuse these rather than reading keys directly. Catch exceptions inside actions and set `loop.state.status` — an uncaught exception corrupts the full-screen display.
- Logging is redirected: console handlers are detached so download output can't scramble the UI; logs render in the in-panel Logs view and still go to `orpheus.log`. Don't `print()` from backend code paths reachable by the TUI.

## Conventions

- **Commit straight to `main`. Never create a branch in this repo.**
- Secrets/auth live as untracked files in the repo root: `browser.json` (YT Music session), `cookies.txt` (yt-dlp bot-detection bypass), `oauth.json`, `g-creds.json`. Treat them as present-but-private; don't read or echo their contents.
- Config is via `.env` (loaded by `python-dotenv`): `YTM_CLIENT_ID/SECRET`, `LIBRARY_PATH`, `M3U8_BASE_PATH`, the three `*_PLAYLIST_PATH` vars, `BEETS_PATH`, `BLENDS_PATH`, `LISTENBRAINZ_USER`.
