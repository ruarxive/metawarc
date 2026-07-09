import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from metawarc import __version__

load_dotenv()


def env_str(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    if value is None:
        return default
    value = str(value).strip()
    return default if not value else value


def env_bool(name: str, default: str = "false") -> bool:
    value = env_str(name, default) or default
    return value.lower() in ("1", "true", "yes", "on")


VERSION = __version__
AUTHOR = "Ruarxive (Ivan Begtin)"
HOME_PAGE = "https://github.com/ruarxive/metawarc"
EMAIL = "ivan@begtin.tech"
CONTACT = {"name": AUTHOR, "url": HOME_PAGE, "email": EMAIL}

TITLE = env_str("METAWARC_TITLE") or "Metawarc API"
SUMMARY = "API access to WARC collections and records."
DESCRIPTION = """
The Metawarc API provides endpoints to interact with indexed WARC collections and their contents.
"""

OPEN_API_PUBLIC_URL = env_str("OPEN_API_PUBLIC_URL") or "/openapi.json"

TAGS: List[Dict[str, Any]] = [
    {
        "name": "Metawarc",
        "description": "WARC collections endpoints.",
        "externalDocs": {
            "description": "Metawarc source code",
            "url": HOME_PAGE,
        },
    }
]

TESTING = False
DEBUG = env_bool("METAWARC_DEBUG", "true")

DB_PATH = env_str("METAWARC_DB_PATH") or "warcindex.db"
PORT = int(env_str("METAWARC_PORT") or env_str("PORT") or "8000")
MCP_PORT = int(env_str("METAWARC_MCP_PORT") or "8191")

MAX_PAGE = 500
MAX_OFFSET = 100000

LOG_JSON = env_bool("METAWARC_LOG_JSON", "true")
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO
