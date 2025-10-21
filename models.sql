-- ===== Schema for PLACE shop with subcategories & sizes =====
DROP TABLE IF EXISTS products;
CREATE TABLE products (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  title       TEXT NOT NULL,
  category    TEXT NOT NULL,
  subcategory TEXT DEFAULT '',
  description TEXT DEFAULT '',
  price       INTEGER NOT NULL,
  sizes       TEXT DEFAULT '',      -- "XS,S,M,L" или "36,37,38,39"
  image_url   TEXT DEFAULT '',
  is_active   INTEGER DEFAULT 1
);

DROP TABLE IF EXISTS orders;
CREATE TABLE orders (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      INTEGER,
  username     TEXT,
  full_name    TEXT,
  phone        TEXT,
  address      TEXT,
  comment      TEXT,
  total_price  INTEGER,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS order_items;
CREATE TABLE order_items (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id   INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  size       TEXT DEFAULT '',
  qty        INTEGER NOT NULL,
  price      INTEGER NOT NULL,
  FOREIGN KEY(order_id)   REFERENCES orders(id),
  FOREIGN KEY(product_id) REFERENCES products(id)
);
