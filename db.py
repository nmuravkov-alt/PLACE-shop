import sqlite3
import os
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "data.sqlite")

# если models.sql есть в проекте — используем его
MODELS_SQL = os.getenv("MODELS_SQL", "models.sql")


# ---------- schema ----------
def ensure_schema():
    """
    Гарантирует, что таблицы существуют.
    1) Если есть models.sql — применяем его.
    2) Иначе создаём минимальные таблицы напрямую.
    """
    try:
        p = Path(MODELS_SQL)
        if p.is_file():
            sql = p.read_text(encoding="utf-8")
            with sqlite3.connect(DB_PATH) as conn:
                conn.executescript(sql)
            return
    except Exception:
        pass

    # fallback: минимальная схема (чтобы не падало)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              category TEXT,
              subcategory TEXT,
              price INTEGER DEFAULT 0,
              image_url TEXT,
              images_urls TEXT,
              sizes TEXT,
              is_active INTEGER DEFAULT 1,
              description TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
              key TEXT PRIMARY KEY,
              value TEXT
            );

            CREATE TABLE IF NOT EXISTS orders (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER,
              username TEXT,
              full_name TEXT,
              phone TEXT,
              address TEXT,
              comment TEXT,
              telegram TEXT,
              total_price INTEGER DEFAULT 0,
              created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS order_items (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              order_id INTEGER,
              product_id INTEGER,
              size TEXT,
              qty INTEGER DEFAULT 1,
              price INTEGER DEFAULT 0
            );
            """
        )


# ---------- low-level ----------
def connect():
    ensure_schema()
    return sqlite3.connect(DB_PATH)


def dicts(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def trim(s: str) -> str:
    return (s or "").strip()


def norm_py(s: str) -> str:
    return trim(s).lower()


def _variants(s: str):
    t = trim(s)
    if not t:
        return []
    v = {t, t.lower(), t.upper()}
    return [x for x in v if x]


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
            SELECT DISTINCT TRIM(COALESCE(category,'')) AS title
            FROM products
            WHERE is_active = 1 AND TRIM(COALESCE(category,'')) <> ''
            ORDER BY title
            """
        )
        rows = dicts(cur)

    merged = {}
    for r in rows:
        t = trim(r.get("title"))
        if not t:
            continue
        k = norm_py(t)
        if k not in merged:
            merged[k] = t

    return [{"title": merged[k], "image_url": ""} for k in sorted(merged.keys())]


def get_subcategories(category: str):
    cat_in = trim(category)
    if not cat_in:
        return []

    cat_key = norm_py(cat_in)

    with connect() as conn:
        cur = conn.execute(
            """
            SELECT DISTINCT TRIM(COALESCE(category,'')) AS c
            FROM products
            WHERE is_active = 1 AND TRIM(COALESCE(category,'')) <> ''
            """
        )
        cats = [trim(r["c"]) for r in dicts(cur) if trim(r.get("c"))]

        matched = [c for c in cats if norm_py(c) == cat_key]
        if not matched:
            matched = [cat_in]

        placeholders = ",".join(["?"] * len(matched))
        cur2 = conn.execute(
            f"""
            SELECT DISTINCT TRIM(COALESCE(subcategory,'')) AS title
            FROM products
            WHERE is_active = 1
              AND TRIM(COALESCE(subcategory,'')) <> ''
              AND TRIM(COALESCE(category,'')) IN ({placeholders})
            ORDER BY title
            """,
            tuple(matched),
        )
        subs_raw = [trim(r["title"]) for r in dicts(cur2) if trim(r.get("title"))]

    merged = {}
    for s in subs_raw:
        k = norm_py(s)
        if k not in merged:
            merged[k] = s
    return [merged[k] for k in sorted(merged.keys())]


def _row_to_product(r: dict) -> dict:
    raw_sizes = trim(r.get("sizes"))
    sizes = [s.strip() for s in raw_sizes.split(",") if s.strip()] if raw_sizes else []

    images_urls = trim(r.get("images_urls"))

    return {
        "id": r["id"],
        "title": trim(r.get("title")),
        "category": trim(r.get("category")),
        "subcategory": trim(r.get("subcategory")),
        "price": int(r.get("price") or 0),

        "image_url": trim(r.get("image_url")),
        "images_urls": images_urls,

        "description": trim(r.get("description")),

        "sizes": sizes,
        "sizes_text": ",".join(sizes) if sizes else "",
        "is_active": int(r.get("is_active") if r.get("is_active") is not None else 1),
    }


def get_products(category=None, subcategory=None):
    q = "SELECT * FROM products WHERE is_active = 1"
    args = []

    if category:
        vs = _variants(category)
        if vs:
            placeholders = ",".join(["?"] * len(vs))
            q += f" AND TRIM(COALESCE(category,'')) IN ({placeholders})"
            args.extend(vs)

    if subcategory is not None:
        vs = _variants(subcategory)
        if vs:
            placeholders = ",".join(["?"] * len(vs))
            q += f" AND TRIM(COALESCE(subcategory,'')) IN ({placeholders})"
            args.extend(vs)
        else:
            q += " AND TRIM(COALESCE(subcategory,'')) = ''"

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
                    trim(it.get("size")),
                    int(it.get("qty", 1) or 1),
                    int(it.get("price", 0) or 0),
                ),
            )
        conn.commit()
        return order_id