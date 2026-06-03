"""
key_renderer.py — YALLA PIPS Standalone
Generates PIL images for all 15 key displays.
Size: 72x72 px (hardware native).
"""
import io
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

SIZE = 72

def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    try:
        name = "arialbd.ttf" if bold else "arial.ttf"
        return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
    except Exception:
        return ImageFont.load_default()


def _base(bg=C_BG) -> tuple:
    img  = Image.new("RGB", (SIZE, SIZE), bg)
    draw = ImageDraw.Draw(img)
    return img, draw


def _label(draw, line1: str, color1: tuple, line2: str = "", color2=C_WHITE,
           y1: int = 30, y2: int = 52, size1: int = 18, size2: int = 10):
    draw.text((SIZE//2, y1), line1, font=_font(size1, bold=True), fill=color1, anchor="mm")
    if line2:
        draw.text((SIZE//2, y2), line2, font=_font(size2),         fill=color2, anchor="mm")


def _push_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════
#  KEY 0 — BUY
# ══════════════════════════════════════════════════════════════════
def render_buy(price: str = "") -> Image.Image:
    img, draw = _base()
    # Up arrow
    draw.polygon([(36,10),(22,26),(28,26),(28,35),(44,35),(44,26),(50,26)], fill=C_GREEN)
    _label(draw, "BUY", C_GREEN, price, y1=48, y2=62, size1=16, size2=9)
    draw.rectangle([(0,0),(71,71)], outline=C_GREEN, width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 1 — SELL
# ══════════════════════════════════════════════════════════════════
def render_sell(price: str = "") -> Image.Image:
    img, draw = _base()
    # Down arrow
    draw.polygon([(36,62),(22,46),(28,46),(28,37),(44,37),(44,46),(50,46)], fill=C_RED)
    _label(draw, "SELL", C_RED, price, y1=24, y2=13, size1=16, size2=9)
    draw.rectangle([(0,0),(71,71)], outline=C_RED, width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 2 — CLOSE ALL
# ══════════════════════════════════════════════════════════════════
def render_close_all() -> Image.Image:
    img, draw = _base()
    draw.line([(14,10),(58,54)], fill=C_ORANGE, width=5)
    draw.line([(58,10),(14,54)], fill=C_ORANGE, width=5)
    _label(draw, "CLOSE", C_ORANGE, "ALL", y1=60, y2=68, size1=11, size2=9)
    draw.rectangle([(0,0),(71,71)], outline=C_ORANGE, width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 3 — CLOSE LOSING
# ══════════════════════════════════════════════════════════════════
def render_close_losing() -> Image.Image:
    img, draw = _base((18, 5, 5))
    draw.polygon([(36,60),(24,46),(30,46),(30,16),(42,16),(42,46),(48,46)], fill=C_RED)
    _label(draw, "LOSING", C_RED, "CLOSE", y1=10, y2=66, size1=11, size2=9)
    draw.rectangle([(0,0),(71,71)], outline=C_RED, width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 4 — CLOSE PROFIT
# ══════════════════════════════════════════════════════════════════
def render_close_profit() -> Image.Image:
    img, draw = _base((5, 18, 8))
    draw.polygon([(36,12),(24,26),(30,26),(30,56),(42,56),(42,26),(48,26)], fill=C_GREEN)
    _label(draw, "PROFIT", C_GREEN, "CLOSE", y1=64, y2=8, size1=11, size2=9)
    draw.rectangle([(0,0),(71,71)], outline=C_GREEN, width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 5 — SL TO BE
# ══════════════════════════════════════════════════════════════════
def render_sl_to_be() -> Image.Image:
    img, draw = _base()
    # lock body
    draw.rectangle([(20,38),(52,58)], fill=C_BLUE)
    # shackle
    draw.arc([(22,24),(50,44)], 200, 340, fill=C_BLUE, width=5)
    # keyhole
    draw.ellipse([(33,42),(39,48)], fill=C_BG)
    _label(draw, "SL→BE", C_BLUE, "BREAKEVEN", y1=64, y2=68, size1=12, size2=7)
    draw.rectangle([(0,0),(71,71)], outline=C_BLUE, width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 6 — CLOSE 25%
# ══════════════════════════════════════════════════════════════════
def render_close_25() -> Image.Image:
    img, draw = _base()
    r = 22
    cx, cy = 36, 30
    # background circle
    draw.arc([(cx-r, cy-r),(cx+r, cy+r)], 0, 360, fill=(40,40,40), width=8)
    # 25% arc
    draw.arc([(cx-r, cy-r),(cx+r, cy+r)], -90, 0, fill=C_PURPLE, width=8)
    draw.text((cx, cy), "25%", font=_font(13, bold=True), fill=C_PURPLE, anchor="mm")
    draw.text((36, 60), "CLOSE", font=_font(10, bold=True), fill=C_PURPLE, anchor="mm")
    draw.rectangle([(0,0),(71,71)], outline=C_PURPLE, width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 7 — CLOSE 50%
# ══════════════════════════════════════════════════════════════════
def render_close_50() -> Image.Image:
    img, draw = _base()
    r = 22; cx, cy = 36, 30
    draw.arc([(cx-r, cy-r),(cx+r, cy+r)], 0, 360, fill=(40,40,40), width=8)
    draw.arc([(cx-r, cy-r),(cx+r, cy+r)], -90, 90, fill=(160,110,255), width=8)
    draw.text((cx, cy), "50%", font=_font(13, bold=True), fill=(160,110,255), anchor="mm")
    draw.text((36, 60), "CLOSE", font=_font(10, bold=True), fill=(160,110,255), anchor="mm")
    draw.rectangle([(0,0),(71,71)], outline=(160,110,255), width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 8 — CLOSE 75%
# ══════════════════════════════════════════════════════════════════
def render_close_75() -> Image.Image:
    img, draw = _base()
    r = 22; cx, cy = 36, 30
    draw.arc([(cx-r, cy-r),(cx+r, cy+r)], 0, 360, fill=(40,40,40), width=8)
    draw.arc([(cx-r, cy-r),(cx+r, cy+r)], -90, 180, fill=(100,60,200), width=8)
    draw.text((cx, cy), "75%", font=_font(13, bold=True), fill=(100,60,200), anchor="mm")
    draw.text((36, 60), "CLOSE", font=_font(10, bold=True), fill=(100,60,200), anchor="mm")
    draw.rectangle([(0,0),(71,71)], outline=(100,60,200), width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 9 — AUTO BE
# ══════════════════════════════════════════════════════════════════
def render_auto_be(on: bool, pips: int = 20) -> Image.Image:
    c = C_CYAN if on else C_GREY
    bg = (0, 10, 18) if on else C_BG
    img, draw = _base(bg)
    state = "ON" if on else "OFF"
    draw.text((36, 14), "AUTO BE", font=_font(11, bold=True), fill=c, anchor="mm")
    draw.text((36, 34), state,     font=_font(22, bold=True), fill=c, anchor="mm")
    draw.text((36, 52), f"{pips} PIPS",  font=_font(9),       fill=c, anchor="mm")
    draw.text((36, 64), "TRIGGER",       font=_font(8),        fill=(c[0]//2,c[1]//2,c[2]//2), anchor="mm")
    draw.rectangle([(0,0),(71,71)], outline=c, width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 10 — PARTIAL SL
# ══════════════════════════════════════════════════════════════════
def render_partial_sl() -> Image.Image:
    img, draw = _base()
    # entry line
    draw.line([(8,18),(64,18)], fill=C_GREEN, width=2)
    draw.text((66,15), "E", font=_font(7), fill=C_GREEN)
    # new SL line
    draw.line([(8,36),(64,36)], fill=C_YELLOW, width=2)
    draw.text((66,33), "½", font=_font(7), fill=C_YELLOW)
    # original SL line
    draw.line([(8,54),(64,54)], fill=C_RED, width=1)
    draw.text((66,51), "SL", font=_font(7), fill=C_RED)
    draw.text((36, 64), "PARTIAL SL", font=_font(9, bold=True), fill=C_YELLOW, anchor="mm")
    draw.rectangle([(0,0),(71,71)], outline=C_YELLOW, width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 11 — SL TRAILING
# ══════════════════════════════════════════════════════════════════
def render_trailing(on: bool, pips: int = 15) -> Image.Image:
    c = C_PINK if on else C_GREY
    bg = (18, 0, 8) if on else C_BG
    img, draw = _base(bg)
    state = "ON" if on else "OFF"
    draw.text((36, 14), "TRAIL SL", font=_font(11, bold=True), fill=c, anchor="mm")
    draw.text((36, 34), state,      font=_font(22, bold=True), fill=c, anchor="mm")
    draw.text((36, 52), f"{pips} PIPS",   font=_font(9),       fill=c, anchor="mm")
    draw.rectangle([(0,0),(71,71)], outline=c, width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 12 — TRADINGVIEW
# ══════════════════════════════════════════════════════════════════
def render_tradingview() -> Image.Image:
    c = (41, 98, 255)
    img, draw = _base((5, 5, 20))
    draw.ellipse([(14,8),(58,52)], outline=c, width=3)
    draw.text((36, 30), "TV", font=_font(18, bold=True), fill=c, anchor="mm")
    draw.text((36, 60), "TRADINGVIEW", font=_font(8), fill=c, anchor="mm")
    draw.text((36, 68), ".COM", font=_font(7), fill=(80,100,180), anchor="mm")
    draw.rectangle([(0,0),(71,71)], outline=c, width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 13 — FOREXFACTORY
# ══════════════════════════════════════════════════════════════════
def render_forexfactory() -> Image.Image:
    c = C_ORANGE
    img, draw = _base((18, 8, 0))
    draw.text((36, 14), "FF", font=_font(22, bold=True), fill=c, anchor="mm")
    # calendar grid
    draw.rectangle([(8,26),(64,56)], outline=c, width=2)
    for x in [28, 48]:
        draw.line([(x,26),(x,56)], fill=c, width=1)
    draw.line([(8,40),(64,40)], fill=c, width=1)
    draw.text((36, 64), "FOREXFACTORY", font=_font(7), fill=c, anchor="mm")
    draw.rectangle([(0,0),(71,71)], outline=c, width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  KEY 14 — MT5 (live account summary)
# ══════════════════════════════════════════════════════════════════
def render_mt5(balance: float = 0, equity: float = 0,
               profit: float = 0, currency: str = "", connected: bool = False) -> Image.Image:
    c = (68, 138, 255)
    img, draw = _base(C_NAVY)
    draw.text((36, 10), "MT5", font=_font(13, bold=True), fill=c, anchor="mm")
    draw.line([(4,18),(68,18)], fill=(30,40,60), width=1)
    if connected:
        pc = C_GREEN if profit >= 0 else C_RED
        draw.text((36, 28), f"BAL {balance:.0f}", font=_font(9),  fill=C_WHITE, anchor="mm")
        draw.text((36, 39), f"EQ  {equity:.0f}",  font=_font(9),  fill=C_WHITE, anchor="mm")
        draw.text((36, 50), f"P&L {profit:+.0f}", font=_font(10, bold=True), fill=pc, anchor="mm")
        draw.text((36, 62), currency,              font=_font(8),  fill=(80,100,140), anchor="mm")
    else:
        draw.text((36, 38), "NOT",       font=_font(11, bold=True), fill=C_RED, anchor="mm")
        draw.text((36, 52), "CONNECTED", font=_font(9),             fill=C_RED, anchor="mm")
    draw.rectangle([(0,0),(71,71)], outline=c, width=2)
    return img

# ══════════════════════════════════════════════════════════════════
#  FEEDBACK flash images
# ══════════════════════════════════════════════════════════════════
def render_flash_ok(label: str = "DONE") -> Image.Image:
    img, draw = _base((0, 20, 8))
    draw.text((36, 28), "✓",    font=_font(28, bold=True), fill=C_GREEN, anchor="mm")
    draw.text((36, 54), label,  font=_font(11),             fill=C_GREEN, anchor="mm")
    draw.rectangle([(0,0),(71,71)], outline=C_GREEN, width=3)
    return img

def render_flash_err(msg: str = "ERROR") -> Image.Image:
    img, draw = _base((20, 0, 0))
    draw.text((36, 28), "✗",  font=_font(28, bold=True), fill=C_RED, anchor="mm")
    draw.text((36, 54), msg,  font=_font(9),              fill=C_RED, anchor="mm")
    draw.rectangle([(0,0),(71,71)], outline=C_RED, width=3)
    return img
