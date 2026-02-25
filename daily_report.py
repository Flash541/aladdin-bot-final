"""
daily pnl report — generates premium dark-themed report images
grouped by exchange (OKX, BingX, Bybit) with exchange icons.
only sends if total pnl is POSITIVE.
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
EXCHANGES_DIR = os.path.join(ASSETS_DIR, "exchanges")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")

# exchange display config
EXCHANGE_CONFIG = {
    "okx": {"name": "OKX", "color": "#FFFFFF", "icon": "okx.png"},
    "bingx": {"name": "BingX", "color": "#2CB77A", "icon": "bingx.png"},
    "bybit": {"name": "Bybit", "color": "#F7A600", "icon": "bybit.png"},
}

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
    for fp in ["/System/Library/Fonts/Helvetica.ttc",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _load_exchange_icon(exchange: str, size: int) -> Image.Image:
    """load exchange icon PNG, fall back to colored circle with letter."""
    cfg = EXCHANGE_CONFIG.get(exchange, {"name": exchange.upper(), "color": "#4ECDC4", "icon": ""})
    path = os.path.join(EXCHANGES_DIR, cfg["icon"]) if cfg["icon"] else ""

    if path and os.path.exists(path):
        try:
            icon = Image.open(path).convert("RGBA")
            icon = icon.resize((size, size), Image.Resampling.LANCZOS)
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
            out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            out.paste(icon, (0, 0), mask)
            return out
        except Exception:
            pass

    # fallback: colored circle with letter
    color = cfg["color"]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, size, size], fill=color)
    fnt = _font(int(size * 0.4), bold=True)
    letter = cfg["name"][:1]
    bbox = draw.textbbox((0, 0), letter, font=fnt)
    lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    txt_color = "#000000" if color in ("#FFFFFF", "#F7A600", "#2CB77A") else "#FFFFFF"
    draw.text(((size - lw) / 2, (size - lh) / 2 - 2), letter, font=fnt, fill=txt_color)
    return img


def generate_report_image(date_str: str, total_pnl: float, exchange_breakdown: list[dict]) -> io.BytesIO:
    """
    generate premium dark card with exchange icons.
    exchange_breakdown: [{"exchange": "okx", "pnl": 1.47}, ...]
    returns BytesIO with PNG.
    """
    W = 1200
    ICON_SIZE = 56
    ROW_H = 80
    LIST_TOP = 340
    item_count = min(len(exchange_breakdown), 5)
    H = max(560, LIST_TOP + item_count * ROW_H + 80)

    # dark base
    img = Image.new("RGBA", (W, H), "#0b0e14")
    draw = ImageDraw.Draw(img)

    # top glow effect
    glow = Image.new("RGBA", (W, 450), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse([-200, -300, W + 200, 280], fill=(6, 96, 249, 40))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=100))
    img.alpha_composite(glow)
    draw = ImageDraw.Draw(img)

    # subtle border
    draw.rounded_rectangle([20, 20, W - 20, H - 20], radius=24, outline="#1a2035", width=2)

    # title
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

    # big pnl number (always positive since we only send for profit)
    f_pnl = _font(96, bold=True)
    pnl_str = f"+{total_pnl:.2f} USDT"
    pnl_color = GREEN
    bbox = draw.textbbox((0, 0), pnl_str, font=f_pnl)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) / 2 + 3, 173), pnl_str, fill="#00000060", font=f_pnl)
    draw.text(((W - tw) / 2, 170), pnl_str, fill=pnl_color, font=f_pnl)

    # separator
    draw.line([(100, 310), (W - 100, 310)], fill="#1a2a3a", width=2)

    # exchange rows
    f_name = _font(32, bold=True)
    f_pnl_small = _font(32, bold=True)
    MARGIN_L = 140
    MARGIN_R = 140

    for i, item in enumerate(exchange_breakdown[:5]):
        y_center = LIST_TOP + i * ROW_H + ROW_H // 2

        # exchange icon
        icon = _load_exchange_icon(item["exchange"], ICON_SIZE)
        icon_y = y_center - ICON_SIZE // 2
        img.paste(icon, (MARGIN_L, icon_y), icon)
        draw = ImageDraw.Draw(img)

        # exchange name
        cfg = EXCHANGE_CONFIG.get(item["exchange"], {"name": item["exchange"].upper()})
        draw.text((MARGIN_L + ICON_SIZE + 20, y_center - 16), cfg["name"], fill="#CCDDEE", font=f_name)

        # pnl value (right aligned) — show $0.00 for negative
        cpnl = max(item["pnl"], 0)
        cpnl_str = f"+${cpnl:.2f}"
        cpnl_color = GREEN
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
    """scheduler callback — queries yesterday's pnl, generates images, sends to users.
    ONLY sends report if user's total PnL is POSITIVE."""
    from database import get_daily_pnl_report, get_user_language

    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"📊 [DAILY REPORT] Generating reports for {yesterday}...")

    rows = get_daily_pnl_report(yesterday)
    if not rows:
        print("📊 [DAILY REPORT] No closed trades yesterday.")
        if ADMIN_USER_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=f"📊 Daily Report ({yesterday})\n\nНет закрытых сделок за вчера.",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                print(f"❌ [DAILY REPORT] Admin notify failed: {e}")
        return

    # group by user
    user_data = defaultdict(list)
    for r in rows:
        user_data[r["user_id"]].append({"exchange": r["exchange"], "pnl": r["pnl"]})

    sent, failed, skipped = 0, 0, 0
    for user_id, exchanges in user_data.items():
        # total = sum of ONLY positive exchange PnLs
        total_pnl = sum(max(e["pnl"], 0) for e in exchanges)

        # ⛔ SKIP if no profitable exchanges
        if total_pnl <= 0:
            skipped += 1
            print(f"   ⏭ User {user_id}: no positive PnL, skipping")
            continue

        # sort by pnl descending (most profitable exchange first)
        exchanges.sort(key=lambda x: x["pnl"], reverse=True)

        try:
            img_buf = generate_report_image(yesterday, total_pnl, exchanges)
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
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"❌ [DAILY REPORT] Failed to send to {user_id}: {e}")
            failed += 1

    print(f"📊 [DAILY REPORT] Done. Sent: {sent}, Failed: {failed}, Skipped (negative): {skipped}")

    # admin summary
    if ADMIN_USER_ID:
        try:
            total_users = len(user_data)
            total_pnl_all = sum(sum(e["pnl"] for e in exs) for exs in user_data.values())
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=(
                    f"📊 <b>Daily Report Summary ({yesterday})</b>\n\n"
                    f"👥 Users with trades: {total_users}\n"
                    f"✅ Reports sent: {sent}\n"
                    f"⏭ Skipped (negative PnL): {skipped}\n"
                    f"❌ Failed: {failed}\n"
                    f"💰 Total PnL (all users): {total_pnl_all:+.2f} USDT"
                ),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"❌ [DAILY REPORT] Admin summary failed: {e}")
