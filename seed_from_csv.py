import csv, sqlite3, os
from pathlib import Path

DB_PATH = os.getenv("DB_PATH","data.sqlite")

def ensure_schema():
    sql = Path("models.sql").read_text(encoding="utf-8")
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(sql)

def upsert(row, cur):
    title = (row.get("title") or "").strip()
    if not title: return
    def as_int(v, default=0):
        try: return int(str(v).strip())
        except: return default
    cur.execute("""
        INSERT INTO products(title,category,subcategory,price,image_url,sizes,is_active)
        VALUES(?,?,?,?,?,?,?)
    """, (
        title,
        (row.get("category") or "").strip(),
        (row.get("subcategory") or "").strip(),
        as_int(row.get("price"), 0),
        (row.get("image_url") or "").strip(),
        (row.get("sizes") or "").replace(" ", ""),
        as_int(row.get("is_active"), 1)
    ))

def main(csv_path, clear=False):
    ensure_schema()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        if clear: cur.execute("DELETE FROM products")
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                upsert(row, cur)
        conn.commit()
    print("Imported products into data.sqlite")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--clear", action="store_true")
    a = ap.parse_args()
    main(a.csv, a.clear)
