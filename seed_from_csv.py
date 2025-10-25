import csv, sqlite3, sys, os

DB_PATH = "data.sqlite"
CSV_PATH = "data.csv"

def ensure_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Основные таблицы
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        category TEXT,
        subcategory TEXT,
        price INTEGER,
        image_url TEXT,
        sizes_text TEXT,
        is_active INTEGER DEFAULT 1,
        description TEXT
    )
    """)
    conn.commit()
    conn.close()


def seed_from_csv(path=CSV_PATH):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM products")

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("title") or "").strip()
            if not title:
                continue

            # ==== hero/video logo ====
            if title in ["__VIDEO__", "__HERO__"]:
                video_url = (row.get("image_url") or "").strip()
                if video_url:
                    print(f"⚙️  Установлен hero_video_url = {video_url}")
                    cur.execute("""
                        INSERT INTO settings(key, value)
                        VALUES('hero_video_url', ?)
                        ON CONFLICT(key) DO UPDATE SET value=excluded.value
                    """, (video_url,))
                continue

            # ==== обычные товары ====
            cur.execute("""
                INSERT INTO products(title, category, subcategory, price, image_url, sizes_text, is_active, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                title,
                (row.get("category") or "").strip(),
                (row.get("subcategory") or "").strip(),
                int(float(row.get("price") or 0)),
                (row.get("image_url") or "").strip(),
                (row.get("sizes") or "").strip(),
                int(row.get("is_active") or 1),
                (row.get("description") or "").strip(),
            ))

    conn.commit()
    conn.close()
    print("✅ Импорт завершён.")


if __name__ == "__main__":
    ensure_db()
    seed_from_csv(sys.argv[1] if len(sys.argv) > 1 else CSV_PATH)