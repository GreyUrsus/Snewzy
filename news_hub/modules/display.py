"""Display module - simple GUI for viewing summarized news."""

import flet as ft
from typing import List, Tuple
from .database import get_articles_by_priority, init_database
from .settings_dialog import create_settings_dialog

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
        2: ft.Colors.ORANGE_100,
        3: ft.Colors.GREEN_100
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
    priority_names = {1: "Crtical", 2: "Important", 3: "General"}
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


def main_page(page: ft.Page):
    """Main application page."""
    page.title = "Snewzy - Personal News Hub"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    
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
            except Exception as ex:
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
    
    def refresh_news(e):
        """Run --update in background, then reload GUI."""
        import subprocess
        import sys
        
        # Show updating status
        status_text = ft.Text("Updating... (this may take a minute)", 
                             color=ft.Colors.ORANGE_500)
        page.add(status_text)
        page.update()
        
        try:
            # Run update process
            result = subprocess.run(
                [sys.executable, "-m", "news_hub.main", "--update"],
                capture_output=True,
                text=True,
                timeout=600  # Timeout: 5 minutes may not be enough for 15 articles × 30s each = 7.5 min.

            )
            
            # Remove status message
            page.remove(status_text)
            
            if result.returncode == 0:
                # Success - clear and rebuild page
                page.clean()
                main_page(page)
            else:
                # Show error
                error_msg = result.stderr[-200:] if result.stderr else "Unknown error"
                page.add(ft.Text(f"Update failed: {error_msg}", 
                               color=ft.Colors.RED_400))
                page.update()
                
        except subprocess.TimeoutExpired:
            page.remove(status_text)
            page.add(ft.Text("Update timed out (5 min)", color=ft.Colors.RED_400))
            page.update()
        except Exception as ex:
            page.remove(status_text)
            page.add(ft.Text(f"Error: {str(ex)}", color=ft.Colors.RED_400))
            page.update()
    
    # ========== UI BUILDING ==========
    
    # Ensure database exists
    init_database()
    
    # Fetch articles
    p1_articles = get_articles_by_priority(1, status="summarized", limit=5)
    p2_articles = get_articles_by_priority(2, status="summarized", limit=5)
    p3_articles = get_articles_by_priority(3, status="summarized", limit=5)
    
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
            ft.ElevatedButton(
                "Refresh News",
                icon=ft.Icons.REFRESH,
                on_click=refresh_news  # ← NEW BUTTON
            )
        ])
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    
    # Build rest of page...
    page.add(
        ft.Column([
            header,
            ft.Divider(),
            create_priority_section(page, 1, p1_articles, lambda e: None),
            ft.Divider(),
            create_priority_section(page, 2, p2_articles, lambda e: None),
            ft.Divider(),
            create_priority_section(page, 3, p3_articles, lambda e: None)
        ], scroll=ft.ScrollMode.AUTO, expand=True)
    )


def run_display():
    """Entry point to start the GUI."""
    ft.app(target=main_page)