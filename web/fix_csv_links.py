import csv

INPUT_FILE = "Товары из Place.com.csv"      # исходный файл
OUTPUT_FILE = "Товары_исправленные.csv"     # новый файл с исправлениями
DEFAULT_SIZE = "M"                          # можно заменить, например, на "ONE SIZE"

def clean_image_url(url):
    if not url:
        return url
    for ext in [".jpg", ".jpeg", ".png"]:
        if ext in url:
            return url.split(ext)[0] + ext
    return url

with open(INPUT_FILE, "r", encoding="utf-8") as infile, open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as outfile:
    reader = csv.reader(infile)
    writer = csv.writer(outfile)

    for row in reader:
        if len(row) < 7:
            continue  # пропустить странные строки

        # поле с изображением (5-я колонка)
        row[4] = clean_image_url(row[4])

        # поле с размерами (6-я колонка)
        row[5] = DEFAULT_SIZE

        writer.writerow(row)

print("✅ Готово! Исправленный файл сохранён как:", OUTPUT_FILE)
