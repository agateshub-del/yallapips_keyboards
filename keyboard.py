"""
keyboard.py — YALLA PIPS Standalone
Central controller: maps 15 keys to MT5 actions + drives all displays.
"""
import threading
import time
import logging
from src import hardware, mt5_bridge as mt5b, key_renderer as kr
from src.config import get

Logger = logging.getLogger("yp")


class YallaPipsKeyboard:
    def __init__(self, device: hardware.StreamDockDevice):
        self._dev      = device
        self._lock     = threading.Lock()
        self._auto_be  = False
        self._trailing = False

        device.set_key_callback(self._on_key_event)
        device.set_brightness(get("brightness", 80))
        self._render_all_idle()
        self._start_mt5_ticker()

    # ── Render all keys in idle state ─────────────────────────────
    def _render_all_idle(self):
        price = self._price()
        self._push(0,  kr.render_buy(price))
        self._push(1,  kr.render_sell(price))
        self._push(2,  kr.render_close_all())
        self._push(3,  kr.render_close_losing())
        self._push(4,  kr.render_close_profit())
        self._push(5,  kr.render_sl_to_be())
        self._push(6,  kr.render_close_25())
        self._push(7,  kr.render_close_50())
        self._push(8,  kr.render_close_75())
        self._push(9,  kr.render_auto_be(self._auto_be, int(get("be_pips", 20))))
        self._push(10, kr.render_partial_sl())
        self._push(11, kr.render_trailing(self._trailing, int(get("trail_pips", 15))))
        self._push(12, kr.render_tradingview())
        self._push(13, kr.render_forexfactory())
        self._refresh_mt5_key()
        self._refresh_long_display()

    def _push(self, idx, img):
        try:
            self._dev.set_key_image(idx, img)
        except Exception as e:
            Logger.error(f"Push key {idx}: {e}")

    # ── Key press router ──────────────────────────────────────────
    def _on_key_event(self, key_index: int, pressed: bool):
        if not pressed:
            return
        Logger.info(f"Key {key_index} pressed")
        actions = {
            0:  self._buy,
            1:  self._sell,
            2:  self._close_all,
            3:  self._close_losing,
            4:  self._close_profit,
            5:  self._sl_to_be,
            6:  self._close_25,
            7:  self._close_50,
            8:  self._close_75,
            9:  self._toggle_auto_be,
            10: self._partial_sl,
            11: self._toggle_trailing,
            12: self._open_tradingview,
            13: self._open_forexfactory,
            14: self._refresh_mt5_key,
        }
        fn = actions.get(key_index)
        if fn:
            threading.Thread(target=fn, daemon=True).start()

    # ── Helpers ───────────────────────────────────────────────────
    def _sym(self):
        return None if get("all_symbols") else get("symbol", "XAUUSD")

    def _price(self):
        try:
            import MetaTrader5 as mt5
            t = mt5.symbol_info_tick(get("symbol", "XAUUSD"))
            if t:
                return f"{t.bid:.2f}"
        except Exception:
            pass
        return ""

    def _flash(self, idx, ok, msg=""):
        img = kr.render_flash_ok(msg) if ok else kr.render_flash_err(msg)
        self._push(idx, img)
        def restore():
            time.sleep(2)
            self._render_all_idle()
        threading.Thread(target=restore, daemon=True).start()

    # ── Trade actions ─────────────────────────────────────────────
    def _buy(self):
        r = mt5b.buy(get("symbol"), get("lots"), get("sl_points"),
                     get("tp_points"), get("magic"))
        self._flash(0, r.get("success", False),
                    f"{r.get('price',0):.2f}" if r.get("success") else "FAIL")

    def _sell(self):
        r = mt5b.sell(get("symbol"), get("lots"), get("sl_points"),
                      get("tp_points"), get("magic"))
        self._flash(1, r.get("success", False),
                    f"{r.get('price',0):.2f}" if r.get("success") else "FAIL")

    def _close_all(self):
        n = mt5b.close_all(self._sym())
        self._flash(2, True, f"{n} POS")

    def _close_losing(self):
        n = mt5b.close_losing(self._sym())
        self._flash(3, True, f"{n} POS")

    def _close_profit(self):
        n = mt5b.close_profitable(self._sym())
        self._flash(4, True, f"{n} POS")

    def _sl_to_be(self):
        n = mt5b.move_sl_to_be(self._sym())
        self._flash(5, True, f"{n} POS")

    def _close_25(self):
        n = mt5b.partial_close_pct(25, self._sym())
        self._flash(6, True, f"{n} POS")

    def _close_50(self):
        n = mt5b.partial_close_pct(50, self._sym())
        self._flash(7, True, f"{n} POS")

    def _close_75(self):
        n = mt5b.partial_close_pct(75, self._sym())
        self._flash(8, True, f"{n} POS")

    def _toggle_auto_be(self):
        self._auto_be = not self._auto_be
        self._push(9, kr.render_auto_be(self._auto_be, int(get("be_pips", 20))))
        Logger.info(f"Auto BE: {'ON' if self._auto_be else 'OFF'}")
        if self._auto_be:
            self._start_be_monitor()

    def _partial_sl(self):
        n = mt5b.tighten_sl(self._sym())
        self._flash(10, True, f"{n} POS")

    def _toggle_trailing(self):
        self._trailing = not self._trailing
        self._push(11, kr.render_trailing(self._trailing, int(get("trail_pips", 15))))
        Logger.info(f"Trailing: {'ON' if self._trailing else 'OFF'}")
        if self._trailing:
            self._start_trail_monitor()

    def _open_tradingview(self):
        import webbrowser
        webbrowser.open("https://www.tradingview.com")

    def _open_forexfactory(self):
        import webbrowser
        webbrowser.open("https://www.forexfactory.com")

    # ── MT5 key (14) ─────────────────────────────────────────────
    def _refresh_mt5_key(self):
        info      = mt5b.get_account_info()
        connected = bool(info)
        img = kr.render_mt5(
            balance   = info.get("balance", 0),
            equity    = info.get("equity",  0),
            profit    = info.get("profit",  0),
            currency  = info.get("currency",""),
            connected = connected,
        )
        self._push(14, img)

    # ── Long display (right strip) ────────────────────────────────
    def _refresh_long_display(self):
        info      = mt5b.get_account_info()
        connected = bool(info)
        img = kr.render_long_display(
            profit    = info.get("profit", 0.0),
            currency  = info.get("currency", "USD"),
            connected = connected,
        )
        try:
            self._dev.set_long_display(img)
        except Exception as e:
            Logger.error(f"Long display error: {e}")

    # ── Periodic ticker (every 5s) ────────────────────────────────
    def _start_mt5_ticker(self):
        def tick():
            while True:
                time.sleep(5)
                try:
                    self._refresh_mt5_key()
                    price = self._price()
                    self._push(0, kr.render_buy(price))
                    self._push(1, kr.render_sell(price))
                    self._refresh_long_display()
                except Exception:
                    pass
        t = threading.Thread(target=tick, daemon=True)
        t.start()

    # ── Auto BE monitor ───────────────────────────────────────────
    def _start_be_monitor(self):
        def tick():
            while self._auto_be:
                try:
                    mt5b.check_auto_be(get("be_pips", 20), self._sym())
                except Exception:
                    pass
                time.sleep(2)
        threading.Thread(target=tick, daemon=True).start()

    # ── Trailing monitor ──────────────────────────────────────────
    def _start_trail_monitor(self):
        def tick():
            while self._trailing:
                try:
                    mt5b.update_trailing(get("trail_pips", 15),
                                         get("trail_step", 5), self._sym())
                except Exception:
                    pass
                time.sleep(1)
        threading.Thread(target=tick, daemon=True).start()

    def shutdown(self):
        self._auto_be  = False
        self._trailing = False
        self._dev.clear_all()
        self._dev.close()
