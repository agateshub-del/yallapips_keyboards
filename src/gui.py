"""
gui.py — YALLA PIPS Trading Keyboard
Settings window + system tray.
Copyright © 2026 YALLA PIPS. All rights reserved.
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import pystray
from PIL import Image, ImageDraw
import logging
from src.config import get, set_and_save

Logger = logging.getLogger("yp")

VERSION   = "1.0.0"
COPYRIGHT = "© 2026 YALLA PIPS. All rights reserved."

_keyboard_ref = None

def set_keyboard_ref(kb):
    global _keyboard_ref
    _keyboard_ref = kb


# ── Tray icon ─────────────────────────────────────────────────────
def _make_tray_icon():
    img  = Image.new("RGB", (64, 64), (8, 10, 16))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(2, 2),(61,61)], outline=(255,214,0), width=3)
    draw.text((32,32), "YP", fill=(255,214,0), anchor="mm")
    return img


def _open_settings(_=None):
    threading.Thread(target=show_settings_window, daemon=True).start()


# ── About dialog ──────────────────────────────────────────────────
def show_about():
    root = tk.Tk()
    root.title("About YALLA PIPS")
    root.resizable(False, False)
    root.configure(bg="#0a0c14")
    tk.Label(root, text="YALLA PIPS",      bg="#0a0c14", fg="#ffd600",
             font=("Arial",22,"bold")).pack(pady=(20,4))
    tk.Label(root, text="Trading Keyboard", bg="#0a0c14", fg="#e6e6e6",
             font=("Arial",13)).pack()
    tk.Label(root, text=f"Version {VERSION}", bg="#0a0c14", fg="#888",
             font=("Arial",10)).pack(pady=(8,2))
    tk.Label(root, text="XAUUSD — Smart Money Concepts", bg="#0a0c14", fg="#555",
             font=("Arial",9)).pack()
    tk.Frame(root, bg="#ffd600", height=1, width=260).pack(pady=12)
    tk.Label(root, text=COPYRIGHT,             bg="#0a0c14", fg="#666",
             font=("Arial",9)).pack()
    tk.Label(root, text="@YallaPips  |  yallapips.com", bg="#0a0c14", fg="#444",
             font=("Arial",9)).pack(pady=(2,16))
    tk.Button(root, text="Close", bg="#ffd600", fg="#000",
              font=("Arial",10,"bold"), command=root.destroy,
              width=12).pack(pady=(0,16))
    root.mainloop()


# ── Settings window ───────────────────────────────────────────────
def show_settings_window():
    root = tk.Tk()
    root.title("YALLA PIPS — Settings")
    root.resizable(False, False)
    root.configure(bg="#0a0c14")

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TLabel",       background="#0a0c14", foreground="#e6e6e6",
                    font=("Arial",10))
    style.configure("TEntry",       fieldbackground="#1a1c28", foreground="#e6e6e6",
                    font=("Arial",10))
    style.configure("TCheckbutton", background="#0a0c14", foreground="#e6e6e6",
                    font=("Arial",10))
    style.configure("TRadiobutton", background="#0a0c14", foreground="#e6e6e6",
                    font=("Arial",10))
    style.configure("Gold.TButton", background="#ffd600", foreground="#000000",
                    font=("Arial",10,"bold"))
    style.configure("TFrame",       background="#0a0c14")
    style.configure("TLabelframe",  background="#0a0c14", foreground="#ffd600")
    style.configure("TLabelframe.Label", background="#0a0c14", foreground="#ffd600",
                    font=("Arial",10,"bold"))

    pad = {"padx": 12, "pady": 4}

    # ── Header ────────────────────────────────────────────────────
    tk.Label(root, text="YALLA PIPS  Settings",
             bg="#0a0c14", fg="#ffd600",
             font=("Arial",14,"bold")).grid(row=0, column=0, columnspan=2,
                                             pady=(16,8), padx=16)

    # ── Trade fields ──────────────────────────────────────────────
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

    base_row = len(fields) + 1

    # ── All symbols toggle ────────────────────────────────────────
    all_sym = tk.BooleanVar(value=bool(get("all_symbols")))
    ttk.Checkbutton(root, text="Apply to ALL open positions",
                    variable=all_sym).grid(row=base_row, column=0,
                                           columnspan=2, pady=(4,2),
                                           padx=12, sticky="w")

    # ── Close mode ────────────────────────────────────────────────
    mode_frame = ttk.LabelFrame(root, text="  25 / 50 / 75 %  Close Mode  ")
    mode_frame.grid(row=base_row+1, column=0, columnspan=2,
                    padx=12, pady=(6,4), sticky="ew")

    close_mode = tk.StringVar(value=get("close_mode", "volume"))

    ttk.Radiobutton(mode_frame,
                    text="By Volume  (large lots — partial-close each position)",
                    variable=close_mode, value="volume"
                    ).grid(row=0, column=0, sticky="w", padx=10, pady=(6,2))
    ttk.Radiobutton(mode_frame,
                    text="By Count   (grid / small lots — fully close X% of positions)",
                    variable=close_mode, value="count"
                    ).grid(row=1, column=0, sticky="w", padx=10, pady=(2,6))

    hint_var = tk.StringVar()
    tk.Label(mode_frame, textvariable=hint_var,
             bg="#0a0c14", fg="#6080a0",
             font=("Arial",9,"italic")).grid(row=2, column=0,
                                              sticky="w", padx=14, pady=(0,6))

    def _update_hint(*_):
        if close_mode.get() == "count":
            hint_var.set("e.g. 20 grid entries × 25% = close 5 (most losing first)")
        else:
            hint_var.set("e.g. 1.0 lot × 25% = partially close 0.25 lot each")
    close_mode.trace_add("write", _update_hint)
    _update_hint()

    # ── Status label ──────────────────────────────────────────────
    status_var = tk.StringVar(value="")
    tk.Label(root, textvariable=status_var,
             bg="#0a0c14", fg="#00d264",
             font=("Arial",10,"bold")).grid(row=base_row+2, column=0,
                                             columnspan=2, pady=4)

    # ── Save button ───────────────────────────────────────────────
    def on_save():
        # Collect all field values
        updates = {
            "all_symbols": all_sym.get(),
            "close_mode":  close_mode.get(),
        }
        errors = []
        for key, (var, cast) in entries.items():
            try:
                updates[key] = cast(var.get())
            except ValueError:
                errors.append(key)

        if errors:
            messagebox.showerror("Invalid Input",
                                 f"Please fix: {', '.join(errors)}")
            return

        # Save to disk + update in-memory cache
        set_and_save(updates)
        Logger.info(f"Settings saved: {updates}")

        # Refresh key displays immediately
        if _keyboard_ref is not None:
            try:
                _keyboard_ref.refresh_settings_keys()
            except Exception as e:
                Logger.error(f"Refresh error: {e}")

        status_var.set("✓  Saved and applied instantly")
        root.after(3000, lambda: status_var.set(""))

    btn_frame = ttk.Frame(root)
    btn_frame.grid(row=base_row+3, column=0, columnspan=2, pady=(8,16))
    ttk.Button(btn_frame, text="Save & Apply", style="Gold.TButton",
               command=on_save).pack(side="left", padx=8)
    ttk.Button(btn_frame, text="Cancel",
               command=root.destroy).pack(side="left", padx=8)

    root.mainloop()


# ── Tray ──────────────────────────────────────────────────────────
def start_tray(on_quit):
    icon = pystray.Icon(
        "YallaPips",
        _make_tray_icon(),
        "YALLA PIPS Keyboard",
        menu=pystray.Menu(
            pystray.MenuItem("Settings",
                             _open_settings),
            pystray.MenuItem("About YALLA PIPS",
                             lambda: threading.Thread(
                                 target=show_about, daemon=True).start()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: on_quit(icon)),
        )
    )
    icon.run()


class TrayApp:
    def __init__(self, keyboard_controller=None, keyboard=None):
        kb = keyboard_controller or keyboard
        if kb:
            set_keyboard_ref(kb)

    def run(self, on_quit=None):
        def _quit(icon):
            icon.stop()
            if on_quit:
                on_quit()
        start_tray(_quit)

    def open_settings(self):
        _open_settings()
