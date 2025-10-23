<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta name="referrer" content="no-referrer"/>
  <title>LAYOUTPLACE Shop</title>

  <!-- обновили версию, чтобы перебить кеш -->
  <link rel="stylesheet" href="./style.css?v=4"/>

  <!-- Telegram WebApp SDK должен грузиться раньше нашего app.js -->
  <script src="https://telegram.org/js/telegram-web-app.js"></script>

  <!-- наш скрипт — обязательно с defer, чтобы DOM успел построиться -->
  <script src="./app.js?v=4" defer></script>
</head>
<body>
  <header class="topbar">
    <div>
      <div id="shopTitle" class="shop-title"></div>
      <div id="subtitle" class="subtitle"></div>
    </div>
    <button id="cartBtn" class="cart-btn" aria-label="Корзина">
      🛒 <span id="cartCount">0</span>
    </button>
  </header>

  <main class="container">
    <div id="categories" class="cat-grid"></div>
    <div id="products" class="products"></div>
  </main>

  <footer class="bottom">
    <button id="writeBtn" class="btn ghost">Написать</button>
    <button id="checkoutBtn" class="btn primary">Оформить</button>
  </footer>

  <div id="sheet" class="sheet hidden"></div>
  <div id="backdrop" class="backdrop hidden"></div>
</body>
</html>