"""
gui.py — YALLA PIPS
Settings window + system tray.
All settings apply INSTANTLY on Save — no restart needed.
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import pystray
from PIL import Image, ImageDraw
import logging
from src.config import get, set_and_save

Logger = logging.getLogger("yp")

_keyboard_ref = None

def set_keyboard_ref(kb):
    global _keyboard_ref
    _keyboard_ref = kb


def _make_tray_icon():
    img  = Image.new("RGB", (64, 64), (10, 12, 20))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(4,4),(60,60)], outline=(255, 214, 0), width=3)
    draw.text((32, 32), "YP", fill=(255, 214, 0), anchor="mm")
    return img


def _open_settings(_=None):
    threading.Thread(target=show_settings_window, daemon=True).start()


def show_settings_window():
    root = tk.Tk()
    root.title("YALLA PIPS — Settings")
    root.resizable(False, False)
    root.configure(bg="#0a0c14")

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TLabel",       background="#0a0c14", foreground="#e6e6e6", font=("Arial", 10))
    style.configure("TEntry",       fieldbackground="#1a1c28", foreground="#e6e6e6", font=("Arial", 10))
    style.configure("TCheckbutton", background="#0a0c14", foreground="#e6e6e6", font=("Arial", 10))
    style.configure("Gold.TButton", background="#ffd600", foreground="#000000", font=("Arial", 10, "bold"))
    style.configure("TFrame",       background="#0a0c14")

    pad = {"padx": 12, "pady": 5}

    tk.Label(root, text="YALLA PIPS Keyboard Settings",
             bg="#0a0c14", fg="#ffd600",
             font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=2,
                                               pady=(16, 8), padx=16)

    fields = [
        ("Symbol",       "symbol",     str),
        ("Lot Size",     "lots",       float),
        ("SL Points",    "sl_points",  int),
        ("TP Points",    "tp_points",  int),
        ("Magic Number", "magic",      int),
        ("BE Pips",      "be_pips",    int),
        ("Trail Pips",   "trail_pips", int),
        ("Trail Step",   "trail_step", int),
        ("Brightness %", "brightness", int),
    ]

    entries = {}
    for row, (label, key, cast) in enumerate(fields, start=1):
        ttk.Label(root, text=label).grid(row=row, column=0, sticky="e", **pad)
        var = tk.StringVar(value=str(get(key)))
        e   = ttk.Entry(root, textvariable=var, width=18)
        e.grid(row=row, column=1, sticky="w", **pad)
        entries[key] = (var, cast)

    all_sym = tk.BooleanVar(value=bool(get("all_symbols")))
    ttk.Checkbutton(root, text="Apply to ALL open positions",
                    variable=all_sym).grid(row=len(fields)+1, column=0,
                                           columnspan=2, pady=4)

    status_var = tk.StringVar(value="")
    tk.Label(root, textvariable=status_var, bg="#0a0c14", fg="#00d264",
             font=("Arial", 10, "bold")).grid(row=len(fields)+2, column=0,
                                               columnspan=2, pady=4)

    def on_save():
        updates = {"all_symbols": all_sym.get()}
        errors  = []
        for key, (var, cast) in entries.items():
            try:
                updates[key] = cast(var.get())
            except ValueError:
                errors.append(key)
        if errors:
            messagebox.showerror("Invalid input",
                                 f"Fix these fields: {', '.join(errors)}")
            return
        set_and_save(updates)
        if _keyboard_ref:
            try:
                _keyboard_ref.refresh_settings_keys()
            except Exception as e:
                Logger.error(f"Refresh error: {e}")
        status_var.set("✓ Settings saved and applied instantly")
        root.after(3000, lambda: status_var.set(""))

    btn_frame = ttk.Frame(root)
    btn_frame.grid(row=len(fields)+3, column=0, columnspan=2, pady=(8, 16))
    ttk.Button(btn_frame, text="Save & Apply", style="Gold.TButton",
               command=on_save).pack(side="left", padx=8)
    ttk.Button(btn_frame, text="Cancel",
               command=root.destroy).pack(side="left", padx=8)

    root.mainloop()


def start_tray(on_quit):
    icon = pystray.Icon(
        "YallaPips",
        _make_tray_icon(),
        "YALLA PIPS Keyboard",
        menu=pystray.Menu(
            pystray.MenuItem("Settings", _open_settings),
            pystray.MenuItem("Quit",     lambda: on_quit(icon)),
        )
    )
    icon.run()


# ── TrayApp class — keeps compatibility with main.py ─────────────
class TrayApp:
    def __init__(self, keyboard=None):
        if keyboard:
            set_keyboard_ref(keyboard)

    def run(self, on_quit=None):
        def _quit(icon):
            icon.stop()
            if on_quit:
                on_quit()
        start_tray(_quit)

    def open_settings(self):
        _open_settings()
