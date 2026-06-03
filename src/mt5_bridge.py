"""
mt5_bridge.py — YALLA PIPS Trading Keyboard
All MetaTrader 5 operations. Requires: pip install MetaTrader5
"""
import MetaTrader5 as mt5
import logging; Logger = logging.getLogger("yp")


def connect() -> bool:
    if mt5.terminal_info() is not None:
        return True
    if not mt5.initialize():
        Logger.error(f"MT5 init failed: {mt5.last_error()}")
        return False
    Logger.info(f"MT5 connected — {mt5.terminal_info().name}")
    return True


def get_account_info() -> dict:
    if not connect():
        return {}
    info = mt5.account_info()
    if info is None:
        return {}
    return {
        "balance":  round(info.balance, 2),
        "equity":   round(info.equity, 2),
        "profit":   round(info.profit, 2),
        "currency": info.currency,
        "login":    info.login,
    }


def get_open_positions(symbol: str = None) -> list:
    if not connect():
        return []
    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    return list(positions) if positions else []


def _place_order(order_type: int, symbol: str, lots: float,
                 sl_points: int, tp_points: int, magic: int, comment: str) -> dict:
    if not connect():
        return {"success": False, "error": "MT5 not connected"}
    sym = mt5.symbol_info(symbol)
    if sym is None:
        return {"success": False, "error": f"Symbol {symbol} not found"}
    point  = sym.point
    digits = sym.digits
    if order_type == mt5.ORDER_TYPE_BUY:
        price = mt5.symbol_info_tick(symbol).ask
        sl = round(price - sl_points * point, digits) if sl_points else 0.0
        tp = round(price + tp_points * point, digits) if tp_points else 0.0
    else:
        price = mt5.symbol_info_tick(symbol).bid
        sl = round(price + sl_points * point, digits) if sl_points else 0.0
        tp = round(price - tp_points * point, digits) if tp_points else 0.0
    req = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       lots,
        "type":         order_type,
        "price":        price,
        "sl":           sl,
        "tp":           tp,
        "deviation":    20,
        "magic":        magic,
        "comment":      comment,
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    result = mt5.order_send(req)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        return {"success": True, "ticket": result.order, "price": price}
    return {"success": False, "error": f"{result.retcode}: {result.comment}"}


def buy(symbol, lots, sl_points, tp_points, magic):
    return _place_order(mt5.ORDER_TYPE_BUY,  symbol, lots, sl_points, tp_points, magic, "YP BUY")


def sell(symbol, lots, sl_points, tp_points, magic):
    return _place_order(mt5.ORDER_TYPE_SELL, symbol, lots, sl_points, tp_points, magic, "YP SELL")


def _close(ticket: int) -> bool:
    if not connect():
        return False
    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        return False
    p = pos[0]
    otype = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
    price = mt5.symbol_info_tick(p.symbol).bid if p.type == 0 else mt5.symbol_info_tick(p.symbol).ask
    req = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       p.symbol,
        "volume":       p.volume,
        "type":         otype,
        "position":     ticket,
        "price":        price,
        "deviation":    20,
        "magic":        p.magic,
        "comment":      "YP CLOSE",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    return mt5.order_send(req).retcode == mt5.TRADE_RETCODE_DONE


def _close_partial(ticket: int, volume: float) -> bool:
    if not connect():
        return False
    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        return False
    p = pos[0]
    sym = mt5.symbol_info(p.symbol)
    step = sym.volume_step
    vol  = round(round(volume / step) * step, 8)
    if vol < sym.volume_min:
        return False
    otype = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
    price = mt5.symbol_info_tick(p.symbol).bid if p.type == 0 else mt5.symbol_info_tick(p.symbol).ask
    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol,
        "volume": vol, "type": otype, "position": ticket,
        "price": price, "deviation": 20, "magic": p.magic,
        "comment": "YP PARTIAL", "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    return mt5.order_send(req).retcode == mt5.TRADE_RETCODE_DONE


def _modify_sl(ticket: int, new_sl: float) -> bool:
    if not connect():
        return False
    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        return False
    p = pos[0]
    req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": p.symbol,
           "sl": new_sl, "tp": p.tp, "position": ticket}
    return mt5.order_send(req).retcode == mt5.TRADE_RETCODE_DONE


# ── High-level functions ──────────────────────────────────────────

def close_all(symbol=None) -> int:
    return sum(1 for p in get_open_positions(symbol) if _close(p.ticket))


def close_losing(symbol=None) -> int:
    return sum(1 for p in get_open_positions(symbol) if p.profit < 0 and _close(p.ticket))


def close_profitable(symbol=None) -> int:
    return sum(1 for p in get_open_positions(symbol) if p.profit > 0 and _close(p.ticket))


def move_sl_to_be(symbol=None) -> int:
    moved = 0
    for p in get_open_positions(symbol):
        digits  = mt5.symbol_info(p.symbol).digits
        be_sl   = round(p.price_open, digits)
        is_buy  = p.type == 0
        needs   = (is_buy and (p.sl == 0 or p.sl < be_sl)) or \
                  (not is_buy and (p.sl == 0 or p.sl > be_sl))
        if needs and _modify_sl(p.ticket, be_sl):
            moved += 1
    return moved


def partial_close_pct(pct: float, symbol=None) -> int:
    return sum(1 for p in get_open_positions(symbol)
               if _close_partial(p.ticket, p.volume * pct / 100.0))


def tighten_sl(symbol=None) -> int:
    moved = 0
    for p in get_open_positions(symbol):
        if p.sl == 0:
            continue
        digits = mt5.symbol_info(p.symbol).digits
        new_sl = round((p.price_open + p.sl) / 2.0, digits)
        is_buy = p.type == 0
        if is_buy and new_sl > p.sl and _modify_sl(p.ticket, new_sl):
            moved += 1
        elif not is_buy and new_sl < p.sl and _modify_sl(p.ticket, new_sl):
            moved += 1
    return moved


def check_auto_be(be_pips: float, symbol=None) -> int:
    moved = 0
    for p in get_open_positions(symbol):
        sym = mt5.symbol_info(p.symbol)
        if sym is None:
            continue
        pip_size = sym.point * (10 if sym.digits in (5, 3) else 1)
        is_buy   = p.type == 0
        tick     = mt5.symbol_info_tick(p.symbol)
        cur      = tick.bid if is_buy else tick.ask
        pips     = (cur - p.price_open) / pip_size if is_buy else (p.price_open - cur) / pip_size
        if pips < be_pips:
            continue
        be_sl   = round(p.price_open, sym.digits)
        already = (is_buy and p.sl >= be_sl) or (not is_buy and 0 < p.sl <= be_sl)
        if not already and _modify_sl(p.ticket, be_sl):
            moved += 1
    return moved


def update_trailing(trail_pips: float, step_pips: float, symbol=None) -> int:
    moved = 0
    for p in get_open_positions(symbol):
        sym = mt5.symbol_info(p.symbol)
        if sym is None:
            continue
        pip_size = sym.point * (10 if sym.digits in (5, 3) else 1)
        dist     = trail_pips * pip_size
        step     = step_pips  * pip_size
        is_buy   = p.type == 0
        tick     = mt5.symbol_info_tick(p.symbol)
        if is_buy:
            ideal = round(tick.bid - dist, sym.digits)
            if ideal <= p.sl:
                continue
            if p.sl > 0 and ideal - p.sl < step:
                continue
        else:
            ideal = round(tick.ask + dist, sym.digits)
            if p.sl > 0 and ideal >= p.sl:
                continue
            if p.sl > 0 and p.sl - ideal < step:
                continue
        if _modify_sl(p.ticket, ideal):
            moved += 1
    return moved
