web: bash -lc "python - <<'PY'
import sqlite3, pathlib
sql = open('models.sql','r', encoding='utf-8').read()
conn = sqlite3.connect('data.sqlite')
conn.executescript(sql)
conn.close()
print('✅ DB schema ensured')
PY
python seed_from_csv.py --csv products_template.csv --clear && python bot.py"
