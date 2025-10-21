import asyncio, json, logging, os
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

BOT_TOKEN  = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = (os.getenv("WEBAPP_URL", "")).strip()  # ожидается: https://place-shop-production.up.railway.app/
PORT       = int(os.getenv("PORT", "8000"))

# Нормализуем WEBAPP_URL -> /web/
if WEBAPP_URL:
    if not WEBAPP_URL.startswith(("http://", "https://")):
        WEBAPP_URL = "https://" + WEBAPP_URL.lstrip("/")
    if not WEBAPP_URL.endswith("/"):
        WEBAPP_URL += "/"
    if not WEBAPP_URL.endswith("/web/"):
        # если указали корень, добавим web/
        if WEBAPP_URL.endswith("/web"):
            WEBAPP_URL += "/"
        elif WEBAPP_URL.endswith("//web/"):
            pass
        else:
            WEBAPP_URL += "web/"

def _parse_ids(s: str):
    res = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part: 
            continue
        try:
            res.append(int(part))
        except:
            pass
    return res

# Менеджер(ы) — по ТЗ один ID, но оставим поддержку списка
DEFAULT_MANAGER_ID = 6773668793
ADMIN_CHAT_IDS = _parse_ids(os.getenv("ADMIN_CHAT_IDS", "")) or [DEFAULT_MANAGER_ID]

THANKYOU_TEXT = (
    "Спасибо за заказ! В скором времени с Вами свяжется менеджер и пришлет реквизиты для оплаты!"
)

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ---------------- WebApp & API ----------------
async def index_handler(request):
    return web.FileResponse(os.path.join("web", "index.html"))

async def file_handler(request):
    p = os.path.join("web", request.match_info["path"])
    if not os.path.isfile(p):
        return web.Response(status=404, text="Not found")
    return web.FileResponse(p)

# Нормализованные категории ( [{title,image_url}] )
async def api_categories(request):
    cats = get_categories()
    # на всякий случай нормализуем
    out = []
    for c in cats:
        if isinstance(c, dict):
            title = c.get("title") or c.get("name") or ""
            img   = c.get("image_url") or c.get("image") or ""
        else:
            title, img = str(c), ""
        if not title:
            continue
        out.append({"title": title, "image_url": img})
    return web.json_response(out)

# Подкатегории -> ["Все", ...]
async def api_subcategories(request):
    cat = request.rel_url.query.get("category")
    if not cat:
        return web.json_response([])
    subs = get_subcategories(cat)
    titles = []
    for s in subs or []:
        if isinstance(s, dict):
            t = s.get("title") or s.get("name") or ""
        else:
            t = str(s or "")
        if t:
            titles.append(t)
    # уникальные в исходном порядке
    seen, uniq = set(), []
    for t in titles:
        if t not in seen:
            seen.add(t); uniq.append(t)
    return web.json_response(uniq)

async def api_products(request):
    cat = request.rel_url.query.get("category")
    sub = request.rel_url.query.get("subcategory")
    return web.json_response(get_products(cat, sub))

# запасной REST, если вдруг sendData не сработал
async def api_order(request):
    data = await request.json()
    items, total = [], 0
    for it in data.get("items", []):
        p = get_product(int(it["product_id"]))
        if not p: continue
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
    app.router.add_get("/", index_handler)
    app.router.add_get("/web/{path:.*}", file_handler)
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/subcategories", api_subcategories)
    app.router.add_get("/api/products", api_products)
    app.router.add_post("/api/order", api_order)
    return app

# ---------------- Bot ----------------
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
    # данные с vitrina.sendData(...)
    try:
        data = json.loads(m.web_app_data.data)
    except Exception:
        await m.answer("Не удалось прочитать данные заказа.")
        return

    items_payload, total = [], 0
    for it in data.get("items", []):
        p = get_product(int(it["product_id"]))
        if not p: continue
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

    # покупателю
    await m.answer(f"✅ Заказ №{order_id} оформлен.\n\n{THANKYOU_TEXT}")

    # менеджерам
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
