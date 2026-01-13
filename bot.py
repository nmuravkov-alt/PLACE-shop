import asyncio, json, logging, os, os.path as op, sqlite3
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # env должен загрузиться ДО импорта db.py / seed_from_csv

# ===================== DB PATH FIX =====================
DB_PATH = (os.getenv("DB_PATH", "data.sqlite") or "data.sqlite").strip()
if not DB_PATH:
    DB_PATH = "data.sqlite"
os.environ["DB_PATH"] = DB_PATH  # чтобы db.py/seed_from_csv увидели верный путь


def _ensure_db_dir():
    """Создаёт директорию для DB_PATH, если она нужна (например /data)."""
    try:
        d = op.dirname(DB_PATH)
        if d and not op.exists(d):
            os.makedirs(d, exist_ok=True)
    except Exception as e:
        logging.exception("Failed to ensure DB dir: %s", e)


_ensure_db_dir()

# ===================== imports after env/db path =====================
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    User,
)
from aiogram.client.default import DefaultBotProperties
from aiohttp import web, ClientSession

from db import get_categories, get_subcategories, get_products, get_product, create_order

# ✅ попробуем импортировать функции импорта/схемы (как в PLACE-shop)
try:
    from seed_from_csv import seed_from_csv, ensure_schema  # seed_from_csv(csv_file: str, clear: bool=False)
except Exception:
    seed_from_csv = None
    ensure_schema = None

# ===================== config =====================
BOT_TOKEN = (os.getenv("BOT_TOKEN", "") or "").strip()
PORT = int(os.getenv("PORT", "8000"))  # у тебя в логах 8000, оставляем так
STORE_TITLE = (os.getenv("STORE_TITLE", "AKUMA SHOP") or "AKUMA SHOP").strip()
GOOGLE_SHEET_CSV_URL = (os.getenv("GOOGLE_SHEET_CSV_URL", "") or "").strip()

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

WEBAPP_URL = (os.getenv("WEBAPP_URL", "") or "").strip().rstrip("/")
if WEBAPP_URL and not WEBAPP_URL.startswith(("http://", "https://")):
    WEBAPP_URL = "https://" + WEBAPP_URL.lstrip("/")
if WEBAPP_URL:
    if not WEBAPP_URL.endswith("/web") and not WEBAPP_URL.endswith("/web/"):
        WEBAPP_URL += "/web/"
    elif WEBAPP_URL.endswith("/web"):
        WEBAPP_URL += "/"
else:
    WEBAPP_URL = "https://example.com/web/"

THANKYOU_TEXT = "Спасибо за заказ! В скором времени с Вами свяжется менеджер и пришлет реквизиты для оплаты!"

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

_DB_READY = False

# ===================== DB helpers =====================
def _ensure_schema_fallback():
    """Фоллбек: выполняет models.sql, чтобы не было 'no such table: products'."""
    models_path = "models.sql"
    if not op.isfile(models_path):
        return
    try:
        _ensure_db_dir()
        with open(models_path, "r", encoding="utf-8") as f:
            sql = f.read()
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript(sql)
        logging.info("DB schema ensured (fallback models.sql)")
    except Exception as e:
        logging.exception("Schema ensure fallback failed: %s", e)

def ensure_db_ready():
    """Гарантирует папку + схему. Делает это 1 раз на процесс."""
    global _DB_READY
    if _DB_READY:
        return

    _ensure_db_dir()

    # 1) пробуем ensure_schema из seed_from_csv
    if callable(ensure_schema):
        try:
            ensure_schema()
            logging.info("DB schema ensured (seed_from_csv.ensure_schema)")
            _DB_READY = True
            return
        except Exception as e:
            logging.exception("ensure_schema() failed: %s", e)
            # если упало из-за /data — пробуем mkdir и ещё раз
            try:
                _ensure_db_dir()
                ensure_schema()
                logging.info("DB schema ensured after mkdir (/data fix)")
                _DB_READY = True
                return
            except Exception as e2:
                logging.exception("ensure_schema retry failed: %s", e2)

    # 2) фоллбек через models.sql
    _ensure_schema_fallback()
    _DB_READY = True

def _get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        _ensure_db_dir()
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = cur.fetchone()
            return row[0] if row and row[0] is not None else default
    except Exception:
        return default

def _is_admin(user_id: int) -> bool:
    return user_id in set(ADMIN_CHAT_IDS)

# ===================== sync from google =====================
async def _download_csv(url: str, dest_path: str) -> None:
    async with ClientSession() as sess:
        async with sess.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"CSV fetch failed: HTTP {resp.status}: {text[:200]}")
            data = await resp.read()
    os.makedirs(op.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(data)

async def sync_from_google(clear_products: bool = False) -> str:
    if not GOOGLE_SHEET_CSV_URL:
        raise RuntimeError("GOOGLE_SHEET_CSV_URL не задан в Railway Variables")

    ensure_db_ready()

    tmp_csv = "/tmp/products_sheet.csv"
    await _download_csv(GOOGLE_SHEET_CSV_URL, tmp_csv)

    if seed_from_csv is None:
        import sys, subprocess
        cmd = [sys.executable, "seed_from_csv.py", "--csv", tmp_csv]
        if clear_products:
            cmd.append("--clear")
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError((p.stderr or p.stdout or "").strip()[:4000])
        return f"✅ Синк выполнен (script). {(p.stdout or '').strip()}"
    else:
        seed_from_csv(tmp_csv, clear=clear_products)
        return "✅ Товары обновлены из Google Sheets."

# ===================== Web handlers =====================
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
    ensure_db_ready()

    logo_url = (_get_setting("logo_url", "") or "").strip()

    # ✅ видео могло сохраниться как video_url или hero_video_url
    video_url = (_get_setting("video_url", "") or "").strip()
    if not video_url:
        video_url = (_get_setting("hero_video_url", "") or "").strip()

    hero_url = video_url or logo_url
    hero_type = "video" if video_url else ("image" if logo_url else "")

    return web.json_response({
        "title": STORE_TITLE,
        "logo_url": logo_url,
        "video_url": video_url,
        "hero_url": hero_url,
        "hero_type": hero_type,
    })

async def api_categories(request):
    ensure_db_ready()
    return web.json_response(get_categories())

async def api_subcategories(request):
    ensure_db_ready()
    cat = request.rel_url.query.get("category")
    return web.json_response(get_subcategories(cat))

async def api_products(request):
    ensure_db_ready()
    cat = request.rel_url.query.get("category")
    sub = request.rel_url.query.get("subcategory")
    return web.json_response(get_products(cat, sub))

async def api_order(request):
    ensure_db_ready()
    data = await request.json()

    items, total = [], 0
    for it in data.get("items", []):
        p = get_product(int(it["product_id"]))
        if not p:
            continue
        qty = int(it.get("qty", 1))
        size = (it.get("size") or "")
        items.append({"product_id": p["id"], "size": size, "qty": qty, "price": p["price"]})
        total += p["price"] * qty

    user_id = int(data.get("user_id") or 0)
    username = data.get("username")
    if username is not None:
        username = str(username).strip() or None

    order_id = create_order(
        user_id=user_id,
        username=username,
        full_name=data.get("full_name"),
        phone=data.get("phone"),
        address=data.get("address"),
        comment=data.get("comment"),
        telegram=data.get("telegram"),
        total_price=total,
        items=items,
    )

    await notify_admins(order_id, data, total, items, user=None)
    return web.json_response({"ok": True, "order_id": order_id})

# ---------- IMG PROXY (только картинки) ----------
async def img_proxy(request):
    url = (request.rel_url.query.get("u", "") or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return web.Response(status=400, text="bad url")

    lower = url.lower()
    if lower.endswith((".mp4", ".webm", ".mov")):
        return web.Response(status=400, text="video not allowed")

    # для картинок режем query (опционально)
    if any(ext in lower for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
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
                ctype = resp.headers.get("Content-Type", "application/octet-stream")
                headers = {"Cache-Control": "public, max-age=31536000"}
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

    # Статика /images (для локального видео/картинок, если они в репо)
    if op.isdir("images"):
        app.router.add_static("/images/", path="images", show_index=False)

    app.router.add_get("/api/config", api_config)
    app.router.add_get("/api/categories", api_categories)
    app.router.add_get("/api/subcategories", api_subcategories)
    app.router.add_get("/api/products", api_products)
    app.router.add_post("/api/order", api_order)

    app.router.add_get("/img", img_proxy)
    return app

# ===================== Bot handlers =====================
@dp.message(Command("start"))
async def start(m: Message):
    title_upper = STORE_TITLE.upper()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"Открыть {title_upper}", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    await m.answer(f"{title_upper} — мини-магазин в Telegram. Открой витрину ниже:", reply_markup=kb)

@dp.message(Command("sync"))
async def cmd_sync(m: Message):
    if not _is_admin(m.from_user.id):
        return await m.answer("⛔️ Нет доступа.")
    clear = "clear" in (m.text or "").lower()
    await m.answer("⏳ Обновляю товары из Google Sheets...")
    try:
        res = await sync_from_google(clear_products=clear)
        await m.answer(res)
    except Exception as e:
        logging.exception("sync failed: %s", e)
        await m.answer(f"❌ Ошибка синка: {e}")

async def notify_admins(order_id: int, data: dict, total: int, items_payload: list, user: Optional[User]):
    uname = f"@{user.username}" if (user and user.username) else (f"@{data.get('username')}" if data.get("username") else "—")
    buyer_link = f"<a href='tg://user?id={user.id}'>профиль</a>" if user else (
        f"<a href='tg://user?id={data.get('user_id')}'>профиль</a>" if data.get("user_id") else "—"
    )

    items_text = "\n".join([
        f"• {get_product(it['product_id'])['title']} [{it.get('size') or '—'}] × {it.get('qty',1)} — {it.get('price',0)*it.get('qty',1)} ₽"
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
        qty = int(it.get("qty", 1))
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

    ensure_db_ready()
    logging.info(f"DB_PATH resolved to: {op.abspath(DB_PATH)}")

    app = build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logging.info(f"Web server started on port {PORT} (DB_PATH={DB_PATH})")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())