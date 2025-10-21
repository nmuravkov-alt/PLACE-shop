
import sqlite3
import os
from contextlib import closing
from dotenv import load_dotenv
import argparse

load_dotenv()
DB_PATH = os.getenv("DATABASE_PATH", "data.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    price INTEGER NOT NULL,
    photo_url TEXT DEFAULT '',
    category TEXT DEFAULT '',
    sizes TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    full_name TEXT,
    phone TEXT,
    address TEXT,
    comment TEXT,
    total_price INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    size TEXT DEFAULT '',
    qty INTEGER NOT NULL,
    price INTEGER NOT NULL,
    FOREIGN KEY(order_id) REFERENCES orders(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);
"""

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.executescript(SCHEMA)
        conn.commit()

def get_categories():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.execute("SELECT DISTINCT category FROM products WHERE is_active=1 AND category<>'' ORDER BY category")
        return [r[0] for r in cur.fetchall()]

def get_products(category: str | None = None):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        if category and category != "ALL":
            cur = conn.execute("SELECT * FROM products WHERE is_active=1 AND category=? ORDER BY id", (category,))
        else:
            cur = conn.execute("SELECT * FROM products WHERE is_active=1 ORDER BY id")
        return [dict(r) for r in cur.fetchall()]

def get_product(pid: int):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM products WHERE id=? AND is_active=1", (pid,))
        r = cur.fetchone()
        return dict(r) if r else None

def create_order(user_id, username, full_name, phone, address, comment, total_price, items):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO orders (user_id, username, full_name, phone, address, comment, total_price) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, full_name, phone, address, comment, total_price)
        )
        order_id = cur.lastrowid
        for it in items:
            cur.execute(
                "INSERT INTO order_items (order_id, product_id, size, qty, price) VALUES (?, ?, ?, ?, ?)",
                (order_id, it["product_id"], it.get("size",""), it["qty"], it["price"])
            )
        conn.commit()
        return order_id

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="init DB schema")
    args = parser.parse_args()
    if args.init:
        init_db()
        print("DB initialized")
