import asyncio, json, logging, os, os.path as op
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, User
from aiogram.client.default import DefaultBotProperties
from aiohttp import web, ClientSession
from dotenv import load_dotenv

from db import get_categories, get_subcategories, get_products, get_product, create_order

load_dotenv()

BOT_TOKEN  = os.getenv("BOT_TOKEN", "").strip()
PORT       = int(os.getenv("PORT", "8000"))

# ===== Название магазина из ENV =====
STORE_TITLE = (os.getenv("STORE_TITLE", "LAYOUTPLACE Shop").strip() or "LAYOUTPLACE Shop")

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

async def api_config(request):
    return web.json_response({"title": STORE_TITLE})

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

# ---------- ПРОКСИ-КАРТИНОК ----------
# /img?u=<absolute-url>  -> отдаём контент с внешнего URL из нашего домена
async def img_proxy(request):
    url = request.rel_url.query.get("u", "")
    if not (url.startswith("http://") or url.startswith("https://")):
        return web.Response(status=400, text="bad url")
    # небольшая безопасная белая-лист фильтрация при желании:
    # if not any(host in url for host in ("raw.githubusercontent.com","drive.google.com")):
    #     return web.Response(status=403, text="forbidden")

    # убираем временные query токены
    qpos = url.find("?")
    if qpos > -1:
        url = url[:qpos]

    # Google Drive /file/d/<id>/view -> прямой
    # https://drive.google.com/file/d/FILE_ID/view  ->  https://drive.google.com/uc?export=view&id=FILE_ID
    import re
    m = re.search(r"drive\.google\.com\/file\/d\/([^\/]+)", url, flags=re.I)
    if m:
        file_id = m.group(1)
        url = f"https://drive.google.com/uc?export=view&id={file_id}"

    # GitHub refs/heads/main -> main
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
                ctype = resp.headers.get("Content-Type", "image/jpeg")
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

    # Статика из репы (если будешь класть JPG прямо в /images)
    app.router.add_static("/images/", path="images", show_index=False)

    # API
    app.router.add_get("/api/config", api_config)
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/subcategories", api_subcategories)
    app.router.add_get("/api/products", api_products)
    app.router.add_post("/api/order", api_order)

    # 🔹 новый прокси
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