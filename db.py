import sqlite3, os

DB_PATH = os.getenv("DB_PATH","data.sqlite")

def connect():
    return sqlite3.connect(DB_PATH)

def dicts(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols,row)) for row in cur.fetchall()]

def get_categories():
    with connect() as conn:
        cur = conn.execute("""
            SELECT COALESCE(category,'') as title,
                   '' as image_url
            FROM products
            WHERE is_active=1 AND COALESCE(category,'')<>''
            GROUP BY category
            ORDER BY category
        """)
        return dicts(cur)

def get_subcategories(category:str):
    if not category:
        return []
    with connect() as conn:
        cur = conn.execute("""
            SELECT COALESCE(subcategory,'') AS title
            FROM products
            WHERE is_active=1 AND COALESCE(category,'')=?
            GROUP BY subcategory
            ORDER BY subcategory
        """,(category,))
        return [r["title"] for r in dicts(cur) if r["title"]]

def _row_to_product(r):
    sizes = []
    if r.get("sizes"):
        sizes = [s.strip() for s in r["sizes"].split(",") if s.strip()]
    return {
        "id": r["id"],
        "title": r["title"],
        "category": r.get("category") or "",
        "subcategory": r.get("subcategory") or "",
        "price": r["price"],
        "image_url": r.get("image_url") or "",
        "sizes": sizes,
        "is_active": r.get("is_active",1)
    }

def get_products(category=None, subcategory=None):
    q = "SELECT * FROM products WHERE is_active=1"
    args = []
    if category:
        q += " AND COALESCE(category,'')=?"
        args.append(category)
    if subcategory is not None:
        q += " AND COALESCE(subcategory,'')=?"
        args.append(subcategory)
    q += " ORDER BY id DESC"
    with connect() as conn:
        cur = conn.execute(q, tuple(args))
        return [_row_to_product(r) for r in dicts(cur)]

def get_product(pid:int):
    with connect() as conn:
        cur = conn.execute("SELECT * FROM products WHERE id=?", (pid,))
        rows = dicts(cur)
        if not rows: return None
        return _row_to_product(rows[0])

def create_order(user_id:int, username:str, full_name:str, phone:str, address:str,
                 comment:str, telegram:str, total_price:int, items:list):
    with connect() as conn:
        cur = conn.execute("""
            INSERT INTO orders(user_id, username, full_name, phone, address, comment, telegram, total_price)
            VALUES(?,?,?,?,?,?,?,?)
        """, (user_id, username, full_name, phone, address, comment, telegram, total_price))
        order_id = cur.lastrowid
        for it in items:
            conn.execute("""
                INSERT INTO order_items(order_id, product_id, size, qty, price)
                VALUES(?,?,?,?,?)
            """, (order_id, it["product_id"], it.get("size"), it.get("qty",1), it.get("price",0)))
        conn.commit()
        return order_id
