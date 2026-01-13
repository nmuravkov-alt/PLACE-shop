import os
import requests
from pathlib import Path
from seed_from_csv import seed_from_csv

CSV_URL = os.getenv("GOOGLE_SHEET_CSV_URL", "").strip()

def sync(clear_products: bool = False) -> str:
    if not CSV_URL:
        raise RuntimeError("GOOGLE_SHEET_CSV_URL is not set")

    r = requests.get(CSV_URL, timeout=30)
    r.raise_for_status()

    tmp = Path("/tmp/products_sheet.csv")
    tmp.write_bytes(r.content)

    # clear=True удалит ТОЛЬКО products (в твоём seed_from_csv именно так)
    seed_from_csv(str(tmp), clear=clear_products)
    return f"✅ Синк выполнен. CSV: {len(r.content)} bytes"

if __name__ == "__main__":
    print(sync(clear_products=False))
