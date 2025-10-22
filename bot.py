import asyncio, json, logging, os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from dotenv import load_dotenv
from db import get_categories, get_subcategories, get_products, get_product, create_order

load_dotenv()
BOT_TOKEN  = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = (os.getenv("WEBAPP_URL","").strip() or "").rstrip("/") + "/web/"
PORT       = int(os.getenv("PORT","8000"))

def _parse_ids(s:str):
    out=[]
    for part in (s or "").split(","):
        part=part.strip()
        if part:
            try: out.append(int(part))
            except: pass
    return out

DEFAULT_MANAGER_ID = 6773668793
ADMIN_CHAT_IDS = _parse_ids(os.getenv("ADMIN_CHAT_IDS","")) or [DEFAULT_MANAGER_ID]
THANKYOU_TEXT = "Спасибо за заказ! В скором времени с Вами свяжется менеджер и пришлет реквизиты для оплаты!"

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ---------- Web ----------
async def index_handler(_): return web.FileResponse(os.path.join("web","index.html"))
async def file_handler(request):
    p = os.path.join("web", request.match_info["path"])
    return web.FileResponse(p) if os.path.isfile(p) else web.Response(status=404, text="Not found")
async def api_categories(_): return web.json_response(get_categories())
async def api_subcategories(request): return web.json_response(get_subcategories(request.rel_url.query.get("category")))
async def api_products(request): return web.json_response(get_products(request.rel_url.query.get("category"), request.rel_url.query.get("subcategory")))
async def api_order(request):
    data = await request.json()
    items,total=[],0
    for it in data.get("items",[]):
        p = get_product(int(it["product_id"]))
        if not p: continue
        qty=int(it.get("qty",1)); size=(it.get("size") or "")
        items.append({"product_id":p["id"],"size":size,"qty":qty,"price":p["price"]})
        total += p["price"]*qty
    order_id = create_order(0,None,data.get("full_name"),data.get("phone"),data.get("address"),data.get("comment"),data.get("telegram"),total,items)
    return web.json_response({"ok":True,"order_id":order_id})
def build_app():
    app=web.Application()
    app.router.add_get("/",index_handler)
    app.router.add_get("/web/{path:.*}",file_handler)
    app.router.add_get("/api/categories",api_categories)
    app.router.add_get("/api/subcategories",api_subcategories)
    app.router.add_get("/api/products",api_products)
    app.router.add_post("/api/order",api_order)
    return app

# ---------- Bot ----------
@dp.message(Command("start"))
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Открыть LAYOUTPLACE SHOP", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    await m.answer("LAYOUTPLACE SHOP — мини-магазин в Telegram. Открой витрину ниже:", reply_markup=kb)

@dp.message(F.web_app_data)
async def on_webapp_data(m: Message):
    try: data = json.loads(m.web_app_data.data)
    except Exception as e:
        logging.exception("Bad web_app_data: %s", e)
        await m.answer("Не удалось прочитать данные заказа."); return

    items,total=[],0
    for it in data.get("items",[]):
        try: p = get_product(int(it["product_id"]))
        except: p=None
        if not p: continue
        qty=int(it.get("qty",1)); size=(it.get("size") or "")
        items.append({"product_id":p["id"],"size":size,"qty":qty,"price":p["price"]})
        total += p["price"]*qty

    order_id = create_order(m.from_user.id, m.from_user.username,
                            data.get("full_name"), data.get("phone"),
                            data.get("address"), data.get("comment"),
                            data.get("telegram"), total, items)

    await m.answer(f"✅ Заказ №{order_id} оформлен.\n\n{THANKYOU_TEXT}")

    uname = f"@{m.from_user.username}" if m.from_user.username else "—"
    buyer_link = f"<a href='tg://user?id={m.from_user.id}'>профиль</a>"
    items_text = "\n".join([
        f"• {get_product(i['product_id'])['title']} [{i['size'] or '—'}] × {i['qty']} — {i['price']*i['qty']} ₽"
        for i in items
    ]) or "—"
    text = (
        f"<b>Новый заказ #{order_id}</b>\n"
        f"Клиент: <b>{data.get('full_name') or '—'}</b> {uname} ({buyer_link})\n"
        f"User ID: <code>{m.from_user.id}</code>\n"
        f"Телефон: <b>{data.get('phone') or '—'}</b>\n"
        f"СДЭК/адрес: <b>{data.get('address') or '—'}</b>\n"
        f"Telegram: <b>{data.get('telegram') or '—'}</b>\n"
        f"Комментарий: {data.get('comment') or '—'}\n"
        f"Сумма: <b>{total} ₽</b>\n\n{items_text}"
    )
    delivered=0
    for cid in ADMIN_CHAT_IDS:
        try: await bot.send_message(cid, text, disable_web_page_preview=True); delivered+=1
        except Exception as e: logging.exception("Admin notify failed (%s): %s", cid, e)
    logging.info("Order #%s sent to %s admin(s)", order_id, delivered)

async def main():
    assert BOT_TOKEN, "BOT_TOKEN is not set"
    runner = web.AppRunner(build_app()); await runner.setup()
    await web.TCPSite(runner,"0.0.0.0",PORT).start()
    logging.info("Web server started on port %s", PORT)
    try: await dp.start_polling(bot)
    finally: await bot.session.close()

if __name__=="__main__": asyncio.run(main())
