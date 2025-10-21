
import os, csv, sqlite3, argparse
from contextlib import closing
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DATABASE_PATH", "data.sqlite")

def ensure_schema(conn):
    conn.executescript("""
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
    """)

def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows = list(r)
    return rows

def insert_products(conn, rows):
    cur = conn.cursor()
    for r in rows:
        title = (r.get("title") or "").strip()
        if not title: continue
        desc = (r.get("description") or "").strip()
        price = int(float(r.get("price") or 0))
        photo = (r.get("photo_url") or "").strip()
        cat = (r.get("category") or "").strip()
        sizes = (r.get("sizes") or "ONESIZE").strip()
        is_active = int(r.get("is_active") or 1)
        cur.execute("""
            INSERT INTO products (title, description, price, photo_url, category, sizes, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, desc, price, photo, cat, sizes, is_active))
    conn.commit()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to products CSV file")
    ap.add_argument("--clear", action="store_true", help="Clear existing products before import")
    args = ap.parse_args()

    with closing(sqlite3.connect(DB_PATH)) as conn:
        ensure_schema(conn)
        if args.clear:
            conn.execute("DELETE FROM products")
            conn.commit()
        rows = load_csv(args.csv)
        insert_products(conn, rows)
        print(f"Imported {len(rows)} products into {DB_PATH}")

if __name__ == "__main__":
    main()
