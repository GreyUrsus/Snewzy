"""Settings dialog for editing configuration."""
import json
from pathlib import Path
import flet as ft


def create_settings_dialog(page: ft.Page, on_save: callable = None):
    """Create settings editor dialog."""
    CONFIG_PATH = Path(__file__).parent.parent.parent/ "config.json"

    #Load current config
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    #Keyword fields
    p1_field = ft.TextField(
        label="Priority 1 Keywords (comma separated)",
        value=", ".join(config["keywords"]["priority_1"]),
        multiline=True,
        min_lines=2,
        hint_text="security, breach, vulnerability..."
    )

    p2_field = ft.TextField(
        label="Priority 2 Keywords (comma separated)",
        value=", ".join(config["keywords"]["priority_2"]),
        multiline=True,
        min_lines=2,
        hint_text= "funding, startup, investment..."
    )

    p3_field = ft.TextField(
        label="Priority 3 Keywords (comma separated)",
        value=", ".join(config["keywords"]["priority_3"]),
        multiline=True,
        min_lines=2,
        hint_text="review, analysis, opinion"
    )

    #RSS feed list
    sites_text = "\n".join([
        f"{s['name']}|{s['rss_url']}"
        for s in config["whitelist_sites"]
    ])

    sites_field = ft.TextField(
        label="RSS Feeds (format: name|url, one per line)",
        value=sites_text,
        multiline=True,
        min_lines=4
    )

    status_text = ft.Text("", color=ft.Colors.GREEN_400)

    def save_settings(e):
        """Save configuration back to file."""
        try:
            #Parse keywords
            new_config = {
                "whitelist_sites": [],
                "keywords": {
                    "priority_1": [k.strip() for k in p1_field.value.split(",") if k.strip()],
                    "priority_2": [k.strip() for k in p2_field.value.split(",") if k.strip()],
                    "priority_3": [k.strip() for k in p3_field.value.split(",") if k.strip()],
                },
                "api": config["api"],
                "settings": config["settings"]
            }

            #Parse sites
            for line in sites_field.value.strip().split("\n"):
                if "|" in line:
                    name, url = line.split("|", 1)
                    new_config["whitelist_sites"].append({
                        "name": name.strip(),
                        "rss_url": url.strip(),
                        "priority_boost": False
                    })

            #Write to file
            with open(CONFIG_PATH, "w") as f:
                json.dump(new_config, f, indent=2)

            status_text.value = "Settings saved!"
            status_text.color = ft.Colors.GREEN_400
            if on_save:
                on_save()

        except Exception as ex:
            status_text.value = f"Error: {ex}"
            status_text.color = ft.Colors.RED_400

        page.update()
    def close_dialog(e):
        dialog.open = False
        page.update()

    dialog = ft.AlertDialog(
        title=ft.Text("Settings"),
        content=ft.Container(
            content=ft.Column([
            ft.Text("Keywords", weight=ft.FontWeight.BOLD, size=16),
            p1_field,
            p2_field,
            p3_field,
            ft.Divider(),
            ft.Text("RSS Feeds", weight=ft.FontWeight.BOLD, size=16),
            sites_field,
            ft.Text("Format: Site Name|https://example.com/feed",
                    size=11, color=ft.Colors.GREY_500, italic=True),
            status_text
        ], scroll=ft.ScrollMode.AUTO, height=500, width=500)),
        actions=[
            ft.TextButton("Close", on_click=close_dialog),
            ft.ElevatedButton("Save", on_click=save_settings)
        ]
    )
    return dialog