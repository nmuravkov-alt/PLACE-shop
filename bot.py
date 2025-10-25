import asyncio, json, logging, os, os.path as op, sqlite3
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, User
from aiogram.client.default import DefaultBotProperties
from aiohttp import web, ClientSession
from dotenv import load_dotenv

from db import get_categories, get_subcategories, get_products, get_product, create_order

load_dotenv()

BOT_TOKEN   = os.getenv("BOT_TOKEN", "").strip()
PORT        = int(os.getenv("PORT", "8000"))
STORE_TITLE = (os.getenv("STORE_TITLE", "LAYOUTPLACE Shop").strip() or "LAYOUTPLACE Shop")
DB_PATH     = os.getenv("DB_PATH", "data.sqlite")

def _parse_ids(s: str):
    out = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except Exception:
            logging.warning("Skip bad ADMIN_CHAT_IDS item: %r", part)
    return out

ADMIN_CHAT_IDS = _parse_ids(os.getenv("ADMIN_CHAT_IDS", "6773668793"))

WEBAPP_URL = (os.getenv("WEBAPP_URL","").strip() or "").rstrip("/")
if WEBAPP_URL:
    if not WEBAPP_URL.startswith(("http://","https://")):
        WEBAPP_URL = "https://" + WEBAPP_URL.lstrip("/")
    WEBAPP_URL = WEBAPP_URL + "/web/"

THANKYOU_TEXT = "Спасибо за заказ! В скором времени с Вами свяжется менеджер и пришлет реквизиты для оплаты!"

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp  = Dispatcher()

# ---- helpers ----
def _get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Читает settings.value по ключу; если таблицы/ключа нет — вернёт default."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = cur.fetchone()
            return row[0] if row and row[0] is not None else default
    except Exception:
        return default

# ---------- Web ----------
async def index_handler(request):
    return web.FileResponse(op.join("web", "index.html"))

async def file_handler(request):
    path = request.match_info.get("path", "")
    if not path:
        return web.FileResponse(op.join("web", "index.html"))
    p = op.join("web", path)
    if not op.isfile(p):
        return web.Response(status=404, text="Not found")
    return web.FileResponse(p)

# Конфиг для фронта:
#  title       — заголовок магазина
#  video_url   — URL видео для героя (если задан settings.hero_video_url)
#  logo_url    — картинка-логотип (fallback)
#  hero_url    — совместимое поле-синоним (на всякий случай)
#  hero_type   — опционально, если хочешь использовать на фронте
async def api_config(request):
    logo_url   = _get_setting("logo_url", "")              # картинка-логотип (fallback)
    video_url  = _get_setting("hero_video_url", "")        # видео для главной
    hero_url   = video_url or logo_url                     # совместимое поле
    hero_type  = "video" if video_url else ("image" if logo_url else "")

    return web.json_response({
        "title": STORE_TITLE,
        "logo_url": logo_url,
        "video_url": video_url,
        "hero_url": hero_url,
        "hero_type": hero_type,
    })

async def api_categories(request):
    return web.json_response(get_categories())

async def api_subcategories(request):
    cat = request.rel_url.query.get("category")
    return web.json_response(get_subcategories(cat))

async def api_products(request):
    cat = request.rel_url.query.get("category")
    sub = request.rel_url.query.get("subcategory")
    return web.json_response(get_products(cat, sub))

async def api_order(request):
    data = await request.json()
    items, total = [], 0
    for it in data.get("items", []):
        p = get_product(int(it["product_id"]))
        if not p:
            continue
        qty  = int(it.get("qty", 1))
        size = (it.get("size") or "")
        items.append({"product_id": p["id"], "size": size, "qty": qty, "price": p["price"]})
        total += p["price"] * qty
    order_id = create_order(
        user_id=0, username=None,
        full_name=data.get("full_name"), phone=data.get("phone"),
        address=data.get("address"), comment=data.get("comment"),
        telegram=data.get("telegram"),
        total_price=total, items=items
    )
    await notify_admins(order_id, data, total, items, user=None)
    return web.json_response({"ok": True, "order_id": order_id})

# ---------- IMG PROXY ----------
async def img_proxy(request):
    url = request.rel_url.query.get("u", "")
    if not (url.startswith("http://") or url.startswith("https://")):
        return web.Response(status=400, text="bad url")

    qpos = url.find("?")
    if qpos > -1:
        url = url[:qpos]

    import re
    m = re.search(r"drive\.google\.com\/file\/d\/([^\/]+)", url, flags=re.I)
    if m:
        file_id = m.group(1)
        url = f"https://drive.google.com/uc?export=view&id={file_id}"

    url = re.sub(
        r"raw\.githubusercontent\.com\/([^\/]+)\/([^\/]+)\/refs\/heads\/main\/",
        r"raw.githubusercontent.com/\1/\2/main/",
        url,
        flags=re.I
    )

    try:
        async with ClientSession() as sess:
            async with sess.get(url) as resp:
                if resp.status != 200:
                    return web.Response(status=resp.status, text="fetch error")
                data = await resp.read()
                # пробрасываем исходный тип (лучше, чем жёстко image/jpeg)
                ctype = resp.headers.get("Content-Type", "application/octet-stream")
                headers = {"Cache-Control":"public, max-age=31536000"}
                return web.Response(body=data, content_type=ctype, headers=headers)
    except Exception as e:
        logging.exception("IMG proxy error: %s", e)
        return web.Response(status=502, text="proxy error")

def build_app():
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/web/", index_handler)
    app.router.add_get("/web", index_handler)
    app.router.add_get("/web/{path:.*}", file_handler)

    # Статика /images (для hero mp4/webm или картинок)
    if op.isdir("images"):
        app.router.add_static("/images/", path="images", show_index=False)

    # API
    app.router.add_get("/api/config", api_config)
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/subcategories", api_subcategories)
    app.router.add_get("/api/products", api_products)
    app.router.add_post("/api/order", api_order)

    # Прокси
    app.router.add_get("/img", img_proxy)
    return app

# ---------- Bot ----------
@dp.message(Command("start"))
async def start(m: Message):
    title_upper = STORE_TITLE.upper()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"Открыть {title_upper}",
            web_app=WebAppInfo(url=WEBAPP_URL or "https://example.com")
        )
    ]])
    await m.answer(f"{title_upper} — мини-магазин в Telegram. Открой витрину ниже:", reply_markup=kb)

async def notify_admins(order_id: int, data: dict, total: int, items_payload: list, user: Optional[User]):
    uname = f"@{user.username}" if (user and user.username) else "—"
    buyer_link = f"<a href='tg://user?id={user.id}'>профиль</a>" if user else "—"
    items_text = "\n".join([
        f"• {get_product(it['product_id'])['title']} "
        f"[{it.get('size') or '—'}] × {it.get('qty',1)} — {it.get('price',0)*it.get('qty',1)} ₽"
        for it in items_payload
    ]) or "—"
    text = (
        f"<b>Новый заказ #{order_id}</b>\n"
        f"Клиент: <b>{data.get('full_name') or '—'}</b> {uname} ({buyer_link})\n"
        f"Телефон: <b>{data.get('phone') or '—'}</b>\n"
        f"СДЭК/адрес: <b>{data.get('address') or '—'}</b>\n"
        f"Telegram: <b>{data.get('telegram') or '—'}</b>\n"
        f"Комментарий: {data.get('comment') or '—'}\n"
        f"Сумма: <b>{total} ₽</b>\n\n"
        f"{items_text}"
    )
    for cid in ADMIN_CHAT_IDS:
        try:
            await bot.send_message(cid, text, disable_web_page_preview=True)
        except Exception as e:
            logging.exception("Admin DM failed to %s: %s", cid, e)

@dp.message(F.web_app_data)
async def on_webapp_data(m: Message):
    try:
        data = json.loads(m.web_app_data.data)
    except Exception:
        await m.answer("Не удалось прочитать данные заказа.")
        return

    items_payload, total = [], 0
    for it in data.get("items", []):
        p = get_product(int(it["product_id"]))
        if not p:
            continue
        qty  = int(it.get("qty", 1))
        size = (it.get("size") or "")
        item = {"product_id": p["id"], "size": size, "qty": qty, "price": p["price"]}
        items_payload.append(item)
        total += p["price"] * qty

    order_id = create_order(
        user_id=m.from_user.id,
        username=m.from_user.username,
        full_name=data.get("full_name"),
        phone=data.get("phone"),
        address=data.get("address"),
        comment=data.get("comment"),
        telegram=data.get("telegram"),
        total_price=total,
        items=items_payload,
    )

    await m.answer(f"✅ Заказ №{order_id} оформлен.\n\n{THANKYOU_TEXT}")
    await notify_admins(order_id, data, total, items_payload, user=m.from_user)

async def main():
    assert BOT_TOKEN, "BOT_TOKEN is not set"
    app = build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logging.info(f"Web server started on port {PORT}")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
