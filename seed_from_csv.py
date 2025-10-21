import csv, sqlite3

DB_PATH = "data.sqlite"

def parse_row(cols):
    """
    Ожидаемый порядок:
    0 title
    1 category
    2 subcategory
    3 description
    4 price
    5..-3 sizes (может быть много колонок из-за запятых)
    -2 image_url
    -1 is_active
    """
    if len(cols) < 8:
        # добиваем недостающие поля пустыми, чтобы не падать
        cols = cols + [""] * (8 - len(cols))

    title       = (cols[0] or "").strip()
    category    = (cols[1] or "").strip()
    subcategory = (cols[2] or "").strip()
    description = (cols[3] or "").strip()

    price_raw = (cols[4] or "0").replace(",", ".")
    try:
        price = int(float(price_raw))
    except:
        price = 0

    # sizes: всё между индексом 5 и предпоследними 2 полями (image_url, is_active)
    if len(cols) > 7:
        sizes_cols = cols[5:-2]
    else:
        sizes_cols = []
    sizes = ",".join([s.strip() for s in sizes_cols if s.strip()])

    image_url = (cols[-2] or "").strip() if len(cols) >= 2 else ""
    is_active_raw = (cols[-1] or "1").strip() if len(cols) >= 1 else "1"
    try:
        is_active = int(is_active_raw)
    except:
        # если вдруг попало 'M' и т.п. — считаем активным по умолчанию
        is_active = 1

    return {
        "title": title,
        "category": category,
        "subcategory": subcategory,
        "description": description,
        "price": price,
        "sizes": sizes,
        "image_url": image_url,
        "is_active": is_active,
    }

def upsert_product(parsed, cur):
    if not parsed["title"] or not parsed["category"]:
        return
    cur.execute("""
      INSERT INTO products (title, category, subcategory, description, price, sizes, image_url, is_active)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        parsed["title"], parsed["category"], parsed["subcategory"],
        parsed["description"], parsed["price"], parsed["sizes"],
        parsed["image_url"], parsed["is_active"]
    ))

def main(csv_path="products_template.csv", clear=False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if clear:
        cur.execute("DELETE FROM products")

    # читаем построчно как «сырые» колонки, чтобы корректно собрать sizes
    with open(csv_path, newline='', encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("No rows in CSV")
        conn.commit(); conn.close(); return

    # первая строка могла быть заголовком — проверим и скинем её
    header = [c.strip().lower() for c in rows[0]]
    maybe_header = ("title" in header) and ("category" in header)
    data_rows = rows[1:] if maybe_header else rows

    for cols in data_rows:
        parsed = parse_row(cols)
        upsert_product(parsed, cur)

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
