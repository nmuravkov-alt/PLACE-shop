import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "data.sqlite")


# ---------- low-level ----------
def connect():
    return sqlite3.connect(DB_PATH)


def dicts(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def norm(s: str) -> str:
    """Железно нормализуем: trim + lower."""
    return (s or "").strip().lower()


# ---------- settings (логотип и любые key/value) ----------
def get_setting(key: str, default: str = "") -> str:
    with connect() as conn:
        cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else default


def set_setting(key: str, value: str) -> None:
    """Создаёт или обновляет настройку (SQLite UPSERT)."""
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
    """Удобная обёртка — тянет URL логотипа (ключ 'logo_url')."""
    return get_setting("logo_url", "")


# ---------- catalog ----------
def get_categories():
    """
    Возвращаем уникальные категории.
    Нормализуем (trim+lower), но показываем "красивое" имя как первое встретившееся.
    """
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT
              MIN(TRIM(category)) AS title
            FROM products
            WHERE is_active = 1 AND TRIM(COALESCE(category,'')) <> ''
            GROUP BY LOWER(TRIM(category))
            ORDER BY LOWER(TRIM(category))
            """
        )
        rows = dicts(cur)
        # формат как у фронта: [{title:'...', image_url:''}, ...]
        return [{"title": (r.get("title") or "").strip(), "image_url": ""} for r in rows]


def get_subcategories(category: str):
    """
    Подкатегории для выбранной категории.
    category сравниваем по нормализованному значению.
    """
    cat_key = norm(category)
    if not cat_key:
        return []

    with connect() as conn:
        cur = conn.execute(
            """
            SELECT
              MIN(TRIM(subcategory)) AS title
            FROM products
            WHERE is_active = 1
              AND LOWER(TRIM(COALESCE(category,''))) = ?
              AND TRIM(COALESCE(subcategory,'')) <> ''
            GROUP BY LOWER(TRIM(subcategory))
            ORDER BY LOWER(TRIM(subcategory))
            """,
            (cat_key,),
        )
        return [(r.get("title") or "").strip() for r in dicts(cur) if (r.get("title") or "").strip()]


def _row_to_product(r: dict) -> dict:
    raw_sizes = (r.get("sizes") or "").strip()
    sizes = [s.strip() for s in raw_sizes.split(",") if s.strip()] if raw_sizes else []

    images_urls = (r.get("images_urls") or "").strip()  # "url1|url2|url3"

    return {
        "id": r["id"],
        "title": (r.get("title") or "").strip(),
        "category": (r.get("category") or "").strip(),
        "subcategory": (r.get("subcategory") or "").strip(),
        "price": int(r.get("price") or 0),

        "image_url": (r.get("image_url") or "").strip(),
        "images_urls": images_urls,  # ✅ отдаём на фронт

        "description": (r.get("description") or "").strip(),

        "sizes": sizes,
        "sizes_text": ",".join(sizes) if sizes else "",
        "is_active": int(r.get("is_active") if r.get("is_active") is not None else 1),
    }


def get_products(category=None, subcategory=None):
    """
    Фильтры делаем по нормализованным значениям (trim+lower),
    чтобы товары не пропадали из-за лишних пробелов/регистра.
    """
    q = "SELECT * FROM products WHERE is_active = 1"
    args = []

    if category:
        q += " AND LOWER(TRIM(COALESCE(category,''))) = ?"
        args.append(norm(category))

    # если subcategory передали (даже пустую) — фильтруем
    if subcategory is not None:
        q += " AND LOWER(TRIM(COALESCE(subcategory,''))) = ?"
        args.append(norm(subcategory))

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
                    (it.get("size") or "").strip(),
                    int(it.get("qty", 1) or 1),
                    int(it.get("price", 0) or 0),
                ),
            )
        conn.commit()
        return order_id