"""
mt5_bridge.py — YALLA PIPS
All MetaTrader 5 trade operations.
"""
import MetaTrader5 as mt5
import logging

Logger = logging.getLogger("yp")


def connect() -> bool:
    if mt5.terminal_info() is not None:
        return True
    if not mt5.initialize():
        Logger.error(f"MT5 initialize() failed: {mt5.last_error()}")
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
        "margin":   round(info.margin, 2),
        "currency": info.currency,
        "server":   info.server,
        "login":    info.login,
    }


def get_open_positions(symbol: str = None) -> list:
    if not connect():
        return []
    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    return list(positions) if positions else []


def place_order(order_type, symbol, lots, sl_points, tp_points, magic, comment=""):
    if not connect():
        return {"success": False, "error": "MT5 not connected"}
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return {"success": False, "error": f"Symbol {symbol} not found"}
    point  = symbol_info.point
    digits = symbol_info.digits
    if order_type == mt5.ORDER_TYPE_BUY:
        price = mt5.symbol_info_tick(symbol).ask
        sl = round(price - sl_points * point, digits) if sl_points else 0.0
        tp = round(price + tp_points * point, digits) if tp_points else 0.0
    else:
        price = mt5.symbol_info_tick(symbol).bid
        sl = round(price + sl_points * point, digits) if sl_points else 0.0
        tp = round(price - tp_points * point, digits) if tp_points else 0.0
    request = {
        "action":      mt5.TRADE_ACTION_DEAL,
        "symbol":      symbol,
        "volume":      lots,
        "type":        order_type,
        "price":       price,
        "sl":          sl,
        "tp":          tp,
        "deviation":   20,
        "magic":       magic,
        "comment":     comment or "YP KB",
        "type_time":   mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        Logger.info(f"Order placed: {lots} {symbol} @ {price}")
        return {"success": True, "ticket": result.order, "price": price}
    Logger.error(f"Order failed: {result.retcode} {result.comment}")
    return {"success": False, "error": f"{result.retcode}: {result.comment}"}


def buy(symbol, lots, sl_points, tp_points, magic):
    return place_order(mt5.ORDER_TYPE_BUY, symbol, lots, sl_points, tp_points, magic, "YP BUY")


def sell(symbol, lots, sl_points, tp_points, magic):
    return place_order(mt5.ORDER_TYPE_SELL, symbol, lots, sl_points, tp_points, magic, "YP SELL")


def close_position(ticket: int) -> bool:
    if not connect():
        return False
    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        return False
    p          = pos[0]
    order_type = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
    price      = mt5.symbol_info_tick(p.symbol).bid if p.type == 0 else mt5.symbol_info_tick(p.symbol).ask
    req = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       p.symbol,
        "volume":       p.volume,
        "type":         order_type,
        "position":     ticket,
        "price":        price,
        "deviation":    20,
        "magic":        p.magic,
        "comment":      "YP CLOSE",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    result = mt5.order_send(req)
    return result.retcode == mt5.TRADE_RETCODE_DONE


def close_partial(ticket: int, volume: float) -> bool:
    if not connect():
        return False
    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        return False
    p        = pos[0]
    sym_info = mt5.symbol_info(p.symbol)
    lot_step = sym_info.volume_step
    min_lot  = sym_info.volume_min
    vol = round(round(volume / lot_step) * lot_step, 8)
    if vol < min_lot:
        Logger.error(f"Partial close {vol} below min lot {min_lot}")
        return False
    order_type = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
    price      = mt5.symbol_info_tick(p.symbol).bid if p.type == 0 else mt5.symbol_info_tick(p.symbol).ask
    req = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       p.symbol,
        "volume":       vol,
        "type":         order_type,
        "position":     ticket,
        "price":        price,
        "deviation":    20,
        "magic":        p.magic,
        "comment":      "YP PARTIAL",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    result = mt5.order_send(req)
    return result.retcode == mt5.TRADE_RETCODE_DONE


def modify_sl(ticket: int, new_sl: float) -> bool:
    if not connect():
        return False
    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        return False
    p = pos[0]
    req = {
        "action":   mt5.TRADE_ACTION_SLTP,
        "symbol":   p.symbol,
        "sl":       new_sl,
        "tp":       p.tp,
        "position": ticket,
    }
    result = mt5.order_send(req)
    return result.retcode == mt5.TRADE_RETCODE_DONE


def close_all(symbol: str = None) -> int:
    positions = get_open_positions(symbol)
    return sum(1 for p in positions if close_position(p.ticket))

# keep old name as alias
close_all_positions = close_all


def close_losing(symbol: str = None) -> int:
    positions = get_open_positions(symbol)
    return sum(1 for p in positions if p.profit < 0 and close_position(p.ticket))


def close_profitable(symbol: str = None) -> int:
    positions = get_open_positions(symbol)
    return sum(1 for p in positions if p.profit > 0 and close_position(p.ticket))


def move_sl_to_be(symbol: str = None) -> int:
    positions = get_open_positions(symbol)
    moved = 0
    for p in positions:
        digits = mt5.symbol_info(p.symbol).digits
        new_sl = round(p.price_open, digits)
        is_buy = p.type == 0
        if is_buy  and (p.sl == 0 or p.sl < p.price_open):
            if modify_sl(p.ticket, new_sl): moved += 1
        elif not is_buy and (p.sl == 0 or p.sl > p.price_open):
            if modify_sl(p.ticket, new_sl): moved += 1
    return moved


def partial_close_pct(pct: float, symbol: str = None) -> int:
    """
    Close pct% of open positions.

    Mode is read from config each call (no restart needed):
      'volume' — partial-close each position by pct% of its lot size.
                 Best for large lots (e.g. 1.0 lot → close 0.25 lot).
      'count'  — fully close pct% of positions by count.
                 Best for grids with minimum lots (e.g. 20 × 0.01 entries,
                 Close 25% = close 5 positions fully).
                 Closes the most-losing positions first.
    """
    from src.config import get
    mode      = get("close_mode", "volume")
    positions = get_open_positions(symbol)
    if not positions:
        return 0

    if mode == "count":
        # ── Count mode: close X% of positions by number ──────────
        n_close = max(1, round(len(positions) * pct / 100.0))
        # Sort: close most-losing positions first
        sorted_pos = sorted(positions, key=lambda p: p.profit)
        closed = 0
        for p in sorted_pos[:n_close]:
            if close_position(p.ticket):
                closed += 1
        Logger.info(f"Count-close {pct}%: closed {closed}/{n_close} of {len(positions)} positions")
        return closed

    else:
        # ── Volume mode: partial-close each position by pct% ─────
        closed = 0
        for p in positions:
            vol = p.volume * pct / 100.0
            if close_partial(p.ticket, vol):
                closed += 1
        return closed


def tighten_sl(symbol: str = None) -> int:
    positions = get_open_positions(symbol)
    moved = 0
    for p in positions:
        if p.sl == 0:
            continue
        digits = mt5.symbol_info(p.symbol).digits
        new_sl = round((p.price_open + p.sl) / 2.0, digits)
        is_buy = p.type == 0
        if is_buy  and new_sl > p.sl:
            if modify_sl(p.ticket, new_sl): moved += 1
        elif not is_buy and new_sl < p.sl:
            if modify_sl(p.ticket, new_sl): moved += 1
    return moved


def check_auto_be(be_pips: float, symbol: str = None) -> int:
    positions = get_open_positions(symbol)
    moved = 0
    for p in positions:
        sym_info = mt5.symbol_info(p.symbol)
        if sym_info is None:
            continue
        point      = sym_info.point
        digits     = sym_info.digits
        pip_factor = 10 if digits in (5, 3) else 1
        pip_size   = point * pip_factor
        is_buy     = p.type == 0
        tick       = mt5.symbol_info_tick(p.symbol)
        cur_price  = tick.bid if is_buy else tick.ask
        pips_profit = (cur_price - p.price_open) / pip_size if is_buy \
                      else (p.price_open - cur_price) / pip_size
        if pips_profit < be_pips:
            continue
        be_price   = round(p.price_open, digits)
        already_be = (is_buy and p.sl >= be_price) or \
                     (not is_buy and 0 < p.sl <= be_price)
        if already_be:
            continue
        if modify_sl(p.ticket, be_price):
            moved += 1
    return moved


def update_trailing(trail_pips: float, step_pips: float, symbol: str = None) -> int:
    positions = get_open_positions(symbol)
    moved = 0
    for p in positions:
        sym_info = mt5.symbol_info(p.symbol)
        if sym_info is None:
            continue
        point      = sym_info.point
        digits     = sym_info.digits
        pip_factor = 10 if digits in (5, 3) else 1
        pip_size   = point * pip_factor
        trail_dist = trail_pips * pip_size
        step_dist  = step_pips  * pip_size
        is_buy     = p.type == 0
        tick       = mt5.symbol_info_tick(p.symbol)
        if is_buy:
            ideal_sl = round(tick.bid - trail_dist, digits)
            if ideal_sl <= p.sl: continue
            if p.sl > 0 and ideal_sl - p.sl < step_dist: continue
        else:
            ideal_sl = round(tick.ask + trail_dist, digits)
            if p.sl > 0 and ideal_sl >= p.sl: continue
            if p.sl > 0 and p.sl - ideal_sl < step_dist: continue
        if modify_sl(p.ticket, ideal_sl):
            moved += 1
    return moved
