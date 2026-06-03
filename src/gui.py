"""
gui.py — YALLA PIPS Standalone
Settings window (tkinter) + system tray icon (pystray).
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import pystray
from PIL import Image, ImageDraw
from src import config

# ── Build tray icon image ─────────────────────────────────────────
def _tray_icon_image() -> Image.Image:
    img  = Image.new("RGB", (64, 64), (10, 12, 18))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(2,2),(62,62)], outline=(255, 214, 0), width=3)
    draw.text((32, 32), "YP", fill=(255, 214, 0), anchor="mm")
    return img


# ── Settings window ───────────────────────────────────────────────
class SettingsWindow:
    def __init__(self, on_apply=None):
        self._on_apply = on_apply
        self._root = None

    def show(self):
        if self._root and self._root.winfo_exists():
            self._root.lift()
            return
        self._build()

    def _build(self):
        root = tk.Tk()
        self._root = root
        root.title("⬡ YALLA PIPS — Keyboard Settings")
        root.configure(bg="#0e0e1a")
        root.resizable(False, False)

        # ── Style ──
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TLabel",  background="#0e0e1a", foreground="#cccccc", font=("Segoe UI", 9))
        style.configure("TEntry",  fieldbackground="#1a1a2e", foreground="#ffffff", insertcolor="#ffffff")
        style.configure("TFrame",  background="#0e0e1a")
        style.configure("Gold.TLabel", foreground="#ffd600", font=("Segoe UI", 11, "bold"))
        style.configure("Gold.TButton", background="#ffd600", foreground="#000000",
                         font=("Segoe UI", 9, "bold"), padding=6)
        style.configure("TCombobox", fieldbackground="#1a1a2e", foreground="#ffffff")

        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="⬡ YALLA PIPS  —  TRADING KEYBOARD", style="Gold.TLabel").grid(
            row=0, column=0, columnspan=4, pady=(0, 14))

        # ── Trade settings ──
        def row(label, key, r, col=0, width=12, cast=str):
            ttk.Label(frame, text=label).grid(row=r, column=col,   sticky="w", padx=(0,6))
            var = tk.StringVar(value=str(config.get(key, "")))
            ent = ttk.Entry(frame, textvariable=var, width=width)
            ent.grid(row=r, column=col+1, sticky="ew", padx=(0,14))
            return var, cast

        self._vars = {}

        ttk.Label(frame, text="── TRADE ──", foreground="#555", background="#0e0e1a").grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(4,2))

        self._vars["symbol"],    _ = row("Symbol",      "symbol",    2, 0, 10)
        self._vars["lots"],      _ = row("Lot Size",    "lots",      2, 2, 8)
        self._vars["sl_points"], _ = row("SL (points)", "sl_points", 3, 0, 8)
        self._vars["tp_points"], _ = row("TP (points)", "tp_points", 3, 2, 8)
        self._vars["magic"],     _ = row("Magic No.",   "magic",     4, 0, 8)

        ttk.Label(frame, text="Apply to:").grid(row=4, column=2, sticky="w", padx=(0,6))
        all_sym_var = tk.StringVar(value="All symbols" if config.get("all_symbols") else "Chart symbol only")
        combo = ttk.Combobox(frame, textvariable=all_sym_var, width=14,
                             values=["Chart symbol only", "All symbols"], state="readonly")
        combo.grid(row=4, column=3, sticky="ew")
        self._vars["all_symbols"] = all_sym_var

        ttk.Label(frame, text="── AUTO BE & TRAILING ──", foreground="#555",
                  background="#0e0e1a").grid(row=5, column=0, columnspan=4, sticky="w", pady=(10,2))

        self._vars["be_pips"],    _ = row("BE Pips",       "be_pips",    6, 0, 8)
        self._vars["trail_pips"], _ = row("Trail Pips",    "trail_pips", 6, 2, 8)
        self._vars["trail_step"], _ = row("Trail Step",    "trail_step", 7, 0, 8)

        ttk.Label(frame, text="── DEVICE ──", foreground="#555",
                  background="#0e0e1a").grid(row=8, column=0, columnspan=4, sticky="w", pady=(10,2))

        self._vars["brightness"], _ = row("Brightness %", "brightness", 9, 0, 8)
        self._vars["custom_vid"], _ = row("Custom VID (hex)", "custom_vid", 9, 2, 8)
        self._vars["custom_pid"], _ = row("Custom PID (hex)", "custom_pid", 10, 0, 8)

        ttk.Label(frame, text="(Leave VID/PID blank for auto-detect)", foreground="#444",
                  background="#0e0e1a", font=("Segoe UI", 8)).grid(
            row=10, column=2, columnspan=2, sticky="w")

        # ── Buttons ──
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=11, column=0, columnspan=4, pady=(16, 0))

        ttk.Button(btn_frame, text="✔  APPLY & SAVE", style="Gold.TButton",
                   command=self._apply).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="✕  Cancel",
                   command=root.destroy).pack(side="left", padx=4)

        root.mainloop()

    def _apply(self):
        for key, var in self._vars.items():
            val = var.get()
            if key == "all_symbols":
                config.set(key, val == "All symbols")
            elif key in ("custom_vid", "custom_pid"):
                config.set(key, int(val, 16) if val.strip() else None)
            elif key in ("lots",):
                try:
                    config.set(key, float(val))
                except ValueError:
                    pass
            elif key in ("sl_points","tp_points","magic","be_pips","trail_pips","trail_step","brightness"):
                try:
                    config.set(key, int(val))
                except ValueError:
                    pass
            else:
                config.set(key, val)

        if self._on_apply:
            self._on_apply()
        messagebox.showinfo("YALLA PIPS", "Settings saved. Restart to apply device changes.")
        self._root.destroy()


# ── System tray app ───────────────────────────────────────────────
class TrayApp:
    def __init__(self, keyboard_controller=None):
        self._kb      = keyboard_controller
        self._settings_win = SettingsWindow(on_apply=self._on_settings_applied)

    def _on_settings_applied(self):
        if self._kb:
            self._kb._dev.set_brightness(config.get("brightness", 80))
            self._kb._render_all_idle()

    def _open_settings(self, icon, item):
        threading.Thread(target=self._settings_win.show, daemon=True).start()

    def _quit(self, icon, item):
        if self._kb:
            self._kb.shutdown()
        icon.stop()

    def run(self):
        menu = pystray.Menu(
            pystray.MenuItem("⬡ YALLA PIPS Keyboard", lambda i, it: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings...",   self._open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",          self._quit),
        )
        icon = pystray.Icon(
            name   = "YallaPips",
            icon   = _tray_icon_image(),
            title  = "YALLA PIPS Trading Keyboard",
            menu   = menu,
        )
        icon.run()
