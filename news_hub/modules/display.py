"""Display module - simple GUI for viewing summarized news.

This module renders the Flet-based desktop UI for Snewzy: article cards
grouped by priority, a settings overlay, and a "Refresh News" control.
Refreshing (whether user-triggered or on the periodic auto-refresh timer)
shells out to `python -m news_hub.main --update`, which can take several
minutes. To keep the GUI responsive, that subprocess call always runs on a
background thread; a module-level lock prevents overlapping runs, and a
module-level `threading.Timer` drives the periodic auto-refresh, resetting
itself on every manual or automatic refresh so the two mechanisms never
double-fire.
"""

import subprocess
import sys
import threading
from typing import List, Optional, Tuple

import flet as ft

from .config_loader import load_config
from .database import get_articles_by_priority, init_database
from .settings_dialog import create_settings_dialog

# ---------------------------------------------------------------------------
# Module-level refresh coordination state.
#
# This is intentionally global/singleton state: it must be shared across
# every rebuild of main_page() (which recreates all local UI controls) so
# that "is a refresh already running?" and "when does the next automatic
# refresh fire?" stay consistent for the lifetime of the running app.
# ---------------------------------------------------------------------------
_refresh_lock: threading.Lock = threading.Lock()
_timer_lock: threading.Lock = threading.Lock()
_auto_refresh_timer: Optional[threading.Timer] = None


def create_article_card(article: Tuple, on_read: callable = None) -> ft.Card:
    """Create a UI card for a single article."""
    article_id = article[0]
    title = article[1]
    source = article[2]
    url = article[3]
    published = article[4]
    summary = article[6] or "No summary available."
    bullets = article[7] or ""
    priority = article[8]
    status = article[9]
    
    priority_colors = {
        1: ft.Colors.RED_100,
        2: ft.Colors.ORANGE_100
    }
    
    bg_color = priority_colors.get(priority, ft.Colors.GREY_100)
    def handle_read_click(e):
        if on_read:
            on_read(article_id)

    read_button = ft.ElevatedButton(
        "Mark as Read",
        icon=ft.Icons.CHECK_CIRCLE,
        on_click=handle_read_click,
        bgcolor=ft.Colors.GREEN_400,
        color=ft.Colors.WHITE
    )if on_read else ft.Container()
    
    return ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(f"P{priority}", weight=ft.FontWeight.BOLD, size=16),
                    ft.Text(source, italic=True, size=12),
                    ft.Text(published, size=12, color=ft.Colors.GREY_600)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                ft.Text(title, weight=ft.FontWeight.BOLD, size=18),
                
                ft.Container(
                    content=ft.Text(summary, size=14),
                    padding=10
                ),
                
                ft.Container(
                    content=ft.Text(bullets, size=13, 
                                  color=ft.Colors.BLUE_GREY_700),
                    visible=bool(bullets)
                ),
                
                ft.Row([
                    ft.ElevatedButton(
                        "Open Article",
                        url=url
                    ),
                    read_button
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ]),
            padding=15,
            bgcolor=bg_color,
            border_radius=10
        ),
        elevation=2
    )


def create_priority_section(page: ft.Page, priority: int, articles: List[Tuple],
                            on_article_read: callable) -> ft.Column:
    """Create a section for a priority level with read functionality"""
    priority_names = {1: "Breaking News", 2: "General News"}
    name = priority_names.get(priority, f"Priority {priority}")

    def refresh_section():
        """Reload this section after article marked read."""
        page.clean()
        main_page(page)

    def handle_read(article_id):
        """Mark article as read and refresh."""
        from .database import make_article_as_read
        make_article_as_read(article_id)
        refresh_section()
    cards = [
        create_article_card(article, on_read=handle_read)
        for article in articles
    ]
    return ft.Column([
        ft.Row([
            ft.Text(f"{name}) ({len(articles)} articles)",
                    size=20, weight=ft.FontWeight.BOLD),
            ft.Text("Max 5 shown", size=12, color=ft.Colors.GREY_500, italic=True)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Column(cards, spacing=10, scroll=ft.ScrollMode.AUTO) if cards else
        ft.Text("No articles", italic=True, color=ft.Colors.GREY_500)
    ], spacing=10)


def _cancel_auto_refresh_timer() -> None:
    """Cancel any pending automatic-refresh timer, if one is scheduled.

    Thread-safe: guarded by `_timer_lock` so a timer firing on the
    background thread can't race with a manual click cancelling/rescheduling
    it. Safe to call even when no timer is currently pending (a no-op).

    Returns:
        None
    """
    global _auto_refresh_timer
    with _timer_lock:
        if _auto_refresh_timer is not None:
            _auto_refresh_timer.cancel()
            _auto_refresh_timer = None


def _schedule_auto_refresh(page: ft.Page, status_text: ft.Text, interval_hours: float) -> None:
    """(Re)start the periodic auto-refresh countdown.

    Cancels any existing pending timer first, so this both "schedules the
    next automatic refresh" and "resets the 6-hour countdown" in one call -
    used both at page load and after every completed manual/automatic
    refresh.

    Args:
        page: The Flet page the eventual refresh should act on.
        status_text: The status Text control the eventual refresh should
            update to show progress.
        interval_hours: Hours to wait before the next automatic refresh
            (normally config.settings.scan_interval_hours).

    Returns:
        None
    """
    global _auto_refresh_timer
    _cancel_auto_refresh_timer()
    interval_seconds = max(interval_hours, 0.0) * 3600
    timer = threading.Timer(
        interval_seconds, _run_refresh, args=(page, status_text, interval_hours, False)
    )
    timer.daemon = True
    with _timer_lock:
        _auto_refresh_timer = timer
    timer.start()


def _update_status(status_text: ft.Text, message: str, color: str) -> None:
    """Update a status Text control's value/color and push just that change.

    Uses the control's own `.update()` rather than `page.update()` so other
    parts of the UI stay fully interactive while a background refresh runs.

    Args:
        status_text: The Text control to update.
        message: New text to display.
        color: Flet color for the text.

    Returns:
        None
    """
    status_text.value = message
    status_text.color = color
    status_text.update()


def _run_refresh(
    page: ft.Page,
    status_text: ft.Text,
    interval_hours: float,
    manual: bool,
    refresh_button: Optional[ft.ElevatedButton] = None,
) -> None:
    """Run the update subprocess and reflect progress, off the UI thread.

    Meant to be invoked as the target of a `threading.Thread` (manual click)
    or `threading.Timer` (automatic trigger) - never called directly on the
    UI thread, since `subprocess.run` here blocks for up to 10 minutes.

    Overlap protection: attempts a non-blocking acquire of the module-level
    `_refresh_lock`; if a refresh (manual or automatic) is already running,
    this call is ignored instead of starting a second, concurrent run.

    Args:
        page: The Flet page to update/rebuild on completion.
        status_text: Status Text control to update with progress/results.
        interval_hours: Hours until the next automatic refresh; used to
            reschedule the auto-refresh timer once this run finishes.
        manual: True if this run was triggered by the "Refresh News"
            button (used only to decide whether to surface a "busy"
            message when a run is already in progress).
        refresh_button: Optional button control to disable/re-enable while
            this refresh is in progress, so the user gets visual feedback
            that a run is active without blocking other interactions.

    Returns:
        None
    """
    acquired = _refresh_lock.acquire(blocking=False)
    if not acquired:
        if manual:
            _update_status(status_text, "Refresh already in progress...", ft.Colors.ORANGE_500)
        return

    # A refresh is starting now (manual or automatic) - reset the periodic
    # countdown immediately so the timer can't also fire shortly after.
    _cancel_auto_refresh_timer()

    rebuilt = False
    if refresh_button is not None:
        refresh_button.disabled = True
        refresh_button.update()

    try:
        _update_status(status_text, "Updating... (running in background)", ft.Colors.ORANGE_500)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "news_hub.main", "--update"],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes
            )
            if result.returncode == 0:
                _update_status(status_text, "Update complete. Refreshing...", ft.Colors.GREEN_500)
                rebuilt = True
                page.clean()
                main_page(page)  # rebuild schedules its own fresh auto-refresh timer
            else:
                error_msg = result.stderr[-200:] if result.stderr else "Unknown error"
                _update_status(status_text, f"Update failed: {error_msg}", ft.Colors.RED_400)
        except subprocess.TimeoutExpired:
            _update_status(status_text, "Update timed out (10 min)", ft.Colors.RED_400)
        except OSError as ex:
            _update_status(status_text, f"Error: {ex}", ft.Colors.RED_400)
    finally:
        _refresh_lock.release()
        if refresh_button is not None and not rebuilt:
            refresh_button.disabled = False
            refresh_button.update()
        if not rebuilt:
            # No rebuild happened (failure/timeout/busy path never reaches
            # here) - reschedule the next automatic refresh ourselves,
            # since main_page() won't be re-run to do it for us.
            _schedule_auto_refresh(page, status_text, interval_hours)


def main_page(page: ft.Page):
    """Main application page."""
    page.title = "Snewzy - Personal News Hub"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20

    try:
        app_config = load_config()
        interval_hours = app_config.settings.scan_interval_hours
    except (FileNotFoundError, ValueError) as ex:
        print(f"Could not load config for scan interval, defaulting to 6h: {ex}")
        interval_hours = 6

    status_text = ft.Text("", size=13)

    # ========== BUTTON FUNCTIONS ==========
    
    def open_settings(e):
        """Open settings overlay."""
        import subprocess
        import os
        
        config_path = os.path.expanduser("~/workspace/projects/snewzy/config.json")
        
        def close_overlay(e):
            page.remove(overlay_container)
            page.update()
        
        def open_file(e):
            try:
                subprocess.Popen(["xdg-open", config_path])
            except OSError as ex:
                print(f"Could not open file: {ex}")
        
        overlay_container = ft.Container(
            content=ft.Column([
                ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("Click to open config.json:"),
                ft.ElevatedButton(
                    "Open config.json",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=open_file,
                    bgcolor=ft.Colors.BLUE_400,
                    color=ft.Colors.WHITE
                ),
                ft.Text("Or edit manually at:", size=12),
                ft.Text(config_path, selectable=True, size=11),
                ft.ElevatedButton("Close", on_click=close_overlay)
            ]),
            bgcolor=ft.Colors.WHITE,
            padding=20,
            width=400,
            height=300
        )
        
        page.add(overlay_container)
        page.update()

    def handle_refresh_click(e):
        """Kick off a manual refresh on a background thread.

        Does not block: the actual subprocess call happens in `_run_refresh`
        on a separate thread, so the button handler returns immediately and
        the rest of the GUI stays responsive while it runs.
        """
        threading.Thread(
            target=_run_refresh,
            args=(page, status_text, interval_hours, True, refresh_button),
            daemon=True,
        ).start()

    # ========== UI BUILDING ==========
    
    # Ensure database exists
    init_database()
    
    # Fetch articles by priority
    p1_articles = get_articles_by_priority(1, status="summarized", limit=5)
    p2_articles = get_articles_by_priority(2, status="summarized", limit=5)

    refresh_button = ft.ElevatedButton(
        "Refresh News",
        icon=ft.Icons.REFRESH,
        on_click=handle_refresh_click,
    )

    # Header with BOTH buttons
    header = ft.Row([
        ft.Column([
            ft.Text("Snewzy", size=32, weight=ft.FontWeight.BOLD),
            ft.Text("Your personalized news digest", size=16, 
                   color=ft.Colors.GREY_600),
        ]),
        ft.Row([
            ft.ElevatedButton(
                "Settings",
                icon=ft.Icons.SETTINGS,
                on_click=open_settings
            ),
            refresh_button
        ])
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    
    # Build rest of page...
    page.add(
        ft.Column([
            header,
            status_text,
            ft.Divider(),
            create_priority_section(page, 1, p1_articles, lambda e: None),
            ft.Divider(),
            create_priority_section(page, 2, p2_articles, lambda e: None)
        ], scroll=ft.ScrollMode.AUTO, expand=True)
    )

    # Start (or restart) the periodic automatic-refresh countdown for this
    # freshly built page/status control. Runs every `interval_hours` hours
    # without any user interaction, on the same background-thread pattern as
    # the manual button, and gets reset every time a refresh completes.
    _schedule_auto_refresh(page, status_text, interval_hours)


def run_display():
    """Entry point to start the GUI."""
    ft.app(target=main_page)
