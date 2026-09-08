"""
mt5_bridge.py — YALLA PIPS
Handles all MT5 trade operations.
Fully broker-agnostic: auto-detects filling mode, stop levels, volume step.
Works on Exness, Vantage, ICMarkets, and any MT5 broker.
Copyright © 2026 YALLA PIPS. All rights reserved.
"""
import sys
import json
import socket
import logging

Logger   = logging.getLogger("yp")
IS_WIN   = sys.platform == "win32"

try:
    import MetaTrader5 as mt5
    MT5_LOCAL = True
except ImportError:
    mt5        = None
    MT5_LOCAL  = False
    if IS_WIN:
        Logger.warning("MetaTrader5 not installed.")
    else:
        Logger.info("macOS: will use remote MT5 bridge.")


# ══════════════════════════════════════════════════════════════════
# Broker-agnostic helpers
# ══════════════════════════════════════════════════════════════════

def _filling_mode(si):
    """Auto-detect correct ORDER_FILLING from symbol bitmask."""
    fm = si.filling_mode
    if fm & 1: return mt5.ORDER_FILLING_FOK
    if fm & 2: return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


def _normalize_volume(si, lots: float) -> float:
    """Round lots to nearest valid step, clamped to min/max."""
    step = si.volume_step
    vol  = round(round(lots / step) * step, 8)
    return max(si.volume_min, min(si.volume_max, vol))


def _calc_sltp(si, price: float, sl_points: int, tp_points: int,
               is_buy: bool):
    """
    Calculate SL/TP respecting broker digit count.
    pip_factor converts user pips to broker raw points:
      2-digit broker (XAUUSD 0.01 point):  pip_factor=1
      3-digit broker (XAUUSD 0.001 point): pip_factor=10
    """
    from src.config import get
    dg = si.digits
    pt = si.point

    # pip_factor from settings, fallback to auto-detect from symbol digits
    broker_type = get("broker_type", "auto")
    if broker_type == "2digit":
        pip_factor = 1
    elif broker_type == "3digit":
        pip_factor = 10
    else:
        # auto: odd digit count = micro (3,5) needs ×10; even = standard
        pip_factor = 10 if (dg % 2 == 1) else 1

    sd = sl_points * pip_factor if sl_points else 0
    td = tp_points * pip_factor if tp_points else 0

    if is_buy:
        sl = round(price - sd * pt, dg) if sd else 0.0
        tp = round(price + td * pt, dg) if td else 0.0
    else:
        sl = round(price + sd * pt, dg) if sd else 0.0
        tp = round(price - td * pt, dg) if td else 0.0

    Logger.info(f"SL/TP calc: broker_type={broker_type} digits={dg} "
                f"pip_factor={pip_factor} sl={sl} tp={tp}")
    return sl, tp


# Cache successful filling mode per symbol to avoid retries on subsequent orders
_filling_cache: dict = {}


def _filling_mode_cached(si):
    """Return cached filling mode for symbol, or detect from bitmask."""
    sym = si.name
    if sym in _filling_cache:
        return _filling_cache[sym]
    fm = si.filling_mode
    if fm & 1: return mt5.ORDER_FILLING_FOK
    if fm & 2: return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


def _send_with_fallback(request: dict):
    """Send order, retrying all filling modes if broker rejects 10030."""
    sym = request.get("symbol","")
    r = mt5.order_send(request)
    if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
        _filling_cache[sym] = request["type_filling"]  # cache winner
        return r
    if r is not None and r.retcode == 10030:
        for fm in (mt5.ORDER_FILLING_IOC,
                   mt5.ORDER_FILLING_RETURN,
                   mt5.ORDER_FILLING_FOK):
            request["type_filling"] = fm
            r2 = mt5.order_send(request)
            if r2 is not None and r2.retcode == mt5.TRADE_RETCODE_DONE:
                _filling_cache[sym] = fm   # cache winner
                return r2
            if r2 is not None and r2.retcode != 10030:
                r = r2
    return r


def _ensure_symbol(symbol: str) -> bool:
    """Make sure symbol is in Market Watch and has a tick."""
    si = mt5.symbol_info(symbol)
    if si is None:
        return False
    if not si.visible:
        mt5.symbol_select(symbol, True)
    return True


# ══════════════════════════════════════════════════════════════════
# Remote bridge (for macOS)
# ══════════════════════════════════════════════════════════════════

def _remote_call(cmd: dict) -> dict:
    from src.config import get
    host    = get("mt5_bridge_host", "")
    port    = int(get("mt5_bridge_port", 9999))
    timeout = float(get("mt5_bridge_timeout", 5.0))
    if not host:
        return {"error": "mt5_bridge_host not set in Settings"}
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall((json.dumps(cmd) + "\n").encode())
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(4096)
                if not chunk: break
                buf += chunk
            return json.loads(buf.split(b"\n")[0])
    except ConnectionRefusedError:
        return {"error": f"Cannot reach MT5 bridge at {host}:{port}"}
    except Exception as e:
        return {"error": str(e)}


def _use_remote() -> bool:
    if not MT5_LOCAL:
        return True
    from src.config import get
    return bool(get("mt5_bridge_host", ""))


# ══════════════════════════════════════════════════════════════════
# Connection
# ══════════════════════════════════════════════════════════════════

def connect() -> bool:
    if not MT5_LOCAL: return False
    if mt5.terminal_info() is not None: return True
    if not mt5.initialize():
        Logger.error(f"MT5 init failed: {mt5.last_error()}")
        return False
    Logger.info(f"MT5 connected: {mt5.terminal_info().name}")
    return True


# ══════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════

def get_account_info() -> dict:
    if _use_remote():
        r = _remote_call({"action": "account_info"})
        return r if "balance" in r else {}
    if not connect(): return {}
    info = mt5.account_info()
    if not info: return {}
    return {"balance":  round(info.balance, 2),
            "equity":   round(info.equity,  2),
            "profit":   round(info.profit,  2),
            "currency": info.currency,
            "server":   info.server,
            "login":    info.login}


def get_open_positions(symbol=None) -> list:
    if _use_remote():
        return _remote_call({"action": "positions",
                              "symbol": symbol}).get("positions", [])
    if not connect(): return []
    pos = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    return list(pos) if pos else []


def buy(symbol, lots, sl_points, tp_points, magic):
    if _use_remote():
        return _remote_call({"action": "buy", "symbol": symbol, "lots": lots,
                              "sl_points": sl_points, "tp_points": tp_points,
                              "magic": magic})
    try:
        if not connect():
            return {"success": False, "error": "MT5 not connected"}
        if not _ensure_symbol(symbol):
            return {"success": False, "error": f"Symbol '{symbol}' not found"}

        si   = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if not tick or tick.ask == 0:
            return {"success": False, "error": f"No price for '{symbol}'"}

        price       = round(tick.ask, si.digits)
        lots_norm   = _normalize_volume(si, lots)
        sl, tp      = _calc_sltp(si, price, sl_points, tp_points, is_buy=True)

        Logger.info(f"BUY {lots_norm} {symbol} @ {price}  SL={sl}  TP={tp}  "
                    f"digits={si.digits} point={si.point}")

        req = {"action":       mt5.TRADE_ACTION_DEAL,
               "symbol":       symbol,
               "volume":       lots_norm,
               "type":         mt5.ORDER_TYPE_BUY,
               "price":        price,
               "sl":           sl,
               "tp":           tp,
               "deviation":    20,
               "magic":        magic,
               "comment":      "YP BUY",
               "type_time":    mt5.ORDER_TIME_GTC,
               "type_filling": _filling_mode(si)}

        r = _send_with_fallback(req)
        if r is None:
            return {"success": False, "error": f"order_send: {mt5.last_error()}"}
        if r.retcode == mt5.TRADE_RETCODE_DONE:
            return {"success": True, "ticket": r.order, "price": price}
        return {"success": False, "error": f"{r.retcode}: {r.comment}"}

    except Exception as e:
        Logger.error(f"buy() exception: {e}")
        return {"success": False, "error": str(e)}


def sell(symbol, lots, sl_points, tp_points, magic):
    if _use_remote():
        return _remote_call({"action": "sell", "symbol": symbol, "lots": lots,
                              "sl_points": sl_points, "tp_points": tp_points,
                              "magic": magic})
    try:
        if not connect():
            return {"success": False, "error": "MT5 not connected"}
        if not _ensure_symbol(symbol):
            return {"success": False, "error": f"Symbol '{symbol}' not found"}

        si   = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if not tick or tick.bid == 0:
            return {"success": False, "error": f"No price for '{symbol}'"}

        price       = round(tick.bid, si.digits)
        lots_norm   = _normalize_volume(si, lots)
        sl, tp      = _calc_sltp(si, price, sl_points, tp_points, is_buy=False)

        Logger.info(f"SELL {lots_norm} {symbol} @ {price}  SL={sl}  TP={tp}  "
                    f"digits={si.digits} point={si.point}")

        req = {"action":       mt5.TRADE_ACTION_DEAL,
               "symbol":       symbol,
               "volume":       lots_norm,
               "type":         mt5.ORDER_TYPE_SELL,
               "price":        price,
               "sl":           sl,
               "tp":           tp,
               "deviation":    20,
               "magic":        magic,
               "comment":      "YP SELL",
               "type_time":    mt5.ORDER_TIME_GTC,
               "type_filling": _filling_mode(si)}

        r = _send_with_fallback(req)
        if r is None:
            return {"success": False, "error": f"order_send: {mt5.last_error()}"}
        if r.retcode == mt5.TRADE_RETCODE_DONE:
            return {"success": True, "ticket": r.order, "price": price}
        return {"success": False, "error": f"{r.retcode}: {r.comment}"}

    except Exception as e:
        Logger.error(f"sell() exception: {e}")
        return {"success": False, "error": str(e)}


def _close_local(ticket: int, pos_data=None) -> bool:
    """Close a position by ticket. Pass pos_data to skip re-fetching."""
    if not connect(): return False
    if pos_data is None:
        fetched = mt5.positions_get(ticket=ticket)
        if not fetched: return False
        p = fetched[0]
    else:
        p = pos_data
    si   = mt5.symbol_info(p.symbol if hasattr(p,'symbol') else p["symbol"])
    sym  = p.symbol  if hasattr(p,'symbol')  else p["symbol"]
    vol  = p.volume  if hasattr(p,'volume')  else p["volume"]
    mag  = p.magic   if hasattr(p,'magic')   else p["magic"]
    ptype= p.type    if hasattr(p,'type')    else p["type"]
    ot   = mt5.ORDER_TYPE_SELL if ptype == 0 else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(sym)
    if not tick: return False
    pr   = tick.bid if ptype == 0 else tick.ask
    fm   = _filling_cache.get(sym) or (_filling_mode(si) if si else mt5.ORDER_FILLING_IOC)
    req  = {"action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       sym,
            "volume":       vol,
            "type":         ot,
            "position":     ticket,
            "price":        pr,
            "deviation":    20,
            "magic":        mag,
            "comment":      "YP CLOSE",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": fm}
    r = _send_with_fallback(req)
    return r is not None and r.retcode == mt5.TRADE_RETCODE_DONE


def _close_partial_local(ticket: int, volume: float) -> bool:
    if not connect(): return False
    pos = mt5.positions_get(ticket=ticket)
    if not pos: return False
    p  = pos[0]
    si = mt5.symbol_info(p.symbol)
    if not si: return False
    vol  = _normalize_volume(si, volume)
    if vol < si.volume_min: return False
    ot   = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(p.symbol)
    pr   = tick.bid if p.type == 0 else tick.ask
    req  = {"action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       p.symbol,
            "volume":       vol,
            "type":         ot,
            "position":     ticket,
            "price":        pr,
            "deviation":    20,
            "magic":        p.magic,
            "comment":      "YP PARTIAL",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": _filling_mode(si)}
    r = _send_with_fallback(req)
    return r is not None and r.retcode == mt5.TRADE_RETCODE_DONE


def _modify_sl_local(ticket: int, new_sl: float) -> bool:
    if not connect(): return False
    pos = mt5.positions_get(ticket=ticket)
    if not pos: return False
    p = pos[0]
    r = mt5.order_send({"action":   mt5.TRADE_ACTION_SLTP,
                         "symbol":   p.symbol,
                         "sl":       new_sl,
                         "tp":       p.tp,
                         "position": ticket})
    return r is not None and r.retcode == mt5.TRADE_RETCODE_DONE


def _positions_local(symbol=None) -> list:
    if not connect(): return []
    pos = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    return list(pos) if pos else []


def _parallel_close(positions, max_workers=8, retries=1) -> int:
    """Close multiple positions in parallel. Retries once for any missed."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not positions:
        return 0

    def close_one(p):
        ticket = p.ticket if hasattr(p, 'ticket') else p["ticket"]
        return _close_local(ticket, pos_data=p)

    closed = 0
    with ThreadPoolExecutor(max_workers=min(len(positions), max_workers)) as ex:
        futures = {ex.submit(close_one, p): p for p in positions}
        for future in as_completed(futures):
            try:
                if future.result():
                    closed += 1
            except Exception as e:
                Logger.error(f"parallel close error: {e}")

    # Retry once for any that failed
    if retries > 0:
        remaining = _positions_local(
            positions[0].symbol if hasattr(positions[0],'symbol')
            else positions[0]["symbol"] if len(positions)==1 else None
        )
        if remaining:
            Logger.warning(f"Retrying {len(remaining)} unclosed positions")
            closed += _parallel_close(remaining, max_workers, retries=0)

    return closed


def close_all(symbol=None) -> int:
    if _use_remote():
        return _remote_call({"action":"close_all","symbol":symbol}).get("closed",0)
    positions = _positions_local(symbol)
    if not positions: return 0
    Logger.info(f"Closing ALL {len(positions)} positions (parallel)")
    return _parallel_close(positions)

close_all_positions = close_all


def close_losing(symbol=None) -> int:
    if _use_remote():
        return _remote_call({"action":"close_losing","symbol":symbol}).get("closed",0)
    positions = [p for p in _positions_local(symbol) if p.profit < 0]
    if not positions: return 0
    Logger.info(f"Closing {len(positions)} losing positions (parallel)")
    return _parallel_close(positions)


def close_profitable(symbol=None) -> int:
    if _use_remote():
        return _remote_call({"action":"close_profitable","symbol":symbol}).get("closed",0)
    positions = [p for p in _positions_local(symbol) if p.profit > 0]
    if not positions: return 0
    Logger.info(f"Closing {len(positions)} profitable positions (parallel)")
    return _parallel_close(positions)


def move_sl_to_be(symbol=None) -> int:
    positions = get_open_positions(symbol)
    moved = 0
    for p in positions:
        ticket     = p["ticket"]     if isinstance(p, dict) else p.ticket
        sl         = p["sl"]         if isinstance(p, dict) else p.sl
        price_open = p["price_open"] if isinstance(p, dict) else p.price_open
        ptype      = p["type"]       if isinstance(p, dict) else p.type
        sym        = p["symbol"]     if isinstance(p, dict) else p.symbol
        is_buy     = ptype == 0
        si = mt5.symbol_info(sym) if mt5 else None
        digits = si.digits if si else 2
        new_sl = round(price_open, digits)
        if is_buy  and (sl == 0 or sl < price_open):
            if _use_remote():
                if _remote_call({"action":"modify_sl","ticket":ticket,"new_sl":new_sl}).get("success"): moved+=1
            elif _modify_sl_local(ticket, new_sl): moved+=1
        elif not is_buy and (sl == 0 or sl > price_open):
            if _use_remote():
                if _remote_call({"action":"modify_sl","ticket":ticket,"new_sl":new_sl}).get("success"): moved+=1
            elif _modify_sl_local(ticket, new_sl): moved+=1
    return moved


def partial_close_pct(pct: float, symbol=None) -> int:
    from src.config import get
    mode      = get("close_mode", "volume")
    positions = get_open_positions(symbol)
    if not positions: return 0

    if mode == "count":
        n_close    = max(1, round(len(positions) * pct / 100.0))
        sorted_pos = sorted(positions,
                            key=lambda p: p["profit"] if isinstance(p,dict) else p.profit)
        to_close = sorted_pos[:n_close]
        if _use_remote():
            closed = 0
            for p in to_close:
                ticket = p["ticket"] if isinstance(p,dict) else p.ticket
                if _remote_call({"action":"close","ticket":ticket}).get("success"): closed+=1
            return closed
        Logger.info(f"Count-close {pct}%: closing {n_close}/{len(positions)} (parallel)")
        return _parallel_close(to_close)
    else:
        # Volume mode: partial close each position in parallel
        from concurrent.futures import ThreadPoolExecutor, as_completed
        closed = 0
        def partial_one(p):
            ticket = p["ticket"] if isinstance(p,dict) else p.ticket
            volume = p["volume"] if isinstance(p,dict) else p.volume
            vol    = volume * pct / 100.0
            if _use_remote():
                return _remote_call({"action":"close_partial","ticket":ticket,"volume":vol}).get("success",False)
            return _close_partial_local(ticket, vol)
        with ThreadPoolExecutor(max_workers=min(len(positions),8)) as ex:
            futures = [ex.submit(partial_one, p) for p in positions]
            for f in as_completed(futures):
                if f.result(): closed+=1
        return closed


def tighten_sl(symbol=None) -> int:
    positions = get_open_positions(symbol)
    moved = 0
    for p in positions:
        ticket     = p["ticket"]     if isinstance(p,dict) else p.ticket
        sl         = p["sl"]         if isinstance(p,dict) else p.sl
        price_open = p["price_open"] if isinstance(p,dict) else p.price_open
        ptype      = p["type"]       if isinstance(p,dict) else p.type
        sym        = p["symbol"]     if isinstance(p,dict) else p.symbol
        if sl == 0: continue
        si     = mt5.symbol_info(sym) if mt5 else None
        digits = si.digits if si else 2
        new_sl = round((price_open + sl) / 2.0, digits)
        is_buy = ptype == 0
        if is_buy  and new_sl > sl:
            if _use_remote(): _remote_call({"action":"modify_sl","ticket":ticket,"new_sl":new_sl})
            elif _modify_sl_local(ticket, new_sl): moved+=1
        elif not is_buy and new_sl < sl:
            if _use_remote(): _remote_call({"action":"modify_sl","ticket":ticket,"new_sl":new_sl})
            elif _modify_sl_local(ticket, new_sl): moved+=1
    return moved


def check_auto_be(be_pips: float, symbol=None) -> int:
    if not MT5_LOCAL: return 0
    positions = _positions_local(symbol)
    moved = 0
    for p in positions:
        si = mt5.symbol_info(p.symbol)
        if not si: continue
        pt        = si.point
        dg        = si.digits
        pip_size  = pt * (10 if dg in (5,3) else 1)
        is_buy    = p.type == 0
        tick      = mt5.symbol_info_tick(p.symbol)
        cur       = tick.bid if is_buy else tick.ask
        pips_prof = (cur - p.price_open)/pip_size if is_buy else (p.price_open - cur)/pip_size
        if pips_prof < be_pips: continue
        be        = round(p.price_open, dg)
        if (is_buy and p.sl >= be) or (not is_buy and 0 < p.sl <= be): continue
        if _modify_sl_local(p.ticket, be): moved+=1
    return moved


def update_trailing(trail_pips: float, step_pips: float, symbol=None) -> int:
    if not MT5_LOCAL or _use_remote(): return 0
    positions = _positions_local(symbol)
    moved = 0
    for p in positions:
        si = mt5.symbol_info(p.symbol)
        if not si: continue
        pt       = si.point; dg = si.digits
        pip_size = pt*(10 if dg in (5,3) else 1)
        trail    = trail_pips*pip_size; step = step_pips*pip_size
        is_buy   = p.type==0; tick = mt5.symbol_info_tick(p.symbol)
        if is_buy:
            ideal = round(tick.bid-trail, dg)
            if ideal <= p.sl: continue
            if p.sl > 0 and ideal-p.sl < step: continue
        else:
            ideal = round(tick.ask+trail, dg)
            if p.sl > 0 and ideal >= p.sl: continue
            if p.sl > 0 and p.sl-ideal < step: continue
        if _modify_sl_local(p.ticket, ideal): moved+=1
    return moved
