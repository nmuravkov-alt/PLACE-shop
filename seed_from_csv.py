import csv, sqlite3

DB_PATH = "data.sqlite"

def upsert_product(row, cur):
    title       = (row.get("title") or "").strip()
    category    = (row.get("category") or "").strip()
    subcategory = (row.get("subcategory") or "").strip()
    description = (row.get("description") or "").strip()
    price_raw   = (row.get("price") or "0").replace(",", ".")
    try:
        price = int(float(price_raw))
    except:
        price = 0
    sizes       = ",".join([s.strip() for s in (row.get("sizes") or "").split(",") if s.strip()])
    image_url   = (row.get("image_url") or "").strip()
    is_active   = int(row.get("is_active") or 1)

    if not title or not category:
        return

    cur.execute("""
      INSERT INTO products (title, category, subcategory, description, price, sizes, image_url, is_active)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, category, subcategory, description, price, sizes, image_url, is_active))

def main(csv_path="products_template.csv", clear=False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if clear:
        cur.execute("DELETE FROM products")

    with open(csv_path, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            upsert_product(row, cur)

    conn.commit()
    conn.close()
    print("Imported products into data.sqlite")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="products_template.csv")
    ap.add_argument("--clear", action="store_true")
    a = ap.parse_args()
    main(a.csv, a.clear)
