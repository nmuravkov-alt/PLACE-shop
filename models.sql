PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS products (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  title       TEXT NOT NULL,
  category    TEXT NOT NULL,
  subcategory TEXT,
  description TEXT,
  price       INTEGER NOT NULL DEFAULT 0,
  sizes       TEXT,          -- "XS,S,M,L,XL" или "36,37,..." или "ONESIZE"
  image_url   TEXT,
  is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at  INTEGER NOT NULL,
  user_id     INTEGER,
  username    TEXT,
  full_name   TEXT,
  phone       TEXT,
  address     TEXT,
  comment     TEXT,
  telegram    TEXT,
  total_price INTEGER NOT NULL,
  items_json  TEXT NOT NULL
);
