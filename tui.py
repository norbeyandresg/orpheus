"""Orpheus TUI — a fast, keyboard-driven main-menu dashboard.

Rich handles rendering; a raw-key loop (readchar) handles input. No mouse, no
async, no widget framework — vim-style navigation over the existing Orpheus
logic.

Run with:  python tui.py

Keys:
  j / k or ↓ / ↑   move          g / G   top / bottom
  ↵                run action    r       refresh library
  s S b u x        shortcuts     q       quit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import readchar
from art import text2art
from rich.align import Align
from rich.box import HEAVY, ROUNDED
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from logger_setup import setup_logger
from orpheus import Orpheus

logger = setup_logger("OrpheusTUI")

# --------------------------------------------------------------------------- #
# Palette  (a calm "hacker" green/cyan scheme)
# --------------------------------------------------------------------------- #
ACCENT = "bright_cyan"
ACCENT2 = "bright_magenta"
OK = "bright_green"
STAR = "yellow"
DIM = "grey42"
IDLE_BORDER = "grey37"

# gradient endpoints (green → cyan) for the logo/mascot
GREEN_RGB = (74, 222, 128)
CYAN_RGB = (34, 211, 238)

K = readchar.key


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def gradient(text: str, c1=GREEN_RGB, c2=CYAN_RGB) -> Text:
    """Color each character left→right, interpolating between two RGB colors."""
    lines = text.split("\n")
    width = max((len(line) for line in lines), default=1)
    out = Text()
    for li, line in enumerate(lines):
        for x, ch in enumerate(line):
            f = x / max(1, width - 1)
            r, g, b = _lerp(c1[0], c2[0], f), _lerp(c1[1], c2[1], f), _lerp(c1[2], c2[2], f)
            out.append(ch, style=f"#{r:02x}{g:02x}{b:02x}")
        if li != len(lines) - 1:
            out.append("\n")
    return out


# Startup mascot (shown on the splash screen)
MASCOT = r"""
             ,,,,,,,,
           ,|||````||||
     ,,,,|||||       ||,
  ,||||```````       `||
,|||`                 |||,
||`     ....,          `|||
||     ::::::::          |||,
||     :::::::'     ||    ``|||,
||,     :::::'               `|||
`||,                           |||
 `|||,       ||          ||    ,||
   `||                        |||`
    ||                   ,,,||||
    ||              ,||||||```
   ,||         ,,|||||`
  ,||`   ||   |||`
 |||`         ||
,||           ||
||`           ||
|||,         |||
 `|||,,    ,|||
   ``||||||||`
"""


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #


@dataclass
class SyncProgress:
    active: bool = False
    playlists_done: int = 0
    playlists_total: int = 0
    current: str = ""
    tracks_done: int = 0
    tracks_total: int = 0


@dataclass
class AppState:
    entries: List[dict] = field(default_factory=list)  # {name, is_blend, tracks}
    menu_sel: int = 0
    status: str = "Ready."
    progress: SyncProgress = field(default_factory=SyncProgress)
    overlay: Optional[object] = None  # a renderable shown as a modal
    running: bool = True


# --------------------------------------------------------------------------- #
# Rendering  (pure: state -> renderable)
# --------------------------------------------------------------------------- #


def render_header() -> Panel:
    logo = gradient(text2art("Orpheus", font="small").rstrip("\n"))
    body = Group(logo, Text("youtube music · sync & blend", style=DIM))
    return Panel(body, box=ROUNDED, border_style=ACCENT, padding=(0, 2))


def render_splash() -> Group:
    """Full mascot + logo banner shown once on startup."""
    mascot = gradient(MASCOT.strip("\n"))
    logo = gradient(text2art("Orpheus", font="slant").rstrip("\n"))
    return Group(
        Text("\n\n"),  # top padding
        Align.center(mascot),
        Text(""),
        Align.center(logo),
        Align.center(Text("▶ sync & blend your library", style=f"bold {OK}")),
        Text(""),
        Align.center(Text("press any key to start", style=DIM)),
    )


def render_menu(state: AppState) -> Panel:
    grid = Table.grid(padding=(0, 0))
    grid.add_column()
    for i, item in enumerate(MENU):
        selected = i == state.menu_sel
        if selected:
            line = Text(
                f"  {item['key']}   {item['label']:<14}   {item['desc']}",
                style=f"bold black on {ACCENT}",
            )
        else:
            line = Text()
            line.append(f"  {item['key']}   ", style=f"bold {ACCENT}")
            line.append(f"{item['label']:<14}   ", style="bold")
            line.append(item["desc"], style=DIM)
        grid.add_row(line)
        if i != len(MENU) - 1:
            grid.add_row("")

    def _plural(n: int, word: str) -> str:
        return f"{n} {word}" + ("" if n == 1 else "s")

    n_pl = sum(1 for e in state.entries if not e["is_blend"])
    n_bl = sum(1 for e in state.entries if e["is_blend"])
    summary = Text(
        f"library · {_plural(n_pl, 'playlist')} · {_plural(n_bl, 'blend')}",
        style=DIM,
        justify="center",
    )
    block = Group(Align.center(grid), Text(""), summary)
    return Panel(
        Align.center(block, vertical="middle"),
        title="[bold]Main Menu[/]",
        title_align="left",
        border_style=ACCENT,
        box=ROUNDED,
        padding=(1, 2),
    )


def render_status(state: AppState) -> Panel:
    p = state.progress
    if p.active:
        grid = Table.grid(padding=(0, 1), expand=True)
        grid.add_column(width=18)
        grid.add_column(ratio=1)
        grid.add_column(justify="right", width=16, style=DIM)

        overall = ProgressBar(
            total=max(1, p.playlists_total),
            completed=p.playlists_done,
            complete_style=ACCENT,
            finished_style=OK,
        )
        grid.add_row(
            Text("Sync", style=f"bold {ACCENT}"),
            overall,
            f"{p.playlists_done}/{p.playlists_total} playlists",
        )

        track = ProgressBar(
            total=max(1, p.tracks_total),
            completed=p.tracks_done,
            complete_style=ACCENT2,
            finished_style=OK,
        )
        label = Text(f"  └ {p.current}", style=DIM, no_wrap=True, overflow="ellipsis")
        grid.add_row(label, track, f"{p.tracks_done}/{p.tracks_total} tracks")
        return Panel(
            grid, box=ROUNDED, border_style=ACCENT2,
            title="[bold]Syncing[/]", title_align="left",
        )

    return Panel(
        Text(state.status, style=DIM), box=ROUNDED,
        border_style=IDLE_BORDER, title="Status", title_align="left",
    )


def render_footer() -> Panel:
    keys: List[Tuple[str, str]] = [
        ("j/k", "move"), ("g/G", "top/btm"), ("↵", "select"),
        ("r", "refresh"), ("q", "quit"),
    ]
    text = Text()
    for i, (k, label) in enumerate(keys):
        if i:
            text.append("   ")
        text.append(f" {k} ", style=f"bold black on {ACCENT}")
        text.append(f" {label}", style=DIM)
    return Panel(text, box=ROUNDED, border_style=IDLE_BORDER, padding=0)


def build_layout(state: AppState, width: int, height: int) -> Layout:
    status_size = 4
    root = Layout()
    root.split_column(
        Layout(render_header(), name="header", size=6),
        Layout(name="body", ratio=1),
        Layout(render_status(state), name="status", size=status_size),
        Layout(render_footer(), name="footer", size=3),
    )
    if state.overlay is not None:
        root["body"].update(Align.center(state.overlay, vertical="middle"))
    else:
        root["body"].update(render_menu(state))
    return root


# --------------------------------------------------------------------------- #
# Overlays  (modal selection / text input, keyboard-driven)
# --------------------------------------------------------------------------- #


class _Loop:
    """Bundles the Live display + console + state so overlays can redraw."""

    def __init__(self, live: Live, console: Console, state: AppState):
        self.live = live
        self.console = console
        self.state = state

    def refresh(self) -> None:
        size = self.console.size
        self.live.update(build_layout(self.state, size.width, size.height), refresh=True)

    def _show_overlay(self, renderable) -> None:
        self.state.overlay = renderable
        self.refresh()

    def _clear_overlay(self) -> None:
        self.state.overlay = None
        self.refresh()

    def select_one(self, title: str, options: List[Tuple[str, object]]) -> Optional[object]:
        if not options:
            return None
        idx = 0
        while True:
            self._show_overlay(_menu_panel(title, options, idx, hint="↵ select · esc cancel"))
            key = readchar.readkey()
            if key in (K.DOWN, "j"):
                idx = (idx + 1) % len(options)
            elif key in (K.UP, "k"):
                idx = (idx - 1) % len(options)
            elif key in (K.ENTER, "\r", "\n"):
                self._clear_overlay()
                return options[idx][1]
            elif key in (K.ESC, "q", "\x03"):
                self._clear_overlay()
                return None

    def select_many(self, title: str, options: List[Tuple[str, object]]) -> Optional[List[object]]:
        if not options:
            return None
        idx = 0
        chosen: set[int] = set()
        while True:
            self._show_overlay(
                _menu_panel(title, options, idx, chosen=chosen,
                            hint="space toggle · ↵ confirm · esc cancel")
            )
            key = readchar.readkey()
            if key in (K.DOWN, "j"):
                idx = (idx + 1) % len(options)
            elif key in (K.UP, "k"):
                idx = (idx - 1) % len(options)
            elif key in (K.SPACE, " "):
                chosen.symmetric_difference_update({idx})
            elif key in (K.ENTER, "\r", "\n"):
                self._clear_overlay()
                return [options[i][1] for i in sorted(chosen)]
            elif key in (K.ESC, "q", "\x03"):
                self._clear_overlay()
                return None

    def text_input(self, title: str) -> Optional[str]:
        buf = ""
        while True:
            field = Text()
            field.append(buf or " ", style="white on grey23")
            field.append("▏", style=ACCENT)
            panel = Panel(
                Group(Text(title, style=f"bold {ACCENT}"), Text(""), field),
                title="Input", title_align="left", border_style=ACCENT,
                box=HEAVY, width=60, padding=(1, 2),
                subtitle="↵ confirm · esc cancel", subtitle_align="right",
            )
            self._show_overlay(panel)
            key = readchar.readkey()
            if key in (K.ENTER, "\r", "\n"):
                self._clear_overlay()
                return buf.strip()
            elif key in (K.ESC, "\x03"):
                self._clear_overlay()
                return None
            elif key in (K.BACKSPACE, "\x7f", "\b"):
                buf = buf[:-1]
            elif len(key) == 1 and key.isprintable():
                buf += key

    def confirm(self, question: str) -> bool:
        panel = Panel(
            Text(question, style="bold"),
            title="Confirm", title_align="left", border_style=STAR,
            box=HEAVY, width=60, padding=(1, 2),
            subtitle="y confirm · n / esc cancel", subtitle_align="right",
        )
        self._show_overlay(panel)
        while True:
            key = readchar.readkey()
            if key in ("y", "Y"):
                self._clear_overlay()
                return True
            if key in ("n", "N", K.ESC, "\x03"):
                self._clear_overlay()
                return False


def _menu_panel(title, options, idx, chosen=None, hint="") -> Panel:
    table = Table.grid(padding=(0, 1), expand=True)
    table.add_column()
    for i, (label, _value) in enumerate(options):
        mark = ""
        if chosen is not None:
            mark = "[x] " if i in chosen else "[ ] "
        line = Text(f"{mark}{label}")
        if i == idx:
            line.stylize(f"bold black on {ACCENT}")
        table.add_row(line)
    return Panel(
        table, title=f"[bold {ACCENT}]{title}[/]", title_align="left",
        border_style=ACCENT, box=HEAVY, width=60, padding=(1, 2),
        subtitle=f"[{DIM}]{hint}[/]", subtitle_align="right",
    )


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #


def load_entries(orp: Orpheus) -> List[dict]:
    blends = orp.load_blends()
    entries: List[dict] = []
    for name in orp.get_local_playlists():
        entries.append(
            {"name": name, "is_blend": False, "tracks": orp._parse_m3u8_tracks(name)}
        )
    for name in blends:
        entries.append(
            {"name": name, "is_blend": True, "tracks": orp._parse_m3u8_tracks(name)}
        )
    return entries


def _refresh_entries(loop: _Loop, orp: Orpheus) -> None:
    loop.state.entries = load_entries(orp)
    loop.refresh()


def _entry_options(entries: List[dict]) -> List[Tuple[str, str]]:
    return [
        (("★ " if e["is_blend"] else "• ") + e["name"], e["name"]) for e in entries
    ]


def _run_sync(loop: _Loop, orp: Orpheus, playlist_ids: List[str]) -> None:
    p = loop.state.progress
    p.active = True
    p.playlists_total = len(playlist_ids)
    p.playlists_done = 0
    try:
        for pid in playlist_ids:
            playlist = orp.get_playlist_details(pid)
            title = playlist.get("title", "default")
            p.current = title
            p.tracks_total = len(playlist.get("tracks", []))
            p.tracks_done = 0
            loop.refresh()

            def on_progress(done: int, total: int) -> None:
                p.tracks_done, p.tracks_total = done, total
                loop.refresh()

            orp.download_playlist_tracks(playlist, on_progress=on_progress, quiet=True)
            orp.cleanup_missing_tracks_from_playlist(playlist)
            orp.create_m3u8_playlist_file(title)
            p.playlists_done += 1
            loop.refresh()
        orp.cleanup_removed_playlists()
        loop.state.status = f"Synced {len(playlist_ids)} playlist(s)."
    except KeyboardInterrupt:
        loop.state.status = "Sync cancelled."
    finally:
        p.active = False
        _refresh_entries(loop, orp)


def action_sync(loop: _Loop, orp: Orpheus) -> None:
    loop.state.status = "Loading upstream playlists…"
    loop.refresh()
    playlists = orp.get_playlists()
    options = [(p.get("title", "?"), p.get("playlistId")) for p in playlists]
    selected = loop.select_many("Sync — pick playlists", options)
    if selected:
        _run_sync(loop, orp, selected)


def action_full_sync(loop: _Loop, orp: Orpheus) -> None:
    if not loop.confirm("Sync ALL upstream playlists?"):
        return
    loop.state.status = "Loading upstream playlists…"
    loop.refresh()
    ids = [p.get("playlistId") for p in orp.get_playlists()]
    _run_sync(loop, orp, ids)


def action_blend(loop: _Loop, orp: Orpheus) -> None:
    local = orp.get_local_playlists()
    if len(local) < 2:
        loop.state.status = "Need at least two downloaded playlists to blend."
        loop.refresh()
        return
    name = loop.text_input("Name for the new blend:")
    if not name:
        return
    sources = loop.select_many("Blend — pick 2+ playlists", [(n, n) for n in local])
    if not sources or len(sources) < 2:
        loop.state.status = "Blend needs at least two playlists."
        loop.refresh()
        return
    orp.combine_local_playlists(name, sources)
    loop.state.status = f"Created blend '{name}'."
    _refresh_entries(loop, orp)


def action_update(loop: _Loop, orp: Orpheus) -> None:
    blends = orp.load_blends()
    if not blends:
        loop.state.status = "No blends to update."
        loop.refresh()
        return
    name = loop.select_one("Update — pick a blend", [(n, n) for n in blends])
    if not name:
        return
    orp.update_local_blend(name)
    loop.state.status = f"Updated blend '{name}'."
    _refresh_entries(loop, orp)


def action_remove(loop: _Loop, orp: Orpheus) -> None:
    entries = loop.state.entries
    if not entries:
        loop.state.status = "Nothing to remove."
        loop.refresh()
        return
    name = loop.select_one("Remove — pick a playlist/blend", _entry_options(entries))
    if not name:
        return
    if loop.confirm(f"Remove '{name}' (deletes its .m3u8 files)?"):
        orp.remove_playlist(name)
        loop.state.status = f"Removed '{name}'."
        _refresh_entries(loop, orp)


# --------------------------------------------------------------------------- #
# Menu + event loop
# --------------------------------------------------------------------------- #

MENU = [
    {"key": "s", "label": "Sync playlists", "desc": "pick which playlists to download", "action": action_sync},
    {"key": "S", "label": "Full sync", "desc": "download all upstream playlists", "action": action_full_sync},
    {"key": "b", "label": "Create blend", "desc": "mix downloaded playlists into one", "action": action_blend},
    {"key": "u", "label": "Update blend", "desc": "regenerate a blend from its sources", "action": action_update},
    {"key": "x", "label": "Remove", "desc": "delete a playlist or blend locally", "action": action_remove},
    {"key": "q", "label": "Quit", "desc": "exit Orpheus", "action": None},
]


def run_menu_item(index: int, loop: _Loop, orp: Orpheus) -> None:
    item = MENU[index]
    if item["action"] is None:
        loop.state.running = False
    else:
        item["action"](loop, orp)


def handle_key(key: str, loop: _Loop, orp: Orpheus) -> None:
    state = loop.state
    if key in ("q", "\x03"):
        state.running = False
    elif key in (K.DOWN, "j"):
        state.menu_sel = (state.menu_sel + 1) % len(MENU)
    elif key in (K.UP, "k"):
        state.menu_sel = (state.menu_sel - 1) % len(MENU)
    elif key == "g":
        state.menu_sel = 0
    elif key == "G":
        state.menu_sel = len(MENU) - 1
    elif key in (K.ENTER, "\r", "\n"):
        run_menu_item(state.menu_sel, loop, orp)
    elif key == "r":
        _refresh_entries(loop, orp)
        state.status = "Refreshed."
    else:
        for i, item in enumerate(MENU):
            if key == item["key"]:
                state.menu_sel = i
                run_menu_item(i, loop, orp)
                break


def run(orp: Orpheus) -> None:
    console = Console()
    state = AppState(entries=load_entries(orp))
    with Live(console=console, screen=True, auto_refresh=False,
              redirect_stdout=False, redirect_stderr=False) as live:
        # splash screen — any key (except q) enters the dashboard
        live.update(Align.center(render_splash(), vertical="middle"), refresh=True)
        try:
            if readchar.readkey() in ("q", "\x03"):
                return
        except KeyboardInterrupt:
            return

        loop = _Loop(live, console, state)
        loop.refresh()
        while state.running:
            try:
                key = readchar.readkey()
            except KeyboardInterrupt:
                break
            handle_key(key, loop, orp)
            if state.running:
                loop.refresh()


def preview_banner() -> None:
    """Print the startup banner to the terminal (no app, no auth) so you can
    see it in full color:  python -c 'import tui; tui.preview_banner()'
    """
    Console().print(render_splash())


def main() -> None:
    orp = Orpheus()
    run(orp)


if __name__ == "__main__":
    main()
