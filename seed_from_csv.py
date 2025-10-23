import csv, sqlite3, os
from pathlib import Path

# --- Настройки ---
DB_PATH = os.getenv("DB_PATH", "data.sqlite")

# Теперь можно указывать CSV-файл через переменную окружения:
# CSV_FILE=products_akuma.csv   или   CSV_FILE=products_layoutplace.csv
CSV_FILE = os.getenv("CSV_FILE", "products_template.csv")

# --- Функции ---
def ensure_schema():
    sql = Path("models.sql").read_text(encoding="utf-8")
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(sql)

def upsert(row, cur):
    title = (row.get("title") or "").strip()
    if not title:
        return
    def as_int(v, default=0):
        try:
            return int(str(v).strip())
        except:
            return default
    cur.execute("""
        INSERT INTO products(title,category,subcategory,price,image_url,sizes,is_active)
        VALUES(?,?,?,?,?,?,?)
    """, (
        title,
        (row.get("category") or "").strip(),
        (row.get("subcategory") or "").strip(),
        as_int(row.get("price"), 0),
        (row.get("image_url") or "").strip(),
        (row.get("sizes_text") or row.get("sizes") or "").replace(" ", ""),
        as_int(row.get("is_active"), 1)
    ))

def main(csv_path=None, clear=False):
    ensure_schema()
    csv_path = csv_path or CSV_FILE
    if not Path(csv_path).is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        if clear:
            cur.execute("DELETE FROM products")
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                upsert(row, cur)
        conn.commit()
    print(f"✅ Imported products from {csv_path} into {DB_PATH}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=False, help="Path to CSV file (optional if CSV_FILE env is set)")
    ap.add_argument("--clear", action="store_true")
    args = ap.parse_args()
    main(args.csv, args.clear)
