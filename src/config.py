"""
config.py — YALLA PIPS
Live config: changes apply instantly, no restart needed.
"""
import json
import os
import logging

Logger = logging.getLogger("yp")

_CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'config.json')
)

_DEFAULTS = {
    "symbol":      "XAUUSD",
    "lots":        0.10,
    "sl_points":   200,
    "tp_points":   400,
    "magic":       77777,
    "all_symbols": False,
    "be_pips":     20,
    "trail_pips":  15,
    "trail_step":  5,
    "brightness":  80,
    "custom_vid":  26115,
    "custom_pid":  4116,
}

_cache = dict(_DEFAULTS)


def load(path=None):
    """Public load — called by main.py on startup."""
    global _CONFIG_PATH, _cache
    if path:
        _CONFIG_PATH = os.path.abspath(path)
    try:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, "r") as f:
                data = json.load(f)
            _cache = {**_DEFAULTS, **data}
        else:
            _cache = dict(_DEFAULTS)
            _save_to_disk()
    except Exception as e:
        Logger.error(f"Config load error: {e}")
        _cache = dict(_DEFAULTS)


def reload():
    """Re-read config.json from disk."""
    load()
    Logger.info("Config reloaded")


def get(key, default=None):
    return _cache.get(key, default if default is not None else _DEFAULTS.get(key))


def set_and_save(updates: dict):
    """Save one or more keys instantly — no restart needed."""
    global _cache
    _cache.update(updates)
    _save_to_disk()
    Logger.info(f"Config saved: {updates}")


def _save_to_disk():
    try:
        with open(_CONFIG_PATH, "w") as f:
            json.dump(_cache, f, indent=2)
    except Exception as e:
        Logger.error(f"Config save error: {e}")


# Auto-load on import
load()
