"""
key_renderer.py — YALLA PIPS
Generates PIL images for all 15 keys + long display strip.
Key size: 96×96 px (hardware native for MiraBox StreamDock).
"""
import io
import datetime
from PIL import Image, ImageDraw, ImageFont

# ── Colour palette ────────────────────────────────────────────────
C_BG       = (10, 12, 18)
C_WHITE    = (230, 230, 230)
C_GOLD     = (255, 214, 0)
C_GREEN    = (0, 210, 100)
C_RED      = (240, 30, 60)
C_ORANGE   = (255, 109, 0)
C_BLUE     = (41, 121, 255)
C_CYAN     = (0, 220, 255)
C_PURPLE   = (180, 80, 255)
C_PINK     = (245, 0, 87)
C_YELLOW   = (255, 214, 0)
C_GREY     = (70, 70, 90)
C_NAVY     = (20, 30, 50)

SIZE = 96


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        f"C:/Windows/Fonts/{'arialbd.ttf' if bold else 'arial.ttf'}",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans{}.ttf".format("-Bold" if bold else ""),
        "/usr/share/fonts/truetype/liberation/LiberationSans{}-Regular.ttf".format("-Bold" if bold else ""),
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _base(bg=C_BG) -> tuple:
    img  = Image.new("RGB", (SIZE, SIZE), bg)
    draw = ImageDraw.Draw(img)
    return img, draw


def _label(draw, line1, color1, line2="", color2=C_WHITE,
           y1=30, y2=52, size1=18, size2=10):
    draw.text((SIZE//2, y1), line1, font=_font(size1, bold=True),
              fill=color1, anchor="mm")
    if line2:
        draw.text((SIZE//2, y2), line2, font=_font(size2), fill=color2, anchor="mm")


# ══ KEY 0 — BUY ══════════════════════════════════════════════════
def render_buy(price=""):
    img, draw = _base()
    draw.polygon([(48,8),(34,24),(40,24),(40,34),(56,34),(56,24),(62,24)], fill=C_GREEN)
    _label(draw, "BUY", C_GREEN, price, y1=52, y2=66, size1=20, size2=11)
    draw.rectangle([(0,0),(95,95)], outline=C_GREEN, width=2)
    return img

# ══ KEY 1 — SELL ═════════════════════════════════════════════════
def render_sell(price=""):
    img, draw = _base()
    draw.polygon([(48,70),(34,54),(40,54),(40,44),(56,44),(56,54),(62,54)], fill=C_RED)
    _label(draw, "SELL", C_RED, price, y1=28, y2=16, size1=20, size2=11)
    draw.rectangle([(0,0),(95,95)], outline=C_RED, width=2)
    return img

# ══ KEY 2 — CLOSE ALL ════════════════════════════════════════════
def render_close_all():
    img, draw = _base()
    draw.line([(16,14),(72,70)], fill=C_ORANGE, width=6)
    draw.line([(72,14),(16,70)], fill=C_ORANGE, width=6)
    _label(draw, "CLOSE", C_ORANGE, "ALL", y1=78, y2=88, size1=13, size2=11)
    draw.rectangle([(0,0),(95,95)], outline=C_ORANGE, width=2)
    return img

# ══ KEY 3 — CLOSE LOSING ═════════════════════════════════════════
def render_close_losing():
    img, draw = _base((18,5,5))
    draw.polygon([(48,68),(34,52),(40,52),(40,18),(56,18),(56,52),(62,52)], fill=C_RED)
    _label(draw, "LOSING", C_RED, "CLOSE", y1=10, y2=84, size1=13, size2=11)
    draw.rectangle([(0,0),(95,95)], outline=C_RED, width=2)
    return img

# ══ KEY 4 — CLOSE PROFIT ═════════════════════════════════════════
def render_close_profit():
    img, draw = _base((5,18,8))
    draw.polygon([(48,16),(34,32),(40,32),(40,66),(56,66),(56,32),(62,32)], fill=C_GREEN)
    _label(draw, "PROFIT", C_GREEN, "CLOSE", y1=82, y2=10, size1=13, size2=11)
    draw.rectangle([(0,0),(95,95)], outline=C_GREEN, width=2)
    return img

# ══ KEY 5 — SL TO BE ═════════════════════════════════════════════
def render_sl_to_be():
    img, draw = _base()
    draw.rectangle([(22,46),(74,68)], fill=C_BLUE)
    draw.arc([(26,28),(70,54)], 200, 340, fill=C_BLUE, width=6)
    draw.ellipse([(43,52),(53,62)], fill=C_BG)
    _label(draw, "SL→BE", C_BLUE, "BREAKEVEN", y1=80, y2=90, size1=14, size2=8)
    draw.rectangle([(0,0),(95,95)], outline=C_BLUE, width=2)
    return img

# ══ KEY 6 — CLOSE 25% ════════════════════════════════════════════
def render_close_25():
    img, draw = _base()
    r=26; cx,cy=48,38
    draw.arc([(cx-r,cy-r),(cx+r,cy+r)], 0, 360, fill=(40,40,40), width=10)
    draw.arc([(cx-r,cy-r),(cx+r,cy+r)], -90, 0,   fill=C_PURPLE,  width=10)
    draw.text((cx,cy), "25%", font=_font(16,bold=True), fill=C_PURPLE, anchor="mm")
    draw.text((48,76), "CLOSE", font=_font(12,bold=True), fill=C_PURPLE, anchor="mm")
    draw.rectangle([(0,0),(95,95)], outline=C_PURPLE, width=2)
    return img

# ══ KEY 7 — CLOSE 50% ════════════════════════════════════════════
def render_close_50():
    c=(160,110,255)
    img, draw = _base()
    r=26; cx,cy=48,38
    draw.arc([(cx-r,cy-r),(cx+r,cy+r)], 0, 360, fill=(40,40,40), width=10)
    draw.arc([(cx-r,cy-r),(cx+r,cy+r)], -90, 90,  fill=c, width=10)
    draw.text((cx,cy), "50%", font=_font(16,bold=True), fill=c, anchor="mm")
    draw.text((48,76), "CLOSE", font=_font(12,bold=True), fill=c, anchor="mm")
    draw.rectangle([(0,0),(95,95)], outline=c, width=2)
    return img

# ══ KEY 8 — CLOSE 75% ════════════════════════════════════════════
def render_close_75():
    c=(100,60,200)
    img, draw = _base()
    r=26; cx,cy=48,38
    draw.arc([(cx-r,cy-r),(cx+r,cy+r)], 0, 360, fill=(40,40,40), width=10)
    draw.arc([(cx-r,cy-r),(cx+r,cy+r)], -90, 180, fill=c, width=10)
    draw.text((cx,cy), "75%", font=_font(16,bold=True), fill=c, anchor="mm")
    draw.text((48,76), "CLOSE", font=_font(12,bold=True), fill=c, anchor="mm")
    draw.rectangle([(0,0),(95,95)], outline=c, width=2)
    return img

# ══ KEY 9 — AUTO BE ══════════════════════════════════════════════
def render_auto_be(on: bool, pips: int = 20):
    c = C_CYAN if on else C_GREY
    bg = (0,10,18) if on else C_BG
    img, draw = _base(bg)
    draw.text((48,16), "AUTO BE",  font=_font(13,bold=True), fill=c, anchor="mm")
    draw.text((48,44), "ON" if on else "OFF", font=_font(26,bold=True), fill=c, anchor="mm")
    draw.text((48,66), f"{pips} PIPS", font=_font(11), fill=c, anchor="mm")
    draw.text((48,80), "TRIGGER",  font=_font(9), fill=(c[0]//2,c[1]//2,c[2]//2), anchor="mm")
    draw.rectangle([(0,0),(95,95)], outline=c, width=2)
    return img

# ══ KEY 10 — PARTIAL SL ══════════════════════════════════════════
def render_partial_sl():
    img, draw = _base()
    draw.line([(8,22),(80,22)], fill=C_GREEN,  width=2)
    draw.text((84,19), "E",  font=_font(9), fill=C_GREEN)
    draw.line([(8,45),(80,45)], fill=C_YELLOW, width=2)
    draw.text((84,42), "½",  font=_font(9), fill=C_YELLOW)
    draw.line([(8,68),(80,68)], fill=C_RED,    width=1)
    draw.text((84,65), "SL", font=_font(9), fill=C_RED)
    draw.text((48,84), "PARTIAL SL", font=_font(11,bold=True), fill=C_YELLOW, anchor="mm")
    draw.rectangle([(0,0),(95,95)], outline=C_YELLOW, width=2)
    return img

# ══ KEY 11 — SL TRAILING ═════════════════════════════════════════
def render_trailing(on: bool, pips: int = 15):
    c = C_PINK if on else C_GREY
    bg = (18,0,8) if on else C_BG
    img, draw = _base(bg)
    draw.text((48,16), "TRAIL SL", font=_font(13,bold=True), fill=c, anchor="mm")
    draw.text((48,44), "ON" if on else "OFF", font=_font(26,bold=True), fill=c, anchor="mm")
    draw.text((48,66), f"{pips} PIPS", font=_font(11), fill=c, anchor="mm")
    draw.rectangle([(0,0),(95,95)], outline=c, width=2)
    return img

# ══ KEY 12 — TRADINGVIEW ═════════════════════════════════════════
def render_tradingview():
    c = (41,98,255)
    img, draw = _base((5,5,20))
    draw.ellipse([(18,10),(78,70)], outline=c, width=3)
    draw.text((48,40), "TV", font=_font(22,bold=True), fill=c, anchor="mm")
    draw.text((48,80), "TRADINGVIEW", font=_font(9), fill=c, anchor="mm")
    draw.text((48,90), ".COM",        font=_font(8), fill=(80,100,180), anchor="mm")
    draw.rectangle([(0,0),(95,95)], outline=c, width=2)
    return img

# ══ KEY 13 — FOREXFACTORY ════════════════════════════════════════
def render_forexfactory():
    c = C_ORANGE
    img, draw = _base((18,8,0))
    draw.text((48,18), "FF", font=_font(26,bold=True), fill=c, anchor="mm")
    draw.rectangle([(8,28),(88,68)], outline=c, width=2)
    for x in [36, 64]:
        draw.line([(x,28),(x,68)], fill=c, width=1)
    draw.line([(8,48),(88,48)], fill=c, width=1)
    draw.text((48,80), "FOREXFACTORY", font=_font(8), fill=c, anchor="mm")
    draw.rectangle([(0,0),(95,95)], outline=c, width=2)
    return img

# ══ KEY 14 — MT5 ═════════════════════════════════════════════════
def render_mt5(balance=0, equity=0, profit=0, currency="", connected=False):
    c = (68,138,255)
    img, draw = _base(C_NAVY)
    draw.text((48,12), "MT5", font=_font(16,bold=True), fill=c, anchor="mm")
    draw.line([(4,22),(92,22)], fill=(30,40,60), width=1)
    if connected:
        pc = C_GREEN if profit >= 0 else C_RED
        draw.text((48,36), f"BAL {balance:.0f}", font=_font(11), fill=C_WHITE, anchor="mm")
        draw.text((48,50), f"EQ  {equity:.0f}",  font=_font(11), fill=C_WHITE, anchor="mm")
        draw.text((48,66), f"P&L {profit:+.0f}", font=_font(13,bold=True), fill=pc, anchor="mm")
        draw.text((48,82), currency, font=_font(10), fill=(80,100,140), anchor="mm")
    else:
        draw.text((48,44), "NOT",       font=_font(14,bold=True), fill=C_RED, anchor="mm")
        draw.text((48,62), "CONNECTED", font=_font(11),           fill=C_RED, anchor="mm")
    draw.rectangle([(0,0),(95,95)], outline=c, width=2)
    return img

# ══ FEEDBACK FLASHES ═════════════════════════════════════════════
def render_flash_ok(label="DONE"):
    img, draw = _base((0,20,8))
    draw.text((48,30), "✓",   font=_font(36,bold=True), fill=C_GREEN, anchor="mm")
    draw.text((48,66), label, font=_font(13),            fill=C_GREEN, anchor="mm")
    draw.rectangle([(0,0),(95,95)], outline=C_GREEN, width=3)
    return img

def render_flash_err(msg="ERROR"):
    img, draw = _base((20,0,0))
    draw.text((48,30), "✗", font=_font(36,bold=True), fill=C_RED, anchor="mm")
    draw.text((48,66), msg, font=_font(11),            fill=C_RED, anchor="mm")
    draw.rectangle([(0,0),(95,95)], outline=C_RED, width=3)
    return img

# ══ LONG DISPLAY (key 18 — right strip) ══════════════════════════

# Trading session times in UTC
_SESSIONS = [
    ("SYDNEY",   22, 31,  (0, 200, 150)),    # 22:00–07:00
    ("TOKYO",     0, 21,  (100, 150, 255)),   # 00:00–09:00 (stored as 0-9 check below)
    ("LONDON",    8, 41,  (41, 121, 255)),    # 08:00–17:00
    ("NEW YORK", 13, 54,  (255, 130, 0)),     # 13:00–22:00
]

def _active_sessions(utc_now: datetime.datetime) -> list:
    h = utc_now.hour + utc_now.minute / 60.0
    active = []
    if h >= 22 or h < 7:
        active.append(("SYDNEY",   (0, 200, 150)))
    if 0 <= h < 9:
        active.append(("TOKYO",    (100, 150, 255)))
    if 8 <= h < 17:
        active.append(("LONDON",   (41, 121, 255)))
    if 13 <= h < 22:
        active.append(("NEW YORK", (255, 130, 0)))
    return active if active else [("CLOSED", (80, 80, 80))]


def render_long_display(profit: float = 0.0,
                        currency: str = "USD",
                        connected: bool = False) -> Image.Image:
    img  = Image.new("RGB", (96, 96), (8, 10, 16))
    draw = ImageDraw.Draw(img)

    utc_now   = datetime.datetime.now(datetime.timezone.utc)
    local_now = datetime.datetime.now()

    sessions  = _active_sessions(utc_now)
    sess_name, sess_color = sessions[-1]
    if len(sessions) > 1:
        sess_name = "/".join(s[0][:3] for s in sessions)

    # Session band (top)
    draw.rectangle([(0,0),(95,28)], fill=tuple(c//5 for c in sess_color))
    draw.ellipse([(4,8),(14,18)], fill=sess_color)
    draw.text((52, 14), sess_name, font=_font(11, bold=True),
              fill=sess_color, anchor="mm")
    draw.line([(0,29),(95,29)], fill=(30,35,50), width=1)

    # Time band (middle)
    draw.text((48, 46), local_now.strftime("%H:%M:%S"),
              font=_font(14, bold=True), fill=(210, 220, 240), anchor="mm")
    draw.text((48, 60), local_now.strftime("%d %b"),
              font=_font(9), fill=(100, 110, 130), anchor="mm")
    draw.line([(0,67),(95,67)], fill=(30,35,50), width=1)

    # P&L band (bottom)
    if connected:
        pc  = (0, 210, 100) if profit >= 0 else (240, 30, 60)
        sym = "▲" if profit >= 0 else "▼"
        draw.text((48, 80), f"{sym} {profit:+.2f}",
                  font=_font(12, bold=True), fill=pc, anchor="mm")
        draw.text((48, 91), currency,
                  font=_font(8), fill=(70,80,70), anchor="mm")
    else:
        draw.text((48, 82), "MT5 OFF",
                  font=_font(10), fill=(80,40,40), anchor="mm")

    draw.rectangle([(0,0),(95,95)], outline=sess_color, width=2)
    return img
