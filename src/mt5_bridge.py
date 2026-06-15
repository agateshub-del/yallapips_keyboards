"""
mt5_bridge.py — YALLA PIPS
Auto-detects whether to use:
  - Direct MT5 Python API  (Windows with MT5 installed)
  - Remote bridge server   (macOS / Windows without MT5 / any platform)

Remote bridge: run tools/mt5_server.py on your Windows MT5 machine,
then set mt5_bridge_host + mt5_bridge_port in config.json.
"""
import sys
import json
import socket
import logging

Logger   = logging.getLogger("yp")
IS_WIN   = sys.platform == "win32"

# ── Try local MT5 ─────────────────────────────────────────────────
try:
    import MetaTrader5 as mt5
    MT5_LOCAL = True
except ImportError:
    mt5        = None
    MT5_LOCAL  = False
    if IS_WIN:
        Logger.warning("MetaTrader5 not installed. Install via: pip install MetaTrader5")
    else:
        Logger.info("macOS detected — will use remote MT5 bridge server.")


def _filling_mode(si):
    """
    Determine correct ORDER_FILLING mode for this symbol.
    si.filling_mode is a bitmask: bit0=FOK, bit1=IOC, bit2=RETURN
    """
    fm = si.filling_mode
    if fm & 1:  return mt5.ORDER_FILLING_FOK
    if fm & 2:  return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


def _send_with_fallback(request):
    """Try order_send, retrying with alternate filling modes on 10030."""
    r = mt5.order_send(request)
    if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
        return r
    if r is not None and r.retcode == 10030:  # Unsupported filling mode
        for fm in (mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN, mt5.ORDER_FILLING_FOK):
            request["type_filling"] = fm
            r2 = mt5.order_send(request)
            if r2 is not None and r2.retcode == mt5.TRADE_RETCODE_DONE:
                return r2
            if r2 is not None and r2.retcode != 10030:
                r = r2  # keep last non-filling error
    return r


# ══════════════════════════════════════════════════════════════════
# Remote bridge client
# ══════════════════════════════════════════════════════════════════
def _remote_call(cmd: dict) -> dict:
    """Send a command to the Windows MT5 bridge server."""
    from src.config import get
    host    = get("mt5_bridge_host", "")
    port    = int(get("mt5_bridge_port", 9999))
    timeout = float(get("mt5_bridge_timeout", 5.0))

    if not host:
        return {"error": "mt5_bridge_host not set. Open Settings and enter your Windows PC IP."}
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall((json.dumps(cmd) + "\n").encode())
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
            return json.loads(buf.split(b"\n")[0])
    except ConnectionRefusedError:
        return {"error": f"Cannot reach MT5 bridge at {host}:{port}. Is mt5_server.py running?"}
    except socket.timeout:
        return {"error": f"MT5 bridge timeout ({timeout}s). Check network / firewall."}
    except Exception as e:
        return {"error": str(e)}


def _use_remote() -> bool:
    """True if we should use the network bridge instead of local MT5."""
    if not MT5_LOCAL:
        return True
    from src.config import get
    host = get("mt5_bridge_host", "")
    return bool(host)   # if host is set, prefer remote even on Windows


# ══════════════════════════════════════════════════════════════════
# Local MT5 helpers (Windows direct)
# ══════════════════════════════════════════════════════════════════
def connect() -> bool:
    if not MT5_LOCAL: return False
    if mt5.terminal_info() is not None: return True
    if not mt5.initialize():
        Logger.error(f"MT5 init failed: {mt5.last_error()}"); return False
    Logger.info(f"MT5 connected: {mt5.terminal_info().name}"); return True


def _positions_local(symbol=None):
    if not connect(): return []
    pos = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    return list(pos) if pos else []


def _close_local(ticket):
    if not connect(): return False
    pos = mt5.positions_get(ticket=ticket)
    if not pos: return False
    p  = pos[0]
    ot = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
    pr = mt5.symbol_info_tick(p.symbol).bid if p.type == 0 else mt5.symbol_info_tick(p.symbol).ask
    si = mt5.symbol_info(p.symbol)
    req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol,
        "volume": p.volume, "type": ot, "position": ticket, "price": pr,
        "deviation": 20, "magic": p.magic, "comment": "YP CLOSE",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": _filling_mode(si) if si else mt5.ORDER_FILLING_IOC}
    r = _send_with_fallback(req)
    return r is not None and r.retcode == mt5.TRADE_RETCODE_DONE


def _close_partial_local(ticket, volume):
    if not connect(): return False
    pos = mt5.positions_get(ticket=ticket)
    if not pos: return False
    p = pos[0]; si = mt5.symbol_info(p.symbol)
    vol = round(round(volume / si.volume_step) * si.volume_step, 8)
    if vol < si.volume_min: return False
    ot = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
    pr = mt5.symbol_info_tick(p.symbol).bid if p.type == 0 else mt5.symbol_info_tick(p.symbol).ask
    req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol,
        "volume": vol, "type": ot, "position": ticket, "price": pr,
        "deviation": 20, "magic": p.magic, "comment": "YP PARTIAL",
        "type_time": mt5.ORDER_TIME_GTC, "type_filling": _filling_mode(si)}
    r = _send_with_fallback(req)
    return r is not None and r.retcode == mt5.TRADE_RETCODE_DONE


def _modify_sl_local(ticket, new_sl):
    if not connect(): return False
    pos = mt5.positions_get(ticket=ticket)
    if not pos: return False
    p = pos[0]
    r = mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "symbol": p.symbol,
                         "sl": new_sl, "tp": p.tp, "position": ticket})
    return r.retcode == mt5.TRADE_RETCODE_DONE


# ══════════════════════════════════════════════════════════════════
# Public API  (used by keyboard.py — same interface regardless of mode)
# ══════════════════════════════════════════════════════════════════
def get_account_info() -> dict:
    if _use_remote():
        result = _remote_call({"action": "account_info"})
        return result if "balance" in result else {}
    if not connect(): return {}
    info = mt5.account_info()
    if not info: return {}
    return {"balance": round(info.balance,2), "equity": round(info.equity,2),
            "profit": round(info.profit,2), "currency": info.currency,
            "server": info.server, "login": info.login}


def get_open_positions(symbol=None) -> list:
    if _use_remote():
        r = _remote_call({"action": "positions", "symbol": symbol})
        return r.get("positions", [])
    return _positions_local(symbol)


def buy(symbol, lots, sl_points, tp_points, magic):
    if _use_remote():
        return _remote_call({"action": "buy", "symbol": symbol, "lots": lots,
                              "sl_points": sl_points, "tp_points": tp_points, "magic": magic})
    try:
        if not connect(): return {"success": False, "error": "MT5 not connected"}
        si = mt5.symbol_info(symbol)
        if not si:
            return {"success": False, "error": f"Symbol '{symbol}' not found on this broker"}
        if not si.visible:
            if not mt5.symbol_select(symbol, True):
                return {"success": False, "error": f"Could not enable '{symbol}' in Market Watch"}
            si = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if not tick or tick.ask == 0:
            return {"success": False, "error": f"No price tick for '{symbol}' (market closed?)"}
        pt=si.point; dg=si.digits
        price=tick.ask
        sl=round(price-sl_points*pt,dg) if sl_points else 0.0
        tp=round(price+tp_points*pt,dg) if tp_points else 0.0
        request = {"action":mt5.TRADE_ACTION_DEAL,"symbol":symbol,"volume":lots,
            "type":mt5.ORDER_TYPE_BUY,"price":price,"sl":sl,"tp":tp,"deviation":20,
            "magic":magic,"comment":"YP BUY","type_time":mt5.ORDER_TIME_GTC,
            "type_filling":_filling_mode(si)}
        r = _send_with_fallback(request)
        if r is None:
            return {"success": False, "error": f"order_send failed: {mt5.last_error()}"}
        if r.retcode==mt5.TRADE_RETCODE_DONE: return {"success":True,"ticket":r.order,"price":price}
        return {"success":False,"error":f"{r.retcode}: {r.comment}"}
    except Exception as e:
        Logger.error(f"buy() error: {e}")
        return {"success": False, "error": str(e)}


def sell(symbol, lots, sl_points, tp_points, magic):
    if _use_remote():
        return _remote_call({"action": "sell", "symbol": symbol, "lots": lots,
                              "sl_points": sl_points, "tp_points": tp_points, "magic": magic})
    try:
        if not connect(): return {"success": False, "error": "MT5 not connected"}
        si = mt5.symbol_info(symbol)
        if not si:
            return {"success": False, "error": f"Symbol '{symbol}' not found on this broker"}
        if not si.visible:
            if not mt5.symbol_select(symbol, True):
                return {"success": False, "error": f"Could not enable '{symbol}' in Market Watch"}
            si = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if not tick or tick.bid == 0:
            return {"success": False, "error": f"No price tick for '{symbol}' (market closed?)"}
        pt=si.point; dg=si.digits
        price=tick.bid
        sl=round(price+sl_points*pt,dg) if sl_points else 0.0
        tp=round(price-tp_points*pt,dg) if tp_points else 0.0
        request = {"action":mt5.TRADE_ACTION_DEAL,"symbol":symbol,"volume":lots,
            "type":mt5.ORDER_TYPE_SELL,"price":price,"sl":sl,"tp":tp,"deviation":20,
            "magic":magic,"comment":"YP SELL","type_time":mt5.ORDER_TIME_GTC,
            "type_filling":_filling_mode(si)}
        r = _send_with_fallback(request)
        if r is None:
            return {"success": False, "error": f"order_send failed: {mt5.last_error()}"}
        if r.retcode==mt5.TRADE_RETCODE_DONE: return {"success":True,"ticket":r.order,"price":price}
        return {"success":False,"error":f"{r.retcode}: {r.comment}"}
    except Exception as e:
        Logger.error(f"sell() error: {e}")
        return {"success": False, "error": str(e)}


def close_all(symbol=None) -> int:
    if _use_remote():
        return _remote_call({"action": "close_all", "symbol": symbol}).get("closed", 0)
    return sum(1 for p in _positions_local(symbol) if _close_local(p.ticket))

close_all_positions = close_all


def close_losing(symbol=None) -> int:
    if _use_remote():
        return _remote_call({"action": "close_losing", "symbol": symbol}).get("closed", 0)
    return sum(1 for p in _positions_local(symbol) if p.profit < 0 and _close_local(p.ticket))


def close_profitable(symbol=None) -> int:
    if _use_remote():
        return _remote_call({"action": "close_profitable", "symbol": symbol}).get("closed", 0)
    return sum(1 for p in _positions_local(symbol) if p.profit > 0 and _close_local(p.ticket))


def move_sl_to_be(symbol=None) -> int:
    positions = get_open_positions(symbol)
    moved = 0
    for p in positions:
        ticket     = p["ticket"] if isinstance(p, dict) else p.ticket
        sl         = p["sl"]     if isinstance(p, dict) else p.sl
        price_open = p["price_open"] if isinstance(p, dict) else p.price_open
        ptype      = p["type"]   if isinstance(p, dict) else p.type
        sym        = p["symbol"] if isinstance(p, dict) else p.symbol
        is_buy     = ptype == 0
        if _use_remote():
            si_info = _remote_call({"action": "positions", "symbol": sym})
            digits  = 2
        else:
            si_info = mt5.symbol_info(sym)
            digits  = si_info.digits if si_info else 2
        new_sl = round(price_open, digits)
        if is_buy  and (sl == 0 or sl < price_open):
            if _use_remote():
                r = _remote_call({"action": "modify_sl", "ticket": ticket, "new_sl": new_sl})
                if r.get("success"): moved += 1
            elif _modify_sl_local(ticket, new_sl): moved += 1
        elif not is_buy and (sl == 0 or sl > price_open):
            if _use_remote():
                r = _remote_call({"action": "modify_sl", "ticket": ticket, "new_sl": new_sl})
                if r.get("success"): moved += 1
            elif _modify_sl_local(ticket, new_sl): moved += 1
    return moved


def partial_close_pct(pct: float, symbol=None) -> int:
    from src.config import get
    mode      = get("close_mode", "volume")
    positions = get_open_positions(symbol)
    if not positions: return 0

    if mode == "count":
        n_close    = max(1, round(len(positions) * pct / 100.0))
        sorted_pos = sorted(positions,
                            key=lambda p: p["profit"] if isinstance(p, dict) else p.profit)
        closed = 0
        for p in sorted_pos[:n_close]:
            ticket = p["ticket"] if isinstance(p, dict) else p.ticket
            if _use_remote():
                if _remote_call({"action": "close", "ticket": ticket}).get("success"): closed += 1
            elif _close_local(ticket): closed += 1
        return closed
    else:
        closed = 0
        for p in positions:
            ticket = p["ticket"] if isinstance(p, dict) else p.ticket
            volume = p["volume"] if isinstance(p, dict) else p.volume
            vol    = volume * pct / 100.0
            if _use_remote():
                if _remote_call({"action": "close_partial", "ticket": ticket, "volume": vol}).get("success"): closed += 1
            elif _close_partial_local(ticket, vol): closed += 1
        return closed


def tighten_sl(symbol=None) -> int:
    positions = get_open_positions(symbol)
    moved = 0
    for p in positions:
        ticket     = p["ticket"]     if isinstance(p, dict) else p.ticket
        sl         = p["sl"]         if isinstance(p, dict) else p.sl
        price_open = p["price_open"] if isinstance(p, dict) else p.price_open
        ptype      = p["type"]       if isinstance(p, dict) else p.type
        sym        = p["symbol"]     if isinstance(p, dict) else p.symbol
        if sl == 0: continue
        new_sl = round((price_open + sl) / 2.0, 2)
        is_buy = ptype == 0
        if is_buy  and new_sl > sl:
            if _use_remote():
                if _remote_call({"action":"modify_sl","ticket":ticket,"new_sl":new_sl}).get("success"): moved+=1
            elif _modify_sl_local(ticket, new_sl): moved += 1
        elif not is_buy and new_sl < sl:
            if _use_remote():
                if _remote_call({"action":"modify_sl","ticket":ticket,"new_sl":new_sl}).get("success"): moved+=1
            elif _modify_sl_local(ticket, new_sl): moved += 1
    return moved


def check_auto_be(be_pips: float, symbol=None) -> int:
    if not MT5_LOCAL and not _use_remote(): return 0
    positions = get_open_positions(symbol)
    moved = 0
    for p in positions:
        ticket     = p["ticket"]     if isinstance(p, dict) else p.ticket
        ptype      = p["type"]       if isinstance(p, dict) else p.type
        sl         = p["sl"]         if isinstance(p, dict) else p.sl
        price_open = p["price_open"] if isinstance(p, dict) else p.price_open
        sym        = p["symbol"]     if isinstance(p, dict) else p.symbol
        is_buy = ptype == 0
        if not _use_remote() and mt5:
            si       = mt5.symbol_info(sym)
            if not si: continue
            pt       = si.point; dg = si.digits
            pip_size = pt * (10 if si.digits in (5,3) else 1)
            tick     = mt5.symbol_info_tick(sym)
            cur      = tick.bid if is_buy else tick.ask
            pips     = (cur - price_open)/pip_size if is_buy else (price_open - cur)/pip_size
            if pips < be_pips: continue
            be = round(price_open, dg)
            if (is_buy and sl >= be) or (not is_buy and 0 < sl <= be): continue
            if _modify_sl_local(ticket, be): moved += 1
    return moved


def update_trailing(trail_pips: float, step_pips: float, symbol=None) -> int:
    if not MT5_LOCAL or _use_remote(): return 0   # trailing needs tick data locally
    positions = _positions_local(symbol)
    moved = 0
    for p in positions:
        si = mt5.symbol_info(p.symbol)
        if not si: continue
        pt=si.point; dg=si.digits
        pip_size=pt*(10 if dg in (5,3) else 1)
        trail=trail_pips*pip_size; step=step_pips*pip_size
        is_buy=p.type==0; tick=mt5.symbol_info_tick(p.symbol)
        if is_buy:
            ideal=round(tick.bid-trail,dg)
            if ideal<=p.sl: continue
            if p.sl>0 and ideal-p.sl<step: continue
        else:
            ideal=round(tick.ask+trail,dg)
            if p.sl>0 and ideal>=p.sl: continue
            if p.sl>0 and p.sl-ideal<step: continue
        if _modify_sl_local(p.ticket, ideal): moved+=1
    return moved
