"""
keyboard.py — YALLA PIPS Trading Keyboard
Key event handling and trade execution.
Copyright © 2026 YALLA PIPS. All rights reserved.
"""
import time
import threading
import logging

from src.config      import get
from src.hardware    import StreamDockDevice
from src             import key_renderer as kr
from src             import mt5_bridge   as mt5b

Logger = logging.getLogger("yp")


class YallaPipsKeyboard:

    def __init__(self, dev: StreamDockDevice):
        self._dev              = dev
        self._lock             = threading.Lock()
        self._auto_be          = False
        self._trailing         = False
        self._last_order_time  = 0.0   # debounce
        self._ORDER_COOLDOWN   = 2.0   # seconds between orders

        dev.set_key_callback(self._on_key)
        self._render_splash()
        self._render_all_idle()
        self._refresh_long_display()
        self._start_mt5_ticker()
        Logger.info("Keyboard initialised")

    # ── Splash ────────────────────────────────────────────────────
    def _render_splash(self):
        for i in range(self._dev.key_count):
            self._push(i, kr.render_splash(i + 1))
        time.sleep(1.5)

    # ── Idle render ───────────────────────────────────────────────
    def _render_all_idle(self):
        info  = mt5b.get_account_info()
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
        self._push(14, kr.render_mt5(
            balance=info.get("balance", 0),
            equity=info.get("equity", 0),
            profit=info.get("profit", 0),
            currency=info.get("currency", ""),
            connected=bool(info),
        ))

    def _price(self) -> str:
        try:
            import MetaTrader5 as mt5
            tick = mt5.symbol_info_tick(get("symbol", "XAUUSD"))
            if tick:
                return f"{tick.ask:.{mt5.symbol_info(get('symbol','XAUUSD')).digits}f}"
        except Exception:
            pass
        return ""

    def _push(self, idx: int, img):
        try:
            self._dev.set_key_image(idx, img)
        except Exception as e:
            Logger.error(f"Push key {idx}: {e}")

    # ── MT5 ticker ────────────────────────────────────────────────
    def _start_mt5_ticker(self):
        def _tick():
            while True:
                try:
                    self._refresh_mt5_key()
                    self._refresh_long_display()
                    if self._auto_be:
                        mt5b.check_auto_be(get("be_pips", 20),
                                           None if get("all_symbols") else get("symbol"))
                    if self._trailing:
                        mt5b.update_trailing(get("trail_pips", 15), get("trail_step", 5),
                                             None if get("all_symbols") else get("symbol"))
                except Exception as e:
                    Logger.error(f"Ticker error: {e}")
                time.sleep(5)

        threading.Thread(target=_tick, daemon=True).start()

    def _refresh_mt5_key(self):
        info = mt5b.get_account_info()
        self._push(14, kr.render_mt5(
            balance=info.get("balance", 0),
            equity=info.get("equity", 0),
            profit=info.get("profit", 0),
            currency=info.get("currency", ""),
            connected=bool(info),
        ))

    def _refresh_long_display(self):
        info      = mt5b.get_account_info()
        connected = bool(info)
        panels    = kr.render_long_display_panels(
            profit    = info.get("profit", 0.0),
            currency  = info.get("currency", "USD"),
            connected = connected,
        )
        for key_num, img in panels:
            try:
                self._dev.set_long_display_panel(key_num, img)
            except Exception as e:
                Logger.error(f"Long display panel {key_num}: {e}")

    # ── Key event ─────────────────────────────────────────────────
    def _on_key(self, logical_idx: int, pressed: bool):
        if not pressed:
            return
        Logger.info(f"Key {logical_idx} pressed")
        actions = {
            0:  self._buy,
            1:  self._sell,
            2:  self._close_all,
            3:  self._close_losing,
            4:  self._close_profitable,
            5:  self._sl_to_be,
            6:  self._close_25,
            7:  self._close_50,
            8:  self._close_75,
            9:  self._toggle_auto_be,
            10: self._tighten_sl,
            11: self._toggle_trailing,
            12: self._open_tradingview,
            13: self._open_forexfactory,
            14: self._refresh_mt5_key,
        }
        fn = actions.get(logical_idx)
        if fn:
            threading.Thread(target=fn, daemon=True).start()

    # ── Flash feedback ────────────────────────────────────────────
    def _flash(self, key_idx: int, success: bool, msg: str = ""):
        img = kr.render_flash_ok(msg) if success else kr.render_flash_err(msg)
        self._push(key_idx, img)
        time.sleep(2.0)
        self._render_all_idle()

    # ── Order debounce ────────────────────────────────────────────
    def _check_cooldown(self, name: str) -> bool:
        now = time.time()
        if now - self._last_order_time < self._ORDER_COOLDOWN:
            remaining = self._ORDER_COOLDOWN - (now - self._last_order_time)
            Logger.warning(f"{name} ignored — cooldown {remaining:.1f}s")
            return False
        self._last_order_time = now
        return True

    # ── BUY ───────────────────────────────────────────────────────
    def _buy(self):
        if not self._check_cooldown("BUY"):
            return
        sym = get("symbol", "XAUUSD")
        Logger.info(f"→ BUY {get('lots')} {sym} "
                    f"SL={get('sl_points')} TP={get('tp_points')} "
                    f"magic={get('magic')} broker={get('broker_type','auto')}")
        try:
            r = mt5b.buy(sym, get("lots"), get("sl_points"),
                         get("tp_points"), get("magic"))
        except Exception as e:
            Logger.error(f"BUY exception: {e}")
            self._flash(0, False, str(e)[:14])
            return

        Logger.info(f"BUY result: {r}")
        if r.get("success"):
            self._flash(0, True, f"{r.get('price', 0):.2f}")
        else:
            err = r.get("error", "FAIL")
            Logger.error(f"BUY FAILED — {err}")
            self._flash(0, False, err[:14])

    # ── SELL ──────────────────────────────────────────────────────
    def _sell(self):
        if not self._check_cooldown("SELL"):
            return
        sym = get("symbol", "XAUUSD")
        Logger.info(f"→ SELL {get('lots')} {sym} "
                    f"SL={get('sl_points')} TP={get('tp_points')} "
                    f"magic={get('magic')} broker={get('broker_type','auto')}")
        try:
            r = mt5b.sell(sym, get("lots"), get("sl_points"),
                          get("tp_points"), get("magic"))
        except Exception as e:
            Logger.error(f"SELL exception: {e}")
            self._flash(1, False, str(e)[:14])
            return

        Logger.info(f"SELL result: {r}")
        if r.get("success"):
            self._flash(1, True, f"{r.get('price', 0):.2f}")
        else:
            err = r.get("error", "FAIL")
            Logger.error(f"SELL FAILED — {err}")
            self._flash(1, False, err[:14])

    # ── Close actions ─────────────────────────────────────────────
    def _sym(self):
        return None if get("all_symbols") else get("symbol", "XAUUSD")

    def _close_all(self):
        n = mt5b.close_all(self._sym())
        self._push(2, kr.render_flash_ok(f"{n} CLOSED") if n else
                      kr.render_flash_err("NONE"))
        time.sleep(2.0); self._render_all_idle()

    def _close_losing(self):
        n = mt5b.close_losing(self._sym())
        self._push(3, kr.render_flash_ok(f"{n} CLOSED") if n else
                      kr.render_flash_err("NONE"))
        time.sleep(2.0); self._render_all_idle()

    def _close_profitable(self):
        n = mt5b.close_profitable(self._sym())
        self._push(4, kr.render_flash_ok(f"{n} CLOSED") if n else
                      kr.render_flash_err("NONE"))
        time.sleep(2.0); self._render_all_idle()

    def _close_25(self):
        n = mt5b.partial_close_pct(25, self._sym())
        self._push(6, kr.render_flash_ok(f"{n} DONE") if n else
                      kr.render_flash_err("NONE"))
        time.sleep(2.0); self._render_all_idle()

    def _close_50(self):
        n = mt5b.partial_close_pct(50, self._sym())
        self._push(7, kr.render_flash_ok(f"{n} DONE") if n else
                      kr.render_flash_err("NONE"))
        time.sleep(2.0); self._render_all_idle()

    def _close_75(self):
        n = mt5b.partial_close_pct(75, self._sym())
        self._push(8, kr.render_flash_ok(f"{n} DONE") if n else
                      kr.render_flash_err("NONE"))
        time.sleep(2.0); self._render_all_idle()

    def _sl_to_be(self):
        n = mt5b.move_sl_to_be(self._sym())
        self._push(5, kr.render_flash_ok(f"{n} MOVED") if n else
                      kr.render_flash_err("NONE"))
        time.sleep(2.0); self._render_all_idle()

    def _tighten_sl(self):
        n = mt5b.tighten_sl(self._sym())
        self._push(10, kr.render_flash_ok(f"{n} DONE") if n else
                       kr.render_flash_err("NONE"))
        time.sleep(2.0); self._render_all_idle()

    # ── Toggles ───────────────────────────────────────────────────
    def _toggle_auto_be(self):
        self._auto_be = not self._auto_be
        self._push(9, kr.render_auto_be(self._auto_be, int(get("be_pips", 20))))
        Logger.info(f"AutoBE {'ON' if self._auto_be else 'OFF'}")

    def _toggle_trailing(self):
        self._trailing = not self._trailing
        self._push(11, kr.render_trailing(self._trailing, int(get("trail_pips", 15))))
        Logger.info(f"Trailing {'ON' if self._trailing else 'OFF'}")

    # ── External links ────────────────────────────────────────────
    def _open_tradingview(self):
        import webbrowser
        webbrowser.open("https://www.tradingview.com")

    def _open_forexfactory(self):
        import webbrowser
        webbrowser.open("https://www.forexfactory.com")

    # ── Settings refresh ──────────────────────────────────────────
    def refresh_settings_keys(self):
        price = self._price()
        self._push(0,  kr.render_buy(price))
        self._push(1,  kr.render_sell(price))
        self._push(9,  kr.render_auto_be(self._auto_be, int(get("be_pips", 20))))
        self._push(11, kr.render_trailing(self._trailing, int(get("trail_pips", 15))))
        self._refresh_mt5_key()
        Logger.info("Settings keys refreshed instantly")

    # ── Shutdown ──────────────────────────────────────────────────
    def shutdown(self):
        Logger.info("Shutting down keyboard")
        try:
            self._dev.clear_all()
        except Exception as e:
            Logger.error(f"Shutdown clear: {e}")
        try:
            self._dev.close()
        except Exception:
            pass
