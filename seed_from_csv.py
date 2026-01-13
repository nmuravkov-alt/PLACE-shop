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
        # ✅ миграция на случай, если база уже создана без images_urls
        try:
            conn.execute("ALTER TABLE products ADD COLUMN images_urls TEXT")
            conn.commit()
            print("DB migrated: products.images_urls added")
        except Exception:
            # колонка уже есть или таблицы ещё нет — ок
            pass
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


def _clean_gallery(s: str) -> str:
    """
    Приводим галерею к формату: url1|url2|url3
    Разрешаем на вход:
      - уже с | (pipe)
      - с запятыми
      - с пробелами/переносами
    """
    if not s:
        return ""
    raw = str(s).strip()

    # если уже pipe-разделитель — оставляем
    if "|" in raw:
        parts = [p.strip() for p in raw.split("|")]
    else:
        # иначе допускаем "url1, url2, url3"
        parts = [p.strip() for p in raw.replace("\n", " ").split(",")]

    parts = [p for p in parts if p]
    return "|".join(parts)


def insert_product(cur, row: dict) -> bool:
    """
    Обычная вставка товара.

    Поддерживаемые поля CSV (регистр не важен):
      title, category, subcategory, price,
      image_url, images_urls,
      sizes_text|sizes, is_active, description

    images_urls: несколько ссылок через | (pipe)
      пример: url1|url2|url3
    """
    title = (row.get("title") or "").strip()
    if not title or title in ("__LOGO__", "__HERO__"):
        return False  # спец-строки не пишем в products

    image_url = (row.get("image_url") or "").strip()
    images_urls = _clean_gallery(row.get("images_urls") or "")

    # ✅ если галерея пустая, но есть превью — используем превью как 1 фото
    if not images_urls and image_url:
        images_urls = image_url

    cur.execute(
        """
        INSERT INTO products(
            title, category, subcategory, price,
            image_url, images_urls,
            sizes, is_active, description
        )
        VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            title,
            (row.get("category") or "").strip(),
            (row.get("subcategory") or "").strip(),
            as_int(row.get("price"), 0),
            image_url,
            images_urls,
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

                # Спец-строка для ЛОГОТИПА
                if title == "__LOGO__":
                    url = row.get("logo_url") or row.get("image_url") or ""
                    if upsert_setting(cur, "logo_url", url):
                        logo_set = True
                    continue

                # Спец-строка для ВИДЕО/ГЕРОЯ
                if title == "__HERO__":
                    url = row.get("hero_url") or row.get("image_url") or ""
                    if upsert_setting(cur, "hero_video_url", url):
                        hero_set = True
                    continue

                # Обычная товарная строка
                if insert_product(cur, row):
                    inserted += 1

        conn.commit()

    msg = f"✅ Imported {inserted} products from {path} into {DB_PATH}"
    extras = []
    if logo_set:
        extras.append("logo_url saved")
    if hero_set:
        extras.append("hero_video_url saved")
    if extras:
        msg += " (" + ", ".join(extras) + ")"
    print(msg)


def main():
    ap = argparse.ArgumentParser(description="Import products CSV into SQLite.")
    ap.add_argument("--csv", dest="csv", help="Path to CSV file", default=None)
    ap.add_argument("--clear", action="store_true", help="Delete all products before import")
    args = ap.parse_args()

    csv_path = args.csv or CSV_FILE
    seed_from_csv(csv_path, clear=args.clear)


if __name__ == "__main__":
    main()
