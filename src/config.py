"""
config.py — YALLA PIPS Standalone
Loads/saves settings from config.json next to the exe.
"""
import json
import os

_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")

DEFAULTS = {
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
    "custom_vid":  None,
    "custom_pid":  None,
    "license_key": "",
}

_cfg = {}

def load():
    global _cfg
    _cfg = dict(DEFAULTS)
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, "r") as f:
                _cfg.update(json.load(f))
        except Exception:
            pass
    return _cfg

def save():
    try:
        with open(_CONFIG_FILE, "w") as f:
            json.dump(_cfg, f, indent=2)
    except Exception as e:
        print(f"Config save error: {e}")

def get(key, default=None):
    return _cfg.get(key, DEFAULTS.get(key, default))

def set(key, value):
    _cfg[key] = value
    save()

def all_settings():
    return dict(_cfg)
