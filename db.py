import sqlite3

DB_PATH = "data.sqlite"

def get_conn():
    return sqlite3.connect(DB_PATH)

def get_categories():
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT DISTINCT category FROM products WHERE is_active=1 AND category<>'' ORDER BY category")
    rows = [r["category"] for r in cur.fetchall()]
    conn.close()
    return rows

def get_subcategories(category):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.execute("""
        SELECT DISTINCT subcategory
        FROM products
        WHERE is_active=1 AND category=? AND subcategory<>''
        ORDER BY subcategory
    """, (category,))
    rows = [r["subcategory"] for r in cur.fetchall()]
    conn.close()
    return rows

def get_products(category=None, subcategory=None):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM products WHERE is_active=1"
    params = []
    if category:
        sql += " AND category=?"
        params.append(category)
    if subcategory:
        sql += " AND subcategory=?"
        params.append(subcategory)
    sql += " ORDER BY id DESC"
    cur = conn.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        sizes = [s.strip() for s in (r["sizes"] or "").split(",") if s.strip()]
        rows.append({
            "id": r["id"],
            "title": r["title"],
            "category": r["category"],
            "subcategory": r["subcategory"],
            "description": r["description"],
            "price": r["price"],
            "sizes": sizes,
            "image_url": r["image_url"]
        })
    conn.close()
    return rows

def get_product(pid: int):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT * FROM products WHERE id=?", (pid,))
    r = cur.fetchone()
    conn.close()
    if not r:
        return None
    return {
        "id": r["id"],
        "title": r["title"],
        "category": r["category"],
        "subcategory": r["subcategory"],
        "description": r["description"],
        "price": r["price"],
        "sizes": [s.strip() for s in (r["sizes"] or "").split(",") if s.strip()],
        "image_url": r["image_url"]
    }

def create_order(user_id, username, full_name, phone, address, comment, total_price, items):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
      INSERT INTO orders (user_id, username, full_name, phone, address, comment, total_price)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, username, full_name, phone, address, comment, total_price))
    oid = cur.lastrowid
    for it in items:
        cur.execute("""
          INSERT INTO order_items (order_id, product_id, size, qty, price)
          VALUES (?, ?, ?, ?, ?)
        """, (oid, it["product_id"], it.get("size",""), it["qty"], it["price"]))
    conn.commit()
    conn.close()
    return oid
