import asyncio, json, logging, os, os.path as op
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from dotenv import load_dotenv

from db import (
    get_categories, get_subcategories, get_products,
    get_product, create_order
)

load_dotenv()

BOT_TOKEN  = os.getenv("BOT_TOKEN", "").strip()
PORT       = int(os.getenv("PORT", "8000"))
# Менеджер по ТЗ
ADMIN_CHAT_IDS = [int(x) for x in (os.getenv("ADMIN_CHAT_IDS", "6773668793").split(",")) if x.strip().isdigit()]

# Нормализуем URL витрины
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
if WEBAPP_URL:
    if not WEBAPP_URL.startswith(("http://", "https://")):
        WEBAPP_URL = "https://" + WEBAPP_URL.lstrip("/")
    WEBAPP_URL = WEBAPP_URL + "/web/"

THANKYOU_TEXT = (
    "Спасибо за заказ! В скором времени с Вами свяжется менеджер и пришлет реквизиты для оплаты!"
)

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp  = Dispatcher()

# -------------------- WEB --------------------
async def index_handler(request):
    return web.FileResponse(op.join("web", "index.html"))

async def file_handler(request):
    p = op.join("web", request.match_info["path"])
    if not op.isfile(p):
        return web.Response(status=404, text="Not found")
    return web.FileResponse(p)

async def api_categories(request):
    return web.json_response(get_categories())

async def api_subcategories(request):
    cat = request.rel_url.query.get("category")
    return web.json_response(get_subcategories(cat))

async def api_products(request):
    cat = request.rel_url.query.get("category")
    sub = request.rel_url.query.get("subcategory")
    return web.json_response(get_products(cat, sub))

# запасной REST, если вдруг sendData не сработал у клиента
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
    return web.json_response({"ok": True, "order_id": order_id})

def build_app():
    app = web.Application()
    app.router.add_get("/", index_handler)                    # корень
    app.router.add_get("/web/", index_handler)                # /web/
    app.router.add_get("/web/{path:.*}", file_handler)        # /web/static
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/subcategories", api_subcategories)
    app.router.add_get("/api/products", api_products)
    app.router.add_post("/api/order", api_order)
    return app

# -------------------- BOT --------------------
@dp.message(Command("start"))
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="Открыть LAYOUTPLACE SHOP",
            web_app=WebAppInfo(url=WEBAPP_URL or "https://example.com")
        )
    ]])
    await m.answer("LAYOUTPLACE SHOP — мини-магазин в Telegram. Открой витрину ниже:", reply_markup=kb)

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
        items_payload.append({"product_id": p["id"], "size": size, "qty": qty, "price": p["price"]})
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

    # клиенту
    await m.answer(f"✅ Заказ №{order_id} оформлен.\n\n{THANKYOU_TEXT}")

    # менеджеру(ам)
    if ADMIN_CHAT_IDS:
        uname = f"@{m.from_user.username}" if m.from_user.username else "—"
        buyer_link = f"<a href='tg://user?id={m.from_user.id}'>профиль</a>"
        items_text = "\n".join([
            f"• {get_product(it['product_id'])['title']} "
            f"[{it['size'] or '—'}] × {it['qty']} — {it['price']*it['qty']} ₽"
            for it in items_payload
        ]) or "—"
        text = (
            f"<b>Новый заказ #{order_id}</b>\n"
            f"Клиент: <b>{data.get('full_name') or '—'}</b> {uname} ({buyer_link})\n"
            f"User ID: <code>{m.from_user.id}</code>\n"
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
