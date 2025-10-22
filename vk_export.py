# vk_export.py
import csv, os, time, requests, sys

# --- Конфиг и токены ---
# Для вызовов market.* НУЖЕН именно пользовательский токен!
VK_USER_TOKEN      = os.getenv("VK_USER_TOKEN", "").strip()        # <-- сюда пользовательский токен vk1.a...
VK_COMMUNITY_TOKEN = os.getenv("VK_COMMUNITY_TOKEN", "").strip()   # не используем для market, оставлено на будущее
GROUP_ID           = os.getenv("VK_GROUP_ID", "").strip()          # только цифры, без 'public'
API_URL            = "https://api.vk.com/method/"
API_V              = "5.199"

CLOTHES_SIZES = "XS,S,M,L,XL,XXL"
SHOES_SIZES   = ",".join(str(x) for x in range(36, 46))

def active_token() -> str:
    """
    Для методов market.* обязателен пользовательский токен.
    Если его нет — возвращаем пустую строку (импорт будет пропущен).
    """
    if VK_USER_TOKEN:
        return VK_USER_TOKEN
    return ""

# --- Категории/размеры ---
def map_category(album_title: str) -> str:
    t = (album_title or "").lower()
    if any(w in t for w in ["куртк","бомбер"]):                     return "Куртки/Бомберы"
    if any(w in t for w in ["толстов","свитер","худи"]):            return "Толстовки/Свитера"
    if any(w in t for w in ["брюк","джинс","штаны"]):               return "Брюки/Джинсы"
    if any(w in t for w in ["сумк","рюкзак"]):                      return "Сумки/Рюкзаки"
    if any(w in t for w in ["футболк","лонгслив","рубашк","топ"]):  return "Футболки/Лонгсливы/Рубашки"
    if any(w in t for w in ["шапк","кепк","панам"]):                return "Шапки/Кепки"
    if any(w in t for w in ["шорт","юбк"]):                         return "Шорты/Юбки"
    if any(w in t for w in ["обув","кросс","ботинк","кеды"]):       return "Обувь"
    return "Аксессуары"

def sizes_for(category: str, title: str, desc: str) -> str:
    s = (title + " " + (desc or "")).lower()
    if "one size" in s or "one-size" in s or "onesize" in s:
        return "ONE SIZE"
    return SHOES_SIZES if "обув" in (category or "").lower() else CLOTHES_SIZES

# --- VK API ---
def vk(method, **params):
    token = active_token()
    if not token:
        raise RuntimeError("Нет VK_USER_TOKEN: методы market.* недоступны с токеном сообщества")
    params.update({"access_token": token, "v": API_V})
    r = requests.get(API_URL + method, params=params, timeout=30)
    data = r.json()
    if "error" in data:
        code = data["error"].get("error_code")
        msg  = data["error"].get("error_msg")
        raise RuntimeError(f"VK error {code}: {msg}")
    return data["response"]

def get_albums(owner_id: int):
    albums = {}
    offset = 0
    while True:
        resp = vk("market.getAlbums", owner_id=owner_id, count=100, offset=offset)
        for a in resp.get("items", []):
            albums[a["id"]] = a.get("title", "")
        offset += 100
        if offset >= resp.get("count", 0):
            break
        time.sleep(0.34)
    return albums

# --- Main ---
def main():
    # Мягко пропускаем импорт, чтобы деплой не падал
    if not GROUP_ID.isdigit() or not VK_USER_TOKEN:
        print("vk_export.py: пропуск — нужен VK_USER_TOKEN и числовой VK_GROUP_ID", file=sys.stderr)
        return

    group_num = int(GROUP_ID)
    owner_id = -group_num  # для сообществ owner_id всегда отрицательный

    try:
        albums = get_albums(owner_id)
    except Exception as e:
        print(f"Не удалось получить альбомы: {e}", file=sys.stderr)
        albums = {}

    items_out = []
    offset = 0
    total = 0
    while True:
        resp = vk("market.get", owner_id=owner_id, count=200, offset=offset, extended=0)
        total = resp.get("count", 0)
        for it in resp.get("items", []):
            title = (it.get("title") or "Товар").strip()
            desc  = it.get("description") or ""
            # price.amount приходит в копейках (строкой/числом)
            amount = it.get("price", {}).get("amount", 0) or 0
            try:
                amount = int(amount)
            except:
                try:
                    amount = int(float(amount))
                except:
                    amount = 0
            price = int(round(amount / 100.0))

            album_id    = (it.get("albums_ids") or [None])[0]
            album_title = albums.get(album_id, "") if album_id else ""
            category    = map_category(album_title)
            image       = it.get("thumb_photo") or ""
            sizes       = sizes_for(category, title, desc)
            # availability: 0 — в наличии, остальные — нет
            is_active   = 1 if it.get("availability", 0) == 0 else 0

            items_out.append({
                "title":       title,
                "category":    category,
                "subcategory": "",
                "price":       price,
                "image_url":   image,
                "sizes_text":  sizes,
                "is_active":   is_active,
            })
        offset += 200
        if offset >= total:
            break
        time.sleep(0.34)

    with open("products_template.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "title","category","subcategory","price","image_url","sizes_text","is_active"
        ])
        w.writeheader()
        for row in items_out:
            w.writerow(row)

    print(f"Exported {len(items_out)} items → products_template.csv")

if __name__ == "__main__":
    main()
