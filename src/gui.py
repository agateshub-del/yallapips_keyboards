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

# Will be set by main.py after keyboard is initialised
_keyboard_ref = None

def set_keyboard_ref(kb):
    global _keyboard_ref
    _keyboard_ref = kb


# ── Tray icon ─────────────────────────────────────────────────────
def _make_tray_icon():
    img  = Image.new("RGB", (64, 64), (10, 12, 20))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(4,4),(60,60)], outline=(255, 214, 0), width=3)
    draw.text((32, 26), "YP", fill=(255, 214, 0), anchor="mm")
    return img


def _open_settings(_=None):
    threading.Thread(target=show_settings_window, daemon=True).start()


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


# ── Settings window ───────────────────────────────────────────────
def show_settings_window():
    root = tk.Tk()
    root.title("YALLA PIPS — Settings")
    root.resizable(False, False)
    root.configure(bg="#0a0c14")

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TLabel",      background="#0a0c14", foreground="#e6e6e6", font=("Arial", 10))
    style.configure("TEntry",      fieldbackground="#1a1c28", foreground="#e6e6e6", font=("Arial", 10))
    style.configure("TCheckbutton",background="#0a0c14", foreground="#e6e6e6", font=("Arial", 10))
    style.configure("Gold.TButton",background="#ffd600", foreground="#000000", font=("Arial", 10, "bold"))
    style.configure("TFrame",      background="#0a0c14")

    pad = {"padx": 12, "pady": 5}

    # ── Header ────────────────────────────────────────────────────
    tk.Label(root, text="YALLA PIPS Keyboard Settings",
             bg="#0a0c14", fg="#ffd600",
             font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=2,
                                               pady=(16,8), padx=16)

    # ── Field definitions ─────────────────────────────────────────
    fields = [
        ("Symbol",       "symbol",      str),
        ("Lot Size",     "lots",        float),
        ("SL Points",    "sl_points",   int),
        ("TP Points",    "tp_points",   int),
        ("Magic Number", "magic",       int),
        ("BE Pips",      "be_pips",     int),
        ("Trail Pips",   "trail_pips",  int),
        ("Trail Step",   "trail_step",  int),
        ("Brightness %", "brightness",  int),
    ]

    entries = {}
    for row, (label, key, _) in enumerate(fields, start=1):
        ttk.Label(root, text=label).grid(row=row, column=0, sticky="e", **pad)
        var = tk.StringVar(value=str(get(key)))
        e   = ttk.Entry(root, textvariable=var, width=18)
        e.grid(row=row, column=1, sticky="w", **pad)
        entries[key] = (var, _)

    # ── All symbols toggle ────────────────────────────────────────
    all_sym = tk.BooleanVar(value=bool(get("all_symbols")))
    ttk.Checkbutton(root, text="Apply to ALL open positions",
                    variable=all_sym).grid(row=len(fields)+1, column=0,
                                           columnspan=2, pady=4)

    # ── Status label ──────────────────────────────────────────────
    status_var = tk.StringVar(value="")
    status_lbl = tk.Label(root, textvariable=status_var,
                          bg="#0a0c14", fg="#00d264",
                          font=("Arial", 10, "bold"))
    status_lbl.grid(row=len(fields)+2, column=0, columnspan=2, pady=4)

    # ── Save button ───────────────────────────────────────────────
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

        # Save to disk — takes effect immediately
        set_and_save(updates)

        # Refresh key displays instantly
        if _keyboard_ref:
            try:
                _keyboard_ref.refresh_settings_keys()
            except Exception as e:
                Logger.error(f"Refresh error: {e}")

        status_var.set("✓ Settings saved — applied instantly")
        root.after(3000, lambda: status_var.set(""))

    btn_frame = ttk.Frame(root)
    btn_frame.grid(row=len(fields)+3, column=0, columnspan=2, pady=(8,16))
    ttk.Button(btn_frame, text="Save & Apply", style="Gold.TButton",
               command=on_save).pack(side="left", padx=8)
    ttk.Button(btn_frame, text="Cancel",
               command=root.destroy).pack(side="left", padx=8)

    root.mainloop()
