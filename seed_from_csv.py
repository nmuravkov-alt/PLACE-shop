import csv, sqlite3, os
from pathlib import Path

# --- Настройки ---
DB_PATH  = os.getenv("DB_PATH", "data.sqlite")

# Можно задать CSV через ENV: CSV_FILE=products_akuma.csv
CSV_FILE = os.getenv("CSV_FILE", "products_template.csv")


# --- Вспомогательные ---
def ensure_schema():
    """
    Прогоняем models.sql — там должны быть:
      - products(...)
      - orders(...), order_items(...)
      - settings(key TEXT PRIMARY KEY, value TEXT)
    """
    sql = Path("models.sql").read_text(encoding="utf-8")
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(sql)


def _as_int(v, default=0):
    try:
        return int(str(v).strip())
    except Exception:
        return default


def _norm_keys(d: dict) -> dict:
    """Приводим ключи CSV к нижнему регистру для стабильного доступа."""
    return { (k or "").strip().lower(): (v or "") for k, v in d.items() }


def _save_logo(cur, url: str):
    """Сохраняем логотип в settings.logo_url (UPSERT)."""
    url = (url or "").strip()
    if not url:
        return False
    cur.execute(
        """
        INSERT INTO settings(key, value)
        VALUES('logo_url', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (url,),
    )
    return True


def _upsert_product(row: dict, cur):
    """
    Обычная вставка товара.
    Поддерживает поля:
      title, category, subcategory, price, image_url, sizes_text|sizes, is_active
    """
    title = (row.get("title") or "").strip()
    if not title or title == "__LOGO__":
        return False  # для __LOGO__ ничего в products не пишем

    cur.execute(
        """
        INSERT INTO products(title, category, subcategory, price, image_url, sizes, is_active)
        VALUES(?,?,?,?,?,?,?)
        """,
        (
            title,
            (row.get("category") or "").strip(),
            (row.get("subcategory") or "").strip(),
            _as_int(row.get("price"), 0),
            (row.get("image_url") or "").strip(),
            (row.get("sizes_text") or row.get("sizes") or "").replace(" ", ""),
            _as_int(row.get("is_active"), 1),
        ),
    )
    return True


# --- Основная логика ---
def main(csv_path=None, clear=False):
    ensure_schema()
    csv_path = csv_path or CSV_FILE
    if not Path(csv_path).is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    inserted = 0
    logo_set = False

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        if clear:
            # чистим только товары; настройки (включая логотип) НЕ трогаем
            cur.execute("DELETE FROM products")

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for raw in reader:
                row = _norm_keys(raw)

                # Спец-строка для логотипа:
                #   title=__LOGO__, image_url=<url>   (или logo_url=<url>)
                if (row.get("title") or "").strip().upper() == "__LOGO__":
                    url = row.get("logo_url") or row.get("image_url") or ""
                    if _save_logo(cur, url):
                        logo_set = True
                    continue  # не пишем в products

                if _upsert_product(row, cur):
                    inserted += 1

        conn.commit()

    msg = f"✅ Imported {inserted} products from {csv_path} into {DB_PATH}"
    if logo_set:
        msg += " (logo_url saved)"
    print(msg)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=False, help="Path to CSV file (optional if CSV_FILE env is set)")
    ap.add_argument("--clear", action="store_true", help="Delete all products before import")
    args = ap.parse_args()
    main(args.csv, args.clear)