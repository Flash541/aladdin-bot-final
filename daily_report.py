"""
daily pnl report — generates premium dark-themed report images
with real coin icons, logo, and montserrat fonts.
sends them to active copy-trading users via telegram.
runs daily at 08:00 CET via bot.py job_queue.
"""
import os
import io
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from telegram.constants import ParseMode

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
COINS_DIR = os.path.join(ASSETS_DIR, "coins")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")

# map base ticker to icon filename
COIN_ICON_MAP = {
    "BTC": "bitcoin.png", "ETH": "ethereum.png", "BNB": "bnb.png",
    "OKB": "okb.png", "SOL": "sol.png", "XRP": "xrp.png",
    "DOGE": "doge.png", "ADA": "ada.png", "AVAX": "avax.png",
    "DOT": "dot.png", "LTC": "ltc.png", "LINK": "link.png",
    "MATIC": "matic.png",
}

# fallback colors for coins without icons
COIN_COLORS = {
    "BTC": "#F7931A", "ETH": "#627EEA", "BNB": "#F3BA2F",
    "OKB": "#2B6AFF", "SOL": "#9945FF", "XRP": "#00AAE4",
    "DOGE": "#C2A633", "ADA": "#0033AD", "AVAX": "#E84142",
    "DOT": "#E6007A", "LTC": "#BFBBBB", "LINK": "#2A5ADA",
}
DEFAULT_COLOR = "#4ECDC4"
GREEN = "#00FFA3"
RED = "#FF4D4D"
TEXT_MAIN = "#FFFFFF"
TEXT_SEC = "#8899AA"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """load montserrat font, fall back gracefully"""
    name = "Montserrat-Bold.ttf" if bold else "Montserrat-Regular.ttf"
    path = os.path.join(FONTS_DIR, name)
    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    # fallback chain
    for fp in ["/System/Library/Fonts/Helvetica.ttc",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _parse_base(symbol: str) -> str:
    """extract base coin name: 'BTC/USDT' -> 'BTC', 'BTCUSDT' -> 'BTC'"""
    if "/" in symbol:
        return symbol.split("/")[0].upper()
    return symbol.replace("USDT", "").replace("-", "").upper()


def _load_coin_icon(symbol: str, size: int) -> Image.Image:
    """load coin icon PNG rescaled to size, with circular mask.
    falls back to colored circle with initial letter."""
    base = _parse_base(symbol)
    filename = COIN_ICON_MAP.get(base, f"{base.lower()}.png")
    path = os.path.join(COINS_DIR, filename)

    if os.path.exists(path):
        try:
            icon = Image.open(path).convert("RGBA")
            icon = icon.resize((size, size), Image.Resampling.LANCZOS)
            # circular mask
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
            out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            out.paste(icon, (0, 0), mask)
            return out
        except Exception:
            pass

    # fallback: colored circle with letter
    color = COIN_COLORS.get(base, DEFAULT_COLOR)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, size, size], fill=color)
    fnt = _font(int(size * 0.45), bold=True)
    letter = base[:1]
    bbox = draw.textbbox((0, 0), letter, font=fnt)
    lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - lw) / 2, (size - lh) / 2 - 2), letter, font=fnt, fill="white")
    return img


def generate_report_image(date_str: str, total_pnl: float, coin_breakdown: list[dict]) -> io.BytesIO:
    """
    generate premium dark card with real coin icons and montserrat fonts.
    coin_breakdown: [{"symbol": "BTC/USDT", "pnl": 1.47}, ...]
    returns BytesIO with PNG.
    """
    W = 1200
    ICON_SIZE = 56
    ROW_H = 80
    LIST_TOP = 340
    coin_count = min(len(coin_breakdown), 10)
    H = max(560, LIST_TOP + coin_count * ROW_H + 80)

    # dark base
    img = Image.new("RGBA", (W, H), "#0b0e14")
    draw = ImageDraw.Draw(img)

    # top glow effect — blue ellipse blurred
    glow = Image.new("RGBA", (W, 450), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse([-200, -300, W + 200, 280], fill=(6, 96, 249, 40))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=100))
    img.alpha_composite(glow)

    # redraw after composite
    draw = ImageDraw.Draw(img)

    # subtle border
    draw.rounded_rectangle([20, 20, W - 20, H - 20], radius=24, outline="#1a2035", width=2)

    # title — no logo, just text
    f_title = _font(46, bold=True)
    title = "Black Aladdin"
    bbox = draw.textbbox((0, 0), title, font=f_title)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) / 2, 50), title, fill=TEXT_MAIN, font=f_title)

    # date subtitle
    f_date = _font(26)
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_txt = f"Доходность: {dt.strftime('%d.%m.%Y')}"
    except Exception:
        date_txt = date_str
    bbox = draw.textbbox((0, 0), date_txt, font=f_date)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) / 2, 110), date_txt, fill=TEXT_SEC, font=f_date)

    # big pnl number
    f_pnl = _font(96, bold=True)
    pnl_str = f"+{total_pnl:.2f} USDT"
    pnl_color = GREEN if total_pnl >= 0 else RED
    bbox = draw.textbbox((0, 0), pnl_str, font=f_pnl)
    tw = bbox[2] - bbox[0]
    # subtle shadow
    draw.text(((W - tw) / 2 + 3, 173), pnl_str, fill="#00000060", font=f_pnl)
    draw.text(((W - tw) / 2, 170), pnl_str, fill=pnl_color, font=f_pnl)

    # separator
    draw.line([(100, 310), (W - 100, 310)], fill="#1a2a3a", width=2)

    # coin rows
    f_coin = _font(32, bold=True)
    f_pnl_small = _font(32, bold=True)
    MARGIN_L = 140
    MARGIN_R = 140

    for i, coin in enumerate(coin_breakdown[:10]):
        y_center = LIST_TOP + i * ROW_H + ROW_H // 2

        # coin icon
        icon = _load_coin_icon(coin["symbol"], ICON_SIZE)
        icon_y = y_center - ICON_SIZE // 2
        img.paste(icon, (MARGIN_L, icon_y), icon)
        draw = ImageDraw.Draw(img)

        # symbol name
        display = coin["symbol"].replace("/", "-") if "/" in coin["symbol"] else coin["symbol"]
        draw.text((MARGIN_L + ICON_SIZE + 20, y_center - 16), display, fill="#CCDDEE", font=f_coin)

        # pnl value (right aligned)
        cpnl = coin["pnl"]
        cpnl_str = f"+${cpnl:.2f}" if cpnl >= 0 else f"-${abs(cpnl):.2f}"
        cpnl_color = GREEN if cpnl >= 0 else RED
        bbox = draw.textbbox((0, 0), cpnl_str, font=f_pnl_small)
        cw = bbox[2] - bbox[0]
        draw.text((W - MARGIN_R - cw, y_center - 16), cpnl_str, fill=cpnl_color, font=f_pnl_small)

    # footer
    f_footer = _font(18)
    footer = "Copy Trading Report • Black Aladdin"
    bbox = draw.textbbox((0, 0), footer, font=f_footer)
    fw = bbox[2] - bbox[0]
    draw.text(((W - fw) / 2, H - 50), footer, fill="#334455", font=f_footer)

    # convert to RGB for PNG export
    final = Image.new("RGB", (W, H), (11, 14, 20))
    final.paste(img, mask=img.split()[3])

    buf = io.BytesIO()
    final.save(buf, format="PNG", quality=95)
    buf.seek(0)
    return buf


async def send_daily_reports(context):
    """scheduler callback — queries yesterday's pnl, generates images, sends to users."""
    from database import get_daily_pnl_report, get_user_language

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"📊 [DAILY REPORT] Generating reports for {yesterday}...")

    rows = get_daily_pnl_report(yesterday)
    if not rows:
        print("📊 [DAILY REPORT] No profitable trades yesterday, skipping.")
        return

    # group by user
    user_data = defaultdict(list)
    for r in rows:
        user_data[r["user_id"]].append({"symbol": r["symbol"], "pnl": r["pnl"]})

    sent, failed = 0, 0
    for user_id, coins in user_data.items():
        total_pnl = sum(c["pnl"] for c in coins)
        if total_pnl <= 0:
            continue

        coins.sort(key=lambda x: x["pnl"], reverse=True)

        try:
            img_buf = generate_report_image(yesterday, total_pnl, coins)
            lang = get_user_language(user_id)

            if lang == "ru":
                caption = f"📊 Отчёт за {yesterday}\n💰 Общая прибыль: +{total_pnl:.2f} USDT"
            elif lang == "uk":
                caption = f"📊 Звіт за {yesterday}\n💰 Загальний прибуток: +{total_pnl:.2f} USDT"
            else:
                caption = f"📊 Daily Report — {yesterday}\n💰 Total Profit: +{total_pnl:.2f} USDT"

            await context.bot.send_photo(
                chat_id=user_id, photo=img_buf, caption=caption, parse_mode=ParseMode.HTML
            )
            sent += 1
            await asyncio.sleep(0.1)  # anti-spam
        except Exception as e:
            print(f"❌ [DAILY REPORT] Failed to send to {user_id}: {e}")
            failed += 1

    print(f"📊 [DAILY REPORT] Done. Sent: {sent}, Failed: {failed}")
