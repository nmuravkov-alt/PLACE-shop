# vk_export.py
import csv, os, time, requests

# === настройка ===
VK_TOKEN = os.getenv("VK_COMMUNITY_TOKEN", "")   # токен сообщества vk1.a....
GROUP_ID = int(os.getenv("VK_GROUP_ID", "222108341"))  # 222108341 для @placexcom
OWNER_ID = -GROUP_ID
API_URL  = "https://api.vk.com/method/"
API_V    = "5.199"

# Жёсткие категории под твою витрину
KNOWN = [
    "Куртки/Бомберы",
    "Толстовки/Свитера",
    "Брюки/Джинсы",
    "Сумки/Рюкзаки",
    "Футболки/Лонгсливы/Рубашки",
    "Шапки/Кепки",
    "Шорты/Юбки",
    "Обувь",
    "Аксессуары",
]
CLOTHES = "XS,S,M,L,XL,XXL"
SHOES   = ",".join(str(x) for x in range(36,46))

def vk(method, **params):
    params.update({"access_token": VK_TOKEN, "v": API_V})
    r = requests.get(API_URL+method, params=params, timeout=30).json()
    if "error" in r:
        raise RuntimeError(f"VK error {r['error'].get('error_code')}: {r['error'].get('error_msg')}")
    return r["response"]

def get_albums():
    albums = {}
    off = 0
    while True:
        resp = vk("market.getAlbums", owner_id=OWNER_ID, count=100, offset=off)
        for a in resp.get("items", []):
            albums[a["id"]] = a.get("title","")
        off += 100
        if off >= resp.get("count",0): break
        time.sleep(0.35)
    return albums

def map_category(album_title: str) -> str:
    t = (album_title or "").lower()
    if any(w in t for w in ["куртк","бомбер"]): return "Куртки/Бомберы"
    if any(w in t for w in ["толстов","свитер","худи"]): return "Толстовки/Свитера"
    if any(w in t for w in ["брюк","джинс","штаны"]): return "Брюки/Джинсы"
    if any(w in t for w in ["сумк","рюкзак"]): return "Сумки/Рюкзаки"
    if any(w in t for w in ["футболк","лонгслив","рубашк","топ"]): return "Футболки/Лонгсливы/Рубашки"
    if any(w in t for w in ["шапк","кепк","панам"]): return "Шапки/Кепки"
    if any(w in t for w in ["шорт","юбк"]): return "Шорты/Юбки"
    if any(w in t for w in ["обув","кросс","ботинк","кеды"]): return "Обувь"
    return "Аксессуары"

def sizes_for(category: str, title: str, desc: str) -> str:
    s = (title+" "+desc).lower()
    if "one size" in s or "one-size" in s or "onesize" in s: return "ONE SIZE"
    return SHOES if "обув" in (category.lower()) else CLOTHES

def export(csv_path="products_template.csv"):
    if not VK_TOKEN:
        raise SystemExit("Не указан VK_COMMUNITY_TOKEN")
    albums = get_albums()
    items_out = []
    off = 0
    while True:
        resp = vk("market.get", owner_id=OWNER_ID, count=200, offset=off)
        for it in resp.get("items", []):
            title = (it.get("title") or "Товар").strip()
            price = int(round((it.get("price",{}).get("amount",0) or 0)/100.0))
            album_id = (it.get("albums_ids") or [None])[0]
            album_title = albums.get(album_id, "") if album_id else ""
            category = map_category(album_title)
            desc = it.get("description") or ""
            image = it.get("thumb_photo") or ""
            sizes = sizes_for(category, title, desc)
            # availability: 0 — в наличии, 1 — удалён, 2 — недоступен, 3 — не публикуется
            is_active = 1 if it.get("availability",0) == 0 else 0

            items_out.append({
                "title": title,
                "category": category,
                "subcategory": "",
                "price": price,
                "image_url": image,
                "sizes_text": sizes,
                "is_active": is_active,
            })
        off += 200
        if off >= resp.get("count",0): break
        time.sleep(0.35)

    fields = ["title","category","subcategory","price","image_url","sizes_text","is_active"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in items_out: w.writerow(row)
    print(f"Exported {len(items_out)} items → {csv_path}")

if __name__ == "__main__":
    export()
