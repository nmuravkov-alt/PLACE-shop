CREATE TABLE IF NOT EXISTS products(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT,
    subcategory TEXT,
    price INTEGER NOT NULL DEFAULT 0,
    image_url TEXT,
    sizes TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    username TEXT,
    full_name TEXT,
    phone TEXT,
    address TEXT,
    comment TEXT,
    telegram TEXT,
    total_price INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS order_items(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    size TEXT,
    qty INTEGER NOT NULL DEFAULT 1,
    price INTEGER NOT NULL DEFAULT 0
);
