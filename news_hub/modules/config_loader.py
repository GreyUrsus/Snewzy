"""Config loader module - reads and validates config.json"""

import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List


class SiteConfig(BaseModel):
    """Configuration for a single news source."""
    name: str
    rss_url: str
    priority_boost: bool = False

class KeywordsConfig(BaseModel):
    """Keyword lists organized by priority."""
    priority_1: list[str] = Field(default_factory=list)
    priority_2: list[str] = Field(default_factory=list)
    priority_3: list[str] = Field(default_factory=list)

class APIConfig(BaseModel):
    """AI service configuration."""
    provider: str
    model: str

class SettingsConfig(BaseModel):
    """Application behavior settings."""
    scan_interval_hours: int = 6
    max_articles_per_scan: int = 50

class AppConfig(BaseModel):
    """Root configuration container."""
    whitelist_sites: list[SiteConfig]
    keywords: KeywordsConfig
    api: APIConfig
    settings: SettingsConfig

    
def load_config(config_path: str = None) -> AppConfig:
    """Load and validate configuration from JSON file.
    
    Args:
        config_path: Path to config file. If None, looks in project root.
    
    Returns:
        AppConfig: Validated configuration object.
    """
    #if no path provided, navigate from this file to project root
    if config_path is None:
        #__file__ is this file's location
        #.parent = modules/
        #.parent = new_hub/
        #.parent = snewzy/(project root)
        config_path = Path(__file__).parent.parent.parent/"config.json"

    #Convert to Path object if string was passed
    config_path = Path(config_path)

    #Check if file exists (helpful error message if not)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    #Open and read the JSON file
    with open(config_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    #Validate and convert to Pydantic model
    config = AppConfig.model_validate(raw_data)

    return config

#Test code (runs only when executing this file directly)
if __name__ == "__main__":
    try:
        config = load_config()
        print("Config loaded successfully!")
        print(f"Sites: {len(config.whitelist_sites)}")
        print(f"Priority 1 keywords: {config.keywords.priority_1}")
    except Exception as e:
        print(f"Error: {e}")