"""
key_renderer.py — YALLA PIPS Trading Keyboard
Professional commercial key designs.
Copyright © 2026 YALLA PIPS (@YallaPips). All rights reserved.
"""
import io
import datetime
from PIL import Image, ImageDraw, ImageFont

# ── YALLA PIPS Brand Palette ──────────────────────────────────────
GOLD    = (255, 214,   0)
GREEN   = (  0, 210, 100)
RED     = (230,  40,  60)
ORANGE  = (255, 110,   0)
BLUE    = ( 41, 121, 255)
CYAN    = (  0, 200, 220)
PURPLE  = (160,  80, 240)
YELLOW  = (255, 220,  20)
PINK    = (240,  50, 120)
WHITE   = (230, 230, 235)
BG      = (  8,  10,  16)   # key background

SIZE = 96


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        f"C:/Windows/Fonts/{'arialbd.ttf' if bold else 'arial.ttf'}",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans{}.ttf".format("-Bold" if bold else ""),
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _base(bg=BG):
    img  = Image.new("RGB", (SIZE, SIZE), bg)
    draw = ImageDraw.Draw(img)
    return img, draw


def _border(draw, color, width=2):
    draw.rectangle([(0,0),(95,95)], outline=color, width=width)


def _yp_mark(draw, color):
    """Subtle YALLA PIPS watermark bottom-right."""
    r,g,b = color
    draw.text((90,90), "YP", font=_font(7,True),
              fill=(r//3, g//3, b//3), anchor="rm")


def _fit(draw, text, max_w, max_size, bold=False):
    for size in range(max_size, 7, -1):
        f  = _font(size, bold)
        bb = draw.textbbox((0,0), text, font=f)
        if (bb[2]-bb[0]) <= max_w:
            return f
    return _font(8, bold)


# ══════════════════════════════════════════════════════════════════
# STARTUP SPLASH — shown on all keys before trading images load
# ══════════════════════════════════════════════════════════════════
def render_splash(key_num: int = 0) -> Image.Image:
    """Gold-bordered YALLA PIPS loading screen shown on startup."""
    img, draw = _base()
    draw.rectangle([(0,0),(95,95)], fill=( 6, 8,14))
    draw.rectangle([(0,0),(95,95)], outline=GOLD, width=2)
    draw.rectangle([(3,3),(92,92)], outline=(80,65, 0), width=1)
    draw.text((48,30), "YP",         font=_font(28,True), fill=GOLD,        anchor="mm")
    draw.text((48,56), "YALLA PIPS", font=_font(10,True), fill=GOLD,        anchor="mm")
    draw.text((48,70), "@YallaPips", font=_font(9),       fill=(120,100, 0), anchor="mm")
    draw.text((48,82), "XAUUSD",     font=_font(8),       fill=( 80, 65, 0), anchor="mm")
    return img


# ══════════════════════════════════════════════════════════════════
# TRADING KEYS
# ══════════════════════════════════════════════════════════════════

def render_buy(price: str = "") -> Image.Image:
    img, draw = _base(( 0, 22, 10))
    draw.polygon([(48,6),(29,26),(38,26),(38,44),(58,44),(58,26),(67,26)], fill=GREEN)
    draw.text((48,62), "BUY",  font=_font(22,True), fill=GREEN,       anchor="mm")
    draw.text((48,78), price or "XAUUSD", font=_font(10),fill=(0,130,60), anchor="mm")
    _border(draw, GREEN); _yp_mark(draw, GREEN)
    return img


def render_sell(price: str = "") -> Image.Image:
    img, draw = _base((22,  4,  6))
    draw.polygon([(48,82),(29,62),(38,62),(38,44),(58,44),(58,62),(67,62)], fill=RED)
    draw.text((48,28), "SELL", font=_font(22,True), fill=RED,          anchor="mm")
    draw.text((48,14), price or "XAUUSD", font=_font(10),fill=(150,25,35), anchor="mm")
    _border(draw, RED); _yp_mark(draw, RED)
    return img


def render_close_all() -> Image.Image:
    img, draw = _base((22, 12,  0))
    draw.line([(14,14),(72,72)], fill=ORANGE, width=7)
    draw.line([(72,14),(14,72)], fill=ORANGE, width=7)
    draw.text((48,82), "CLOSE ALL", font=_font(11,True), fill=ORANGE,  anchor="mm")
    _border(draw, ORANGE); _yp_mark(draw, ORANGE)
    return img


def render_close_losing() -> Image.Image:
    img, draw = _base((22,  4,  6))
    draw.polygon([(48,70),(30,52),(38,52),(38,14),(58,14),(58,52),(66,52)], fill=RED)
    draw.text((48, 8), "CLOSE",  font=_font(11,True), fill=RED,        anchor="mm")
    draw.text((48,82), "LOSING", font=_font(14,True), fill=RED,        anchor="mm")
    _border(draw, RED); _yp_mark(draw, RED)
    return img


def render_close_profit() -> Image.Image:
    img, draw = _base(( 0, 22, 10))
    draw.polygon([(48,14),(30,32),(38,32),(38,70),(58,70),(58,32),(66,32)], fill=GREEN)
    draw.text((48, 8), "CLOSE",  font=_font(11,True), fill=GREEN,      anchor="mm")
    draw.text((48,82), "PROFIT", font=_font(14,True), fill=GREEN,      anchor="mm")
    _border(draw, GREEN); _yp_mark(draw, GREEN)
    return img


def render_sl_to_be() -> Image.Image:
    img, draw = _base(( 5, 10, 22))
    draw.rectangle([(18,46),(78,62)], fill=BLUE)
    draw.arc([(22,24),(74,56)], 200, 340, fill=BLUE, width=6)
    draw.ellipse([(43,52),(53,62)], fill=BG)
    draw.text((48,14), "SL → BE",    font=_font(14,True), fill=BLUE,   anchor="mm")
    draw.text((48,80), "BREAKEVEN",  font=_font(10),       fill=BLUE,   anchor="mm")
    _border(draw, BLUE); _yp_mark(draw, BLUE)
    return img


def render_close_25() -> Image.Image:
    c = PURPLE
    img, draw = _base()
    r=28; cx,cy=48,40
    draw.arc([(cx-r,cy-r),(cx+r,cy+r)], 0,360, fill=(35,20,50), width=11)
    draw.arc([(cx-r,cy-r),(cx+r,cy+r)], -90, 0, fill=c, width=11)
    draw.text((cx,cy), "25%", font=_font(15,True), fill=c, anchor="mm")
    draw.text((48,78), "CLOSE",      font=_font(13,True), fill=c, anchor="mm")
    _border(draw, c); _yp_mark(draw, c)
    return img


def render_close_50() -> Image.Image:
    c = (140, 90, 255)
    img, draw = _base()
    r=28; cx,cy=48,40
    draw.arc([(cx-r,cy-r),(cx+r,cy+r)], 0,360, fill=(30,18,50), width=11)
    draw.arc([(cx-r,cy-r),(cx+r,cy+r)], -90, 90, fill=c, width=11)
    draw.text((cx,cy), "50%", font=_font(15,True), fill=c, anchor="mm")
    draw.text((48,78), "CLOSE",      font=_font(13,True), fill=c, anchor="mm")
    _border(draw, c); _yp_mark(draw, c)
    return img


def render_close_75() -> Image.Image:
    c = (100, 50, 200)
    img, draw = _base()
    r=28; cx,cy=48,40
    draw.arc([(cx-r,cy-r),(cx+r,cy+r)], 0,360, fill=(22,12,40), width=11)
    draw.arc([(cx-r,cy-r),(cx+r,cy+r)], -90,180, fill=c, width=11)
    draw.text((cx,cy), "75%", font=_font(15,True), fill=c, anchor="mm")
    draw.text((48,78), "CLOSE",      font=_font(13,True), fill=c, anchor="mm")
    _border(draw, c); _yp_mark(draw, c)
    return img


def render_auto_be(on: bool, pips: int = 20) -> Image.Image:
    c  = CYAN if on else (60, 70, 80)
    bg = ( 0, 16, 20) if on else BG
    img, draw = _base(bg)
    draw.text((48,14), "AUTO BE",          font=_font(12,True), fill=c,   anchor="mm")
    draw.text((48,46), "ON" if on else "OFF", font=_font(28,True), fill=c, anchor="mm")
    draw.text((48,68), f"{pips} PIPS",     font=_font(11),       fill=c,   anchor="mm")
    draw.text((48,82), "TRIGGER",          font=_font(9),        fill=(c[0]//3,c[1]//3,c[2]//3), anchor="mm")
    _border(draw, c); _yp_mark(draw, c)
    return img


def render_partial_sl() -> Image.Image:
    c = YELLOW
    img, draw = _base()
    draw.line([(8,20),(80,20)],  fill=GREEN,  width=2)
    draw.text((84,17),"E",  font=_font(9), fill=GREEN)
    draw.line([(8,44),(80,44)],  fill=YELLOW, width=2)
    draw.text((84,41),"½", font=_font(9), fill=YELLOW)
    draw.line([(8,68),(80,68)],  fill=RED,    width=1)
    draw.text((84,65),"SL", font=_font(9), fill=RED)
    draw.text((48,84), "PARTIAL SL", font=_font(11,True), fill=c, anchor="mm")
    _border(draw, c); _yp_mark(draw, c)
    return img


def render_trailing(on: bool, pips: int = 15) -> Image.Image:
    c  = PINK if on else (60, 70, 80)
    bg = (20,  0, 12) if on else BG
    img, draw = _base(bg)
    draw.text((48,14), "TRAIL SL",         font=_font(13,True), fill=c,   anchor="mm")
    draw.text((48,46), "ON" if on else "OFF", font=_font(28,True), fill=c, anchor="mm")
    draw.text((48,68), f"{pips} PIPS",     font=_font(11),       fill=c,   anchor="mm")
    _border(draw, c); _yp_mark(draw, c)
    return img


def render_tradingview() -> Image.Image:
    c = BLUE
    img, draw = _base(( 4,  6, 20))
    draw.ellipse([(14, 8),(82,76)], outline=c, width=3)
    draw.text((48,42), "TV",          font=_font(24,True), fill=c,        anchor="mm")
    draw.text((48,80), "TRADINGVIEW", font=_font(9),       fill=c,        anchor="mm")
    draw.text((48,90), ".COM",        font=_font(8),       fill=(20,50,120), anchor="mm")
    _border(draw, c); _yp_mark(draw, c)
    return img


def render_forexfactory() -> Image.Image:
    c = ORANGE
    img, draw = _base((18,  8,  0))
    draw.text((48,18), "FF", font=_font(26,True), fill=c,     anchor="mm")
    draw.rectangle([( 8,28),(88,70)], outline=c, width=2)
    for x in [36, 62]:
        draw.line([(x,28),(x,70)], fill=c, width=1)
    draw.line([(8,49),(88,49)], fill=c, width=1)
    draw.text((48,82), "FOREXFACTORY", font=_font(8), fill=c, anchor="mm")
    _border(draw, c); _yp_mark(draw, c)
    return img


def render_mt5(balance=0, equity=0, profit=0,
               currency="", connected=False) -> Image.Image:
    c  = BLUE
    img, draw = _base(( 8, 12, 24))
    draw.text((48,12), "MT5", font=_font(16,True), fill=c,    anchor="mm")
    draw.line([(4,22),(92,22)], fill=(25,35,55), width=1)
    if connected:
        pc = GREEN if profit >= 0 else RED
        draw.text((48,36), f"BAL {balance:.0f}", font=_font(11),      fill=WHITE,  anchor="mm")
        draw.text((48,50), f"EQ  {equity:.0f}",  font=_font(11),      fill=WHITE,  anchor="mm")
        draw.text((48,66), f"P&L {profit:+.0f}", font=_font(13,True), fill=pc,     anchor="mm")
        draw.text((48,80), currency,              font=_font(10),      fill=(60,80,130), anchor="mm")
    else:
        draw.text((48,48), "NOT",       font=_font(14,True), fill=RED, anchor="mm")
        draw.text((48,64), "CONNECTED", font=_font(11),      fill=RED, anchor="mm")
    _border(draw, c); _yp_mark(draw, c)
    return img


# ── Feedback flashes ──────────────────────────────────────────────
def render_flash_ok(label="DONE") -> Image.Image:
    img, draw = _base(( 0, 20,  8))
    draw.text((48,34), "✓",   font=_font(36,True), fill=GREEN,  anchor="mm")
    draw.text((48,68), label, font=_font(13),       fill=GREEN,  anchor="mm")
    _border(draw, GREEN, 3)
    return img


def render_flash_err(msg="ERROR") -> Image.Image:
    img, draw = _base((20,  0,  0))
    draw.text((48,34), "✗", font=_font(36,True), fill=RED,   anchor="mm")
    draw.text((48,68), msg, font=_font(11),       fill=RED,   anchor="mm")
    _border(draw, RED, 3)
    return img


# ══════════════════════════════════════════════════════════════════
# LONG DISPLAY — three 96×96 panels (keys 16, 17, 18)
# ══════════════════════════════════════════════════════════════════
def _active_sessions(utc_now: datetime.datetime) -> list:
    h = utc_now.hour + utc_now.minute / 60.0
    s = []
    if h >= 22 or h < 7:  s.append(("SYDNEY",   (  0,200,150)))
    if 0 <= h  < 9:        s.append(("TOKYO",    (100,150,255)))
    if 8 <= h  < 17:       s.append(("LONDON",   ( 41,121,255)))
    if 13 <= h < 22:       s.append(("NEW YORK", (255,130,  0)))
    return s if s else [("CLOSED", (70,70,80))]


def render_long_display_panels(profit: float = 0.0,
                                currency: str = "USD",
                                connected: bool = False) -> list:
    """
    Returns [(16, img_session), (17, img_time), (18, img_pnl)]
    Key 16 = TOP panel, Key 17 = MIDDLE panel, Key 18 = BOTTOM panel.
    """
    utc_now   = datetime.datetime.now(datetime.timezone.utc)
    local_now = datetime.datetime.now()
    sessions  = _active_sessions(utc_now)
    sc        = sessions[-1][1]
    sn        = sessions[-1][0]
    if len(sessions) > 1:
        sn = "/".join(s[0][:3] for s in sessions)
    CX = 48

    def panel(bg):
        img  = Image.new("RGB", (96,96), bg)
        draw = ImageDraw.Draw(img)
        return img, draw

    def fit(draw, text, max_sz, bold=False):
        for sz in range(max_sz, 6, -1):
            f  = _font(sz, bold)
            bb = draw.textbbox((0,0), text, font=f)
            if (bb[2]-bb[0]) <= 88: return f
        return _font(6, bold)

    # ── Panel 1 (key 16): SESSION ─────────────────────────────────
    p1, d1 = panel(tuple(max(25,c//2) for c in sc))
    d1.rectangle([(0,0),(95,4)],   fill=sc)
    d1.rectangle([(0,91),(95,95)], fill=sc)
    d1.ellipse([(5,10),(17,22)], fill=sc)
    d1.text((CX,14), "SESSION",
            font=_font(10), fill=(200,210,225), anchor="mm")
    d1.text((CX,48), sn,
            font=fit(d1,sn,20,True), fill=(255,255,255), anchor="mm")
    d1.text((CX,70), utc_now.strftime("%H:%M"),
            font=_font(18,True), fill=(255,255,255), anchor="mm")
    d1.text((CX,84), "UTC",
            font=_font(10), fill=(180,190,210), anchor="mm")
    d1.text((90,90),"YP",font=_font(7,True),fill=(c//3 for c in sc),anchor="rm")

    # ── Panel 2 (key 17): LOCAL TIME ──────────────────────────────
    p2, d2 = panel((18, 24, 55))
    d2.rectangle([(0,0),(95,4)],   fill=( 55, 80,190))
    d2.rectangle([(0,91),(95,95)], fill=( 55, 80,190))
    d2.text((CX,14), "LOCAL TIME",
            font=_font(11), fill=(130,155,220), anchor="mm")
    d2.text((CX,48), local_now.strftime("%H:%M"),
            font=_font(26,True), fill=(255,255,255), anchor="mm")
    d2.text((CX,70), local_now.strftime(":%S"),
            font=_font(18,True), fill=(190,205,240), anchor="mm")
    d2.text((CX,84), local_now.strftime("%d %b %Y"),
            font=_font(9), fill=(120,140,200), anchor="mm")
    d2.text((90,90),"YP",font=_font(7,True),fill=(20,30,70),anchor="rm")

    # ── Panel 3 (key 18): OPEN P&L ───────────────────────────────
    if connected:
        pc  = (0,200,90) if profit>=0 else (210,35,55)
        p3, d3 = panel(tuple(max(22,c//2) for c in pc))
        d3.rectangle([(0,0),(95,4)],   fill=pc)
        d3.rectangle([(0,91),(95,95)], fill=pc)
        d3.text((CX,14), "OPEN P&L",
                font=_font(11), fill=(200,225,200), anchor="mm")
        d3.text((CX,46), "▲" if profit>=0 else "▼",
                font=_font(26,True), fill=(255,255,255), anchor="mm")
        d3.text((CX,70), f"{profit:+.2f}",
                font=fit(d3,f"{profit:+.2f}",18,True), fill=(255,255,255), anchor="mm")
        d3.text((CX,84), currency,
                font=_font(11), fill=(170,210,170), anchor="mm")
        d3.text((90,90),"YP",font=_font(7,True),fill=(0,40,20),anchor="rm")
    else:
        p3, d3 = panel((44,12,14))
        d3.rectangle([(0,0),(95,4)],   fill=(180,40,50))
        d3.rectangle([(0,91),(95,95)], fill=(180,40,50))
        d3.text((CX,38), "MT5",     font=_font(24,True), fill=(255, 80, 90), anchor="mm")
        d3.text((CX,65), "OFFLINE", font=_font(14),      fill=(200, 65, 75), anchor="mm")
        d3.text((48,83), "© YALLA PIPS", font=_font(7),  fill=(100,30,35), anchor="mm")

    return [(16, p1), (17, p2), (18, p3)]


def render_long_display(profit=0.0, currency="USD", connected=False):
    """Legacy — returns bottom panel only."""
    return render_long_display_panels(profit, currency, connected)[2][1]
