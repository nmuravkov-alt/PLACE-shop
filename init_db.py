# init_db.py
import sqlite3

with open('models.sql', 'r', encoding='utf-8') as f:
    sql = f.read()

conn = sqlite3.connect('data.sqlite')
conn.executescript(sql)
conn.close()

print('DB schema ensured')
