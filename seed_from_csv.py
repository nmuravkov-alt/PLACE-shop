import csv, sqlite3

DB_PATH = "data.sqlite"

def parse_row(cols):
    if len(cols) < 8:
        cols = cols + [""] * (8 - len(cols))

    title       = (cols[0] or "").strip()
    category    = (cols[1] or "").strip()
    subcategory = (cols[2] or "").strip()
    description = (cols[3] or "").strip()

    price_raw = (cols[4] or "0").replace(",", ".")
    try:    price = int(float(price_raw))
    except: price = 0

    sizes_cols = cols[5:-2] if len(cols) > 7 else []
    sizes = ",".join([s.strip() for s in sizes_cols if s.strip()])

    image_url = (cols[-2] or "").strip() if len(cols) >= 2 else ""
    is_active_raw = (cols[-1] or "1").strip() if len(cols) >= 1 else "1"
    try:    is_active = int(is_active_raw)
    except: is_active = 1

    return {
        "title": title, "category": category, "subcategory": subcategory,
        "description": description, "price": price, "sizes": sizes,
        "image_url": image_url, "is_active": is_active
    }

def insert_product(p, cur):
    if not p["title"] or not p["category"]:
        return
    cur.execute("""
      INSERT INTO products (title, category, subcategory, description, price, sizes, image_url, is_active)
      VALUES (?,?,?,?,?,?,?,?)
    """, (p["title"], p["category"], p["subcategory"], p["description"],
          p["price"], p["sizes"], p["image_url"], p["is_active"]))

def main(csv_path="products_template.csv", clear=False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if clear:
        cur.execute("DELETE FROM products")

    with open(csv_path, newline='', encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        print("No rows in CSV"); conn.commit(); conn.close(); return

    header = [c.strip().lower() for c in rows[0]]
    data_rows = rows[1:] if ("title" in header and "category" in header) else rows

    for cols in data_rows:
        insert_product(parse_row(cols), cur)

    conn.commit(); conn.close()
    print("Imported products into data.sqlite")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="products_template.csv")
    ap.add_argument("--clear", action="store_true")
    a = ap.parse_args()
    main(a.csv, a.clear)
