import csv
import os
import sqlite3
from pathlib import Path
import argparse

# --- настройки ---
DB_PATH  = os.getenv("DB_PATH", "data.sqlite")
CSV_FILE = os.getenv("CSV_FILE", "products_template.csv")  # дефолт, если не указан флаг

MODELS_SQL = "models.sql"  # должен содержать таблицы products, orders, order_items, settings


# --- утилиты ---
def ensure_schema():
    sql = Path(MODELS_SQL).read_text(encoding="utf-8")
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(sql)
    print("DB schema ensured")


def as_int(v, default=0):
    try:
        return int(str(v).strip())
    except Exception:
        return default


def norm_keys(d: dict) -> dict:
    """Ключи CSV -> нижний регистр, значения -> строки (или пусто)."""
    return {(k or "").strip().lower(): (v or "") for k, v in d.items()}


def upsert_setting(cur, key: str, value: str) -> bool:
    value = (value or "").strip()
    if not value:
        return False
    cur.execute(
        """
        INSERT INTO settings(key, value)
        VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    return True


def insert_product(cur, row: dict) -> bool:
    """
    Обычная вставка товара.
    Поддерживаемые поля CSV (регистр не важен):
      title, category, subcategory, price, image_url,
      sizes_text|sizes, is_active, description
    """
    title = (row.get("title") or "").strip()
    if not title or title in ("__LOGO__", "__HERO__"):
        return False  # спец-строки не пишем в products

    cur.execute(
        """
        INSERT INTO products(title, category, subcategory, price, image_url, sizes, is_active, description)
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            title,
            (row.get("category") or "").strip(),
            (row.get("subcategory") or "").strip(),
            as_int(row.get("price"), 0),
            (row.get("image_url") or "").strip(),
            (row.get("sizes_text") or row.get("sizes") or "").replace(" ", ""),
            as_int(row.get("is_active"), 1),
            (row.get("description") or "").strip(),
        ),
    )
    return True


# --- основная логика ---
def seed_from_csv(csv_path: str, clear: bool):
    ensure_schema()

    path = csv_path or CSV_FILE
    if not Path(path).is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")

    inserted = 0
    logo_set = False
    hero_set = False

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        if clear:
            cur.execute("DELETE FROM products")

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for raw in reader:
                row = norm_keys(raw)

                title = (row.get("title") or "").strip().upper()

                # Спец-строка для ЛОГОТИПА (старая механика)
                if title == "__LOGO__":
                    url = row.get("logo_url") or row.get("image_url") or ""
                    if upsert_setting(cur, "logo_url", url):
                        logo_set = True
                    continue

                # Спец-строка для ВИДЕО/ГЕРОЯ (новая механика)
                if title == "__HERO__":
                    url = row.get("hero_url") or row.get("image_url") or ""
                    # сюда клади mp4/gif/и т.п.; локальные пути типа /images/.... тоже ок
                    if upsert_setting(cur, "hero_video_url", url):
                        hero_set = True
                    continue

                # Обычная товарная строка
                if insert_product(cur, row):
                    inserted += 1

        conn.commit()

    msg = f"✅ Imported {inserted} products from {path} into {DB_PATH}"
    extras = []
    if logo_set: extras.append("logo_url saved")
    if hero_set: extras.append("hero_video_url saved")
    if extras:
        msg += " (" + ", ".join(extras) + ")"
    print(msg)


def main():
    ap = argparse.ArgumentParser(description="Import products CSV into SQLite.")
    ap.add_argument("--csv", dest="csv", help="Path to CSV file", default=None)
    ap.add_argument("--clear", action="store_true", help="Delete all products before import")
    args = ap.parse_args()

    # если csv не указан флагом, берём из ENV/дефолта
    csv_path = args.csv or CSV_FILE
    seed_from_csv(csv_path, clear=args.clear)


if __name__ == "__main__":
    main()
