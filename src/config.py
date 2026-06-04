"""
config.py — YALLA PIPS
Live config: reads from JSON on every get() call.
No restart needed — changes apply instantly.
"""
import json
import os
import logging

Logger = logging.getLogger("yp")

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')
_CONFIG_PATH = os.path.abspath(_CONFIG_PATH)

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
    "close_mode":  "volume",  # "volume" or "count"
}

# In-memory cache — refreshed on every save or explicit reload
_cache = dict(_DEFAULTS)


def _load():
    global _cache
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


def _save_to_disk():
    try:
        with open(_CONFIG_PATH, "w") as f:
            json.dump(_cache, f, indent=2)
    except Exception as e:
        Logger.error(f"Config save error: {e}")


def get(key, default=None):
    """Read a config value. Always returns current in-memory value."""
    return _cache.get(key, default if default is not None else _DEFAULTS.get(key))


def set_and_save(updates: dict):
    """Update one or more keys and immediately persist to disk.
    No restart needed — changes take effect instantly."""
    global _cache
    _cache.update(updates)
    _save_to_disk()
    Logger.info(f"Config saved: {updates}")


def reload():
    """Re-read config.json from disk into memory."""
    _load()
    Logger.info("Config reloaded from disk")


# Load on import
_load()
