import json, sqlite3, time

DB = "data.sqlite"

# Фиксированный список категорий c картинками (плейсхолдеры)
FIXED_CATEGORIES = [
    ("Куртки/Бомберы",            "/web/placeholder_clothes.jpg"),
    ("Толстовки/Свитера",         "/web/placeholder_clothes.jpg"),
    ("Брюки/Джинсы",              "/web/placeholder_clothes.jpg"),
    ("Сумки/Рюкзаки",             "/web/placeholder_acc.jpg"),
    ("Футболки/Лонгсливы/Рубашки","/web/placeholder_clothes.jpg"),
    ("Шапки/Кепки",               "/web/placeholder_acc.jpg"),
    ("Шорты/Юбки",                "/web/placeholder_clothes.jpg"),
    ("Обувь",                     "/web/placeholder_clothes.jpg"),
    ("Аксессуары",                "/web/placeholder_acc.jpg"),
]

def _conn():
    return sqlite3.connect(DB)

def get_categories():
    # Возвращаем фиксированный список (как просили)
    return [{"title": t, "image_url": img} for t, img in FIXED_CATEGORIES]

def get_subcategories(category: str):
    # тянем из БД все подкатегории, которые реально есть для категории
    with _conn() as c:
        cur = c.execute("""
            SELECT DISTINCT COALESCE(NULLIF(subcategory,''),'') AS s
            FROM products
            WHERE is_active=1 AND category=?
            ORDER BY s
        """, (category,))
        subs = [r[0] for r in cur.fetchall() if r[0]]
    return subs  # фронт добавит «Все»

def get_products(category: str = None, subcategory: str = None):
    q = "SELECT id,title,price,sizes,image_url FROM products WHERE is_active=1"
    params = []
    if category:
        q += " AND category=?"; params.append(category)
    if subcategory is not None:
        if subcategory == "" or subcategory.lower() == "все":
            q += " AND (subcategory='' OR subcategory IS NULL)"
        else:
            q += " AND subcategory=?"; params.append(subcategory)
    q += " ORDER BY id DESC"

    with _conn() as c:
        cur = c.execute(q, tuple(params))
        rows = cur.fetchall()

    res = []
    for pid, title, price, sizes, img in rows:
        res.append({
            "id": pid,
            "title": title,
            "price": int(price or 0),
            "sizes": [s for s in (sizes or "").split(",") if s],
            "image_url": img
        })
    return res

def get_product(pid: int):
    with _conn() as c:
        cur = c.execute("SELECT id,title,price,sizes,image_url FROM products WHERE id=?", (pid,))
        r = cur.fetchone()
    if not r: return None
    return {
        "id": r[0],
        "title": r[1],
        "price": int(r[2] or 0),
        "sizes": [s for s in (r[3] or "").split(",") if s],
        "image_url": r[4]
    }

def create_order(user_id, username, full_name, phone, address, comment, telegram, total_price, items):
    with _conn() as c:
        cur = c.cursor()
        cur.execute("""
            INSERT INTO orders (created_at,user_id,username,full_name,phone,address,comment,telegram,total_price,items_json)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            int(time.time()), user_id, username, full_name, phone, address, comment, telegram,
            int(total_price or 0), json.dumps(items, ensure_ascii=False)
        ))
        oid = cur.lastrowid
        c.commit()
    return oid
