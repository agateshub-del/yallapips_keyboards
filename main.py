"""
main.py — YALLA PIPS Trading Keyboard
Standalone desktop app. No StreamDock software required.
"""
import sys
import logging
import threading
import time
from src import config, hardware
from src.keyboard import YallaPipsKeyboard
from src.gui import TrayApp

# ── Logging setup ─────────────────────────────────────────────────
logging.basicConfig(
    level   = logging.INFO,
    format  = "[YP %(levelname)s] %(message)s",
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("yallapips.log", encoding="utf-8"),
    ]
)
Logger = logging.getLogger("yp")


def main():
    Logger.info("─────────────────────────────────")
    Logger.info("  YALLA PIPS Trading Keyboard     ")
    Logger.info("  @YallaPips                      ")
    Logger.info("─────────────────────────────────")

    # Load settings
    config.load()

    # Find & connect to the physical device
    vid = config.get("custom_vid")
    pid = config.get("custom_pid")
    device = hardware.find_device(custom_vid=vid, custom_pid=pid)

    kb = None
    if device:
        try:
            device.open()
            kb = YallaPipsKeyboard(device)
            Logger.info("Keyboard ready ✔")
        except Exception as e:
            Logger.error(f"Device init failed: {e}")
            kb = None
    else:
        Logger.warning("Device not found — running in headless mode (settings only)")

    # Start system tray (blocks until quit)
    tray = TrayApp(keyboard_controller=kb)
    tray.run()

    Logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
