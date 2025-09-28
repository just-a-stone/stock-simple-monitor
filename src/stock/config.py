from __future__ import annotations

import os
from typing import Dict, Optional

_DOTENV_CACHE: Optional[Dict[str, str]] = None


def _find_project_root(start: Optional[str] = None) -> str:
    cur = os.path.abspath(start or os.getcwd())
    while True:
        for marker in (".env", "pyproject.toml", ".git"):
            if os.path.exists(os.path.join(cur, marker)):
                return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.getcwd()
        cur = parent


def _parse_dotenv(content: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        # Trim surrounding quotes if present (both single and double)
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        env[key] = val
    return env


def load_dotenv(refresh: bool = False) -> Dict[str, str]:
    global _DOTENV_CACHE
    if _DOTENV_CACHE is not None and not refresh:
        return _DOTENV_CACHE
    root = _find_project_root()
    path = os.path.join(root, ".env")
    if not os.path.exists(path):
        _DOTENV_CACHE = {}
        return _DOTENV_CACHE
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        _DOTENV_CACHE = _parse_dotenv(content)
    except Exception:
        _DOTENV_CACHE = {}
    return _DOTENV_CACHE


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    env = load_dotenv()
    return env.get(name, default)
