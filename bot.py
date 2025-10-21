import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, InlineKeyboardMarkup,
    InlineKeyboardButton, WebAppInfo
)
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from aiohttp import web

from db import get_categories, get_products, get_product, create_order

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "")  # https://<твой-домен>.up.railway.app/web/
PORT = int(os.getenv("PORT", "8000"))

# === поддержка нескольких админов ===
def _parse_ids(s: str):
    ids = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except:
            pass
    return ids

ADMIN_CHAT_IDS = _parse_ids(os.getenv("ADMIN_CHAT_IDS", ""))
if not ADMIN_CHAT_IDS and ADMIN_CHAT_ID:
    ADMIN_CHAT_IDS = [ADMIN_CHAT_ID]

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ----------------- WebApp (aiohttp) -----------------
async def api_categories(request):
    return web.json_response(get_categories())

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

# --- API для оформления заказа из WebApp ---
async def api_order(request):
    data = await request.json()
    items = []
    total = 0

    for it in data.get("items", []):
        p = get_product(int(it["product_id"]))
        if not p:
            continue
        qty = int(it.get("qty", 1))
        size = (it.get("size") or "")
        items.append({
            "product_id": p["id"],
            "size": size,
            "qty": qty,
            "price": p["price"]
        })
        total += p["price"] * qty

    order_id = create_order(
        user_id=0, username=None,
        full_name=data.get("full_name"),
        phone=data.get("phone"),
        address=data.get("address"),
        comment=data.get("comment"),
        total_price=total, items=items
    )

    return web.json_response({"ok": True, "order_id": order_id})


def build_app():
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/web/{path:.*}", file_handler)
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/products", api_products)
    app.router.add_post("/api/order", api_order)
    return app

# ----------------- Бот: запуск WebApp -----------------
@dp.message(Command("start"))
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🛍 Открыть магазин",
            web_app=WebAppInfo(url=WEBAPP_URL or "https://example.com")
        )
    ]])
    await m.answer("🖤 PLACE — мини-магазин в Telegram.\nНажми кнопку ниже, чтобы открыть витрину:", reply_markup=kb)

# ----------------- Обработка заказов из WebApp -----------------
@dp.message(F.web_app_data)
async def on_webapp_data(m: Message):
    try:
        data = json.loads(m.web_app_data.data)
    except Exception:
        await m.answer("Не удалось прочитать данные заказа 😔")
        return

    items_payload = []
    total = 0
    for it in data.get("items", []):
        p = get_product(int(it["product_id"]))
        if not p:
            continue
        qty = int(it.get("qty", 1))
        size = (it.get("size") or "")
        items_payload.append({
            "product_id": p["id"],
            "size": size,
            "qty": qty,
            "price": p["price"]
        })
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

    await m.answer(f"✅ Заказ №{order_id} оформлен!\nМы свяжемся с вами в ближайшее время.\n\nСумма: <b>{total} ₽</b>")

    # --- отправляем менеджерам ---
    if ADMIN_CHAT_IDS:
        uname = f"@{m.from_user.username}" if m.from_user.username else "—"
        buyer_link = f"<a href='tg://user?id={m.from_user.id}'>профиль</a>"

        items_text = "\n".join([
            f"• {get_product(it['product_id'])['title']} "
            f"[{it['size'] or '—'}] × {it['qty']} — {it['price']*it['qty']} ₽"
            for it in items_payload
        ]) or "—"

        text = (
            f"<b>🛒 Новый заказ #{order_id}</b>\n"
            f"👤 Клиент: <b>{data.get('full_name') or '—'}</b> {uname} ({buyer_link})\n"
            f"🆔 User ID: <code>{m.from_user.id}</code>\n"
            f"📞 Телефон: <b>{data.get('phone') or '—'}</b>\n"
            f"📦 Адрес / СДЭК: <b>{data.get('address') or '—'}</b>\n"
            f"💬 Комментарий: {data.get('comment') or '—'}\n"
            f"💰 Сумма: <b>{total} ₽</b>\n\n"
            f"{items_text}"
        )

        for chat_id in ADMIN_CHAT_IDS:
            try:
                await bot.send_message(chat_id, text, disable_web_page_preview=True)
            except Exception as e:
                logging.exception("❌ Ошибка при отправке админу %s: %s", chat_id, e)


async def main():
    assert BOT_TOKEN, "❌ BOT_TOKEN не задан!"
    app = build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"🌐 Web server started on port {PORT}")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
