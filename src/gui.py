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
    style.configure("TRadiobutton", background="#0a0c14", foreground="#e6e6e6", font=("Arial", 10))
    style.configure("Gold.TButton", background="#ffd600", foreground="#000000", font=("Arial", 10, "bold"))
    style.configure("TFrame",       background="#0a0c14")
    style.configure("TLabelframe",  background="#0a0c14", foreground="#ffd600")
    style.configure("TLabelframe.Label", background="#0a0c14", foreground="#ffd600",
                    font=("Arial", 10, "bold"))

    pad = {"padx": 12, "pady": 5}

    # ── Header ────────────────────────────────────────────────────
    tk.Label(root, text="YALLA PIPS Keyboard Settings",
             bg="#0a0c14", fg="#ffd600",
             font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=2,
                                               pady=(16, 6), padx=16)

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
    ttk.Checkbutton(root, text="Apply to ALL open positions (ignore symbol filter)",
                    variable=all_sym).grid(row=base_row, column=0,
                                           columnspan=2, pady=(4, 2), padx=12, sticky="w")

    # ── 25/50/75% Close Mode ──────────────────────────────────────
    mode_frame = ttk.LabelFrame(root, text="  25 / 50 / 75 % Close Mode  ")
    mode_frame.grid(row=base_row+1, column=0, columnspan=2,
                    padx=12, pady=(8, 4), sticky="ew")

    close_mode = tk.StringVar(value=get("close_mode", "volume"))

    vol_rb = ttk.Radiobutton(
        mode_frame, text="By Volume  (large lots — partial-close each position)",
        variable=close_mode, value="volume"
    )
    vol_rb.grid(row=0, column=0, sticky="w", padx=10, pady=(6, 2))

    cnt_rb = ttk.Radiobutton(
        mode_frame,
        text="By Count   (grid / small lots — fully close X% of positions)",
        variable=close_mode, value="count"
    )
    cnt_rb.grid(row=1, column=0, sticky="w", padx=10, pady=(2, 6))

    # Hint label
    hint_var = tk.StringVar()
    hint_lbl = tk.Label(mode_frame, textvariable=hint_var,
                        bg="#0a0c14", fg="#6080a0", font=("Arial", 9, "italic"))
    hint_lbl.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 6))

    def _update_hint(*_):
        if close_mode.get() == "count":
            hint_var.set("e.g. 20 grid entries × 25% = close 5 positions (most losing first)")
        else:
            hint_var.set("e.g. 1.0 lot × 25% = close 0.25 lot on each position")
    close_mode.trace_add("write", _update_hint)
    _update_hint()

    # ── Status ────────────────────────────────────────────────────
    status_var = tk.StringVar(value="")
    tk.Label(root, textvariable=status_var, bg="#0a0c14", fg="#00d264",
             font=("Arial", 10, "bold")).grid(row=base_row+2, column=0,
                                               columnspan=2, pady=4)

    # ── Save button ───────────────────────────────────────────────
    def on_save():
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
    btn_frame.grid(row=base_row+3, column=0, columnspan=2, pady=(8, 16))
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
