import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, WebAppInfo
)
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from aiohttp import web

# добавили get_subcategories
from db import get_categories, get_products, get_product, create_order, get_subcategories

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# нормализуем WEBAPP_URL (добавим https:// и / если их забыли)
WEBAPP_URL = (os.getenv("WEBAPP_URL") or "").strip()
if WEBAPP_URL:
    if not WEBAPP_URL.startswith(("http://", "https://")):
        WEBAPP_URL = "https://" + WEBAPP_URL.lstrip("/")
    if not WEBAPP_URL.endswith("/"):
        WEBAPP_URL += "/"

PORT = int(os.getenv("PORT", "8000"))

logging.basicConfig(level=logging.INFO)

# aiogram 3.7+: parse_mode через DefaultBotProperties
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ----------------- WebApp (aiohttp) -----------------
async def api_categories(request):
    return web.json_response(get_categories())

# НОВОЕ: подкатегории для выбранной категории
async def api_subcategories(request):
    cat = request.rel_url.query.get("category")
    if not cat:
        return web.json_response([])
    return web.json_response(get_subcategories(cat))

async def api_products(request):
    cat = request.rel_url.query.get("category")
    sub = request.rel_url.query.get("subcategory")
    return web.json_response(get_products(cat, sub))

async def index_handler(request):
    return web.FileResponse(os.path.join("web", "index.html"))

async def file_handler(request):
    path = request.match_info['path']
    full = os.path.join("web", path)
    if not os.path.isfile(full):
        return web.Response(status=404, text="Not found")
    return web.FileResponse(full)

# Optional fallback API order (если вдруг решишь слать заказ не через sendData)
async def api_order(request):
    data = await request.json()
    # Validate items and recompute total
    items = []
    total = 0
    for it in data.get("items", []):
        p = get_product(int(it["product_id"]))
        if not p:
            continue
        qty = int(it.get("qty", 1))
        size = (it.get("size") or "")
        items.append({"product_id": p["id"], "size": size, "qty": qty, "price": p["price"]})
        total += p["price"] * qty
    order_id = create_order(
        user_id=0, username=None,
        full_name=data.get("full_name"), phone=data.get("phone"),
        address=data.get("address"), comment=data.get("comment"),
        total_price=total, items=items
    )
    return web.json_response({"ok": True, "order_id": order_id})

def build_app():
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/web/{path:.*}", file_handler)
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/subcategories", api_subcategories)  # ← НОВОЕ
    app.router.add_get("/api/products", api_products)
    app.router.add_post("/api/order", api_order)
    return app

# ----------------- Bot: open WebApp -----------------
@dp.message(Command("start"))
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="Открыть магазин",
            web_app=WebAppInfo(url=WEBAPP_URL or "https://example.com")
        )
    ]])
    await m.answer("PLACE — мини-магазин в Telegram. Открой витрину:", reply_markup=kb)

@dp.message(F.web_app_data)
async def on_webapp_data(m: Message):
    try:
        data = json.loads(m.web_app_data.data)
    except Exception:
        await m.answer("Не удалось прочитать данные заказа.")
        return

    # Validate products and calculate total
    items_payload = []
    total = 0
    for it in data.get("items", []):
        p = get_product(int(it["product_id"]))
        if not p:
            continue
        qty = int(it.get("qty", 1))
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
        total_price=total,
        items=items_payload,
    )

    await m.answer(f"✅ Заказ #{order_id} оформлен. Мы свяжемся с вами. Сумма: {total} ₽")

    if ADMIN_CHAT_ID:
        items_text = "\n".join([
            f"• {get_product(it['product_id'])['title']} [{it['size']}] × {it['qty']} — {it['price']*it['qty']} ₽"
            for it in items_payload
        ]) or "—"
        text = (
            f"<b>Новый заказ #{order_id}</b>\n"
            f"Клиент: {data.get('full_name')} (@{m.from_user.username or '—'})\n"
            f"Тел: {data.get('phone')}\n"
            f"СДЭК/адрес: {data.get('address')}\n"
            f"Сумма: <b>{total} ₽</b>\n"
            f"Комментарий: {data.get('comment') or '—'}\n\n"
            f"{items_text}"
        )
        try:
            await bot.send_message(ADMIN_CHAT_ID, text)
        except Exception as e:
            logging.exception("Admin DM failed: %s", e)

async def main():
    assert BOT_TOKEN, "BOT_TOKEN is not set"
    # Start web server and bot together
    app = build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Web server started on port {PORT}")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
