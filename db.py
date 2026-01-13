import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "data.sqlite")
MODELS_SQL = os.getenv("MODELS_SQL", "models.sql")

_schema_ready = False


# ---------- schema / migrations ----------
def ensure_schema():
    """
    1) Создаёт таблицы из models.sql (если их нет)
    2) Делает лёгкую миграцию: добавляет колонку images_urls, если её нет
    """
    global _schema_ready
    if _schema_ready:
        return

    # 1) базовая схема
    if Path(MODELS_SQL).is_file():
        sql = Path(MODELS_SQL).read_text(encoding="utf-8")
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript(sql)
            conn.commit()
    else:
        # fallback (на всякий): минимально нужные таблицы
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings(
                  key TEXT PRIMARY KEY,
                  value TEXT
                );

                CREATE TABLE IF NOT EXISTS products(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT NOT NULL,
                  category TEXT,
                  subcategory TEXT,
                  price INTEGER DEFAULT 0,
                  image_url TEXT,
                  sizes TEXT,
                  is_active INTEGER DEFAULT 1,
                  description TEXT
                );

                CREATE TABLE IF NOT EXISTS orders(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  full_name TEXT,
                  phone TEXT,
                  address TEXT,
                  comment TEXT,
                  telegram TEXT,
                  total_price INTEGER DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS order_items(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  order_id INTEGER,
                  product_id INTEGER,
                  size TEXT,
                  qty INTEGER DEFAULT 1,
                  price INTEGER DEFAULT 0
                );
                """
            )
            conn.commit()

    # 2) миграция: products.images_urls
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("PRAGMA table_info(products)")
        cols = [r[1] for r in cur.fetchall()]  # name is index 1
        if "images_urls" not in cols:
            conn.execute("ALTER TABLE products ADD COLUMN images_urls TEXT DEFAULT ''")
            conn.commit()

    _schema_ready = True


# ---------- low-level ----------
def connect():
    ensure_schema()
    return sqlite3.connect(DB_PATH)


def dicts(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# ---------- settings ----------
def get_setting(key: str, default: str = "") -> str:
    with connect() as conn:
        cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else default


def set_setting(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()


def get_logo_url() -> str:
    return get_setting("logo_url", "")


# ---------- catalog ----------
def get_categories():
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT COALESCE(category,'') AS title,
                   '' AS image_url
            FROM products
            WHERE is_active = 1 AND COALESCE(category,'') <> ''
            GROUP BY category
            ORDER BY category
            """
        )
        return dicts(cur)


def get_subcategories(category: str):
    if not category:
        return []
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT COALESCE(subcategory,'') AS title
            FROM products
            WHERE is_active = 1 AND COALESCE(category,'') = ?
            GROUP BY subcategory
            ORDER BY subcategory
            """,
            (category,),
        )
        return [r["title"] for r in dicts(cur) if r["title"]]


def _row_to_product(r: dict) -> dict:
    raw_sizes = (r.get("sizes") or "").strip()
    sizes = [s.strip() for s in raw_sizes.split(",") if s.strip()] if raw_sizes else []

    images_urls = (r.get("images_urls") or "").strip()

    return {
        "id": r["id"],
        "title": r["title"],
        "category": r.get("category") or "",
        "subcategory": r.get("subcategory") or "",
        "price": r.get("price", 0) or 0,

        "image_url": r.get("image_url") or "",
        "images_urls": images_urls,  # ✅ важно для галереи

        "description": r.get("description") or "",

        "sizes": sizes,
        "sizes_text": ",".join(sizes) if sizes else "",
        "is_active": r.get("is_active", 1),
    }


def get_products(category=None, subcategory=None):
    q = "SELECT * FROM products WHERE is_active = 1"
    args = []
    if category:
        q += " AND COALESCE(category,'') = ?"
        args.append(category)
    if subcategory is not None:
        q += " AND COALESCE(subcategory,'') = ?"
        args.append(subcategory)
    q += " ORDER BY id DESC"

    with connect() as conn:
        cur = conn.execute(q, tuple(args))
        return [_row_to_product(r) for r in dicts(cur)]


def get_product(pid: int):
    with connect() as conn:
        cur = conn.execute("SELECT * FROM products WHERE id = ?", (pid,))
        rows = dicts(cur)
        return _row_to_product(rows[0]) if rows else None


# ---------- orders ----------
def create_order(
    user_id: int,
    username: str,
    full_name: str,
    phone: str,
    address: str,
    comment: str,
    telegram: str,
    total_price: int,
    items: list,
):
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO orders(user_id, username, full_name, phone, address, comment, telegram, total_price)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (user_id, username, full_name, phone, address, comment, telegram, total_price),
        )
        order_id = cur.lastrowid

        for it in items:
            conn.execute(
                """
                INSERT INTO order_items(order_id, product_id, size, qty, price)
                VALUES(?,?,?,?,?)
                """,
                (
                    order_id,
                    it["product_id"],
                    it.get("size"),
                    it.get("qty", 1),
                    it.get("price", 0),
                ),
            )
        conn.commit()
        return order_id