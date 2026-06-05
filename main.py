"""
main.py — YALLA PIPS Trading Keyboard
Entry point. Wires device → keyboard → tray correctly.
Copyright © 2026 YALLA PIPS. All rights reserved.
"""
import sys
import threading
import logging
import os

# ── Logging setup ─────────────────────────────────────────────────
log_path = os.path.join(os.path.dirname(sys.executable)
                        if getattr(sys, 'frozen', False)
                        else os.path.dirname(__file__), "yallapips.log")
logging.basicConfig(
    level=logging.INFO,
    format="[YP %(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
Logger = logging.getLogger("yp")

from src.config   import load, get
from src.hardware import find_device
from src.keyboard import YallaPipsKeyboard
from src import gui
from src import mt5_bridge as mt5b

_KB_VERSION = "1.0.0"

def main():
    Logger.info("─────────────────────────────────")
    Logger.info("  YALLA PIPS Trading Keyboard     ")
    Logger.info("  @YallaPips                      ")
    Logger.info(f"  v{_KB_VERSION}                 ")
    Logger.info("─────────────────────────────────")

    # 1. Load config
    load()

    # 2. Find device
    dev = find_device(
        custom_vid=get("custom_vid"),
        custom_pid=get("custom_pid"),
    )
    if not dev:
        Logger.error("No device found — exiting.")
        sys.exit(1)

    # 3. Open device
    try:
        dev.open()
    except Exception as e:
        Logger.error(f"Failed to open device: {e}")
        sys.exit(1)

    # 4. Connect MT5
    try:
        mt5b.connect()
        Logger.info("MT5 connected — MetaTrader 5")
    except Exception as e:
        Logger.warning(f"MT5 connect: {e}")

    # 5. Create keyboard controller
    kb = YallaPipsKeyboard(dev)
    Logger.info("Keyboard ready ✔")

    # 6. Register keyboard with GUI (CRITICAL — enables Save & Apply)
    gui.set_keyboard_ref(kb)

    # 7. Start tray (blocking — runs until Quit)
    def on_quit():
        Logger.info("Shutting down...")
        kb.shutdown()
        sys.exit(0)

    tray = gui.TrayApp(keyboard_controller=kb)
    tray.run(on_quit=on_quit)


if __name__ == "__main__":
    main()
