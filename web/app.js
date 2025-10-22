/* ====== LAYOUTPLACE SHOP — фронт без изменения внешнего вида ======
 * Починено:
 * 1) Добавление в корзину и открытие корзины по иконке справа.
 * 2) Кнопка «Написать» — открывает чат с менеджером в Telegram.
 * 3) «Оформить» — форма, валидация телефона +7XXXXXXXXXX, отправка в бот через sendData.
 * 4) Размеры: OUTFIT = XS,S,M,L,XL,XXL; SHOES = 36–45; ONE SIZE.
 * Вёрстку не трогаем — работаем по data-* атрибутам и id.
 * ================================================================ */

(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) tg.expand();

  /* --- Константы --- */
  const MANAGER_ID = 6773668793; // чат «Написать»
  const CLOTHES_SIZES = ["XS","S","M","L","XL","XXL"];
  const SHOES_SIZES   = Array.from({length: 10}, (_,i)=> String(36+i)); // 36..45
  const ONE_SIZE      = ["ONE SIZE"];

  /* --- Селекторы интерфейса (существующие элементы) --- */
  const el = {
    categories:   document.querySelector('[data-el="categories"]'),     // сетка категорий
    products:     document.querySelector('[data-el="products"]'),       // список карточек
    cartBadge:    document.querySelector('[data-el="cart-badge"]'),     // счётчик в иконке
    cartButton:   document.querySelector('[data-action="open-cart"]'),  // иконка корзины справа
    writeBtn:     document.querySelector('[data-action="write"]'),      // «Написать»
    checkoutBtn:  document.querySelector('[data-action="checkout"]'),   // «Оформить» (внизу)
    cartSheet:    document.querySelector('[data-el="cart-sheet"]'),     // нижний слайдер корзины
    cartList:     document.querySelector('[data-el="cart-list"]'),      // список в корзине
    cartTotal:    document.querySelector('[data-el="cart-total"]'),     // сумма в корзине
    formSheet:    document.querySelector('[data-el="form-sheet"]'),     // нижний слайдер формы
    form:         document.querySelector('[data-el="order-form"]'),     // сама форма
    // поля формы
    fFullName:    document.querySelector('[name="full_name"]'),
    fPhone:       document.querySelector('[name="phone"]'),
    fAddress:     document.querySelector('[name="address"]'),
    fComment:     document.querySelector('[name="comment"]'),
    fTelegram:    document.querySelector('[name="telegram"]'),
  };

  /* --- Состояние --- */
  let state = {
    category: null,
    subcategory: "",
    cart: [],            // [{id,title,price,size,qty}]
    productsCache: {},   // cache по category+subcategory
  };

  /* --- Утилиты --- */
  const rub = n => `${n.toLocaleString("ru-RU")} ₽`;
  const setBadge = () => {
    const count = state.cart.reduce((s, it) => s + it.qty, 0);
    if (el.cartBadge) el.cartBadge.textContent = String(count);
  };
  const openSheet = sheet => sheet?.classList.add('is-open');
  const closeSheet = sheet => sheet?.classList.remove('is-open');

  const phoneValid = (v) => {
    // Только +7 и 10 цифр после
    return /^\+7\d{10}$/.test(String(v).replace(/\s/g,''));
  };

  const inferSizes = (p) => {
    // если явно указан тип, используем его
    const t = (p.size_type || "").toLowerCase();
    if (t === 'clothes') return CLOTHES_SIZES;
    if (t === 'shoes')   return SHOES_SIZES;
    if (t === 'onesize') return ONE_SIZE;

    // попытка угадать по категории
    const cat = (p.category || '').toLowerCase();
    if (["обувь","кроссовки","ботинки","sneakers","shoes"].some(k=>cat.includes(k))) return SHOES_SIZES;
    if (["аксессуары","accessories"].some(k=>cat.includes(k))) return ONE_SIZE;
    // по умолчанию — одежда
    return CLOTHES_SIZES;
  };

  /* --- Работа с API --- */
  const api = {
    categories: () => fetch('/api/categories').then(r=>r.json()),
    subcategories: (cat) => fetch(`/api/subcategories?category=${encodeURIComponent(cat||'')}`).then(r=>r.json()),
    products: (cat, sub) => {
      const key = `${cat}|||${sub||''}`;
      if (state.productsCache[key]) return Promise.resolve(state.productsCache[key]);
      return fetch(`/api/products?category=${encodeURIComponent(cat||'')}&subcategory=${encodeURIComponent(sub||'')}`)
        .then(r=>r.json())
        .then(arr => (state.productsCache[key] = arr, arr));
    }
  };

  /* --- Рендер категорий (кнопки уже существуют, просто наполняем из БД порядком) --- */
  async function initCategories() {
    if (!el.categories) return;
    const cats = await api.categories(); // [{title, image_url}] — image_url можем игнорировать
    // твой интерфейс уже содержит блоки с нужными названиями — просто ставим data-cat
    const buttons = el.categories.querySelectorAll('[data-cat-index]');
    const list = cats?.map(c => c.title) || [];
    buttons.forEach((btn,i)=>{
      const titleNode = btn.querySelector('[data-el="cat-title"]');
      const title = list[i] || titleNode?.textContent || '';
      btn.dataset.category = title;
      if (titleNode) titleNode.textContent = title;
      // клик
      btn.addEventListener('click', () => {
        state.category = title;
        state.subcategory = "";
        loadProducts();
      });
    });
    // автозагрузка первой категории
    if (buttons[0]) buttons[0].click();
  }

  /* --- Рендер продуктов в список карточек --- */
  async function loadProducts() {
    if (!el.products || !state.category) return;
    const prods = await api.products(state.category, state.subcategory);
    el.products.innerHTML = prods.map(p => {
      const prices = Number(p.price) || 0;
      const sizes = inferSizes(p);
      const sel = sizes.map(s => `<option value="${s}">${s}</option>`).join('');
      return `
        <div class="card" data-product-id="${p.id}">
          <div class="title">${escapeHtml(p.title || "")}</div>
          <div class="price">${rub(prices)}</div>
          <select class="size" data-el="size">${sel}</select>
          <button class="btn black" data-action="add" data-id="${p.id}">В корзину</button>
        </div>
      `;
    }).join('');
  }

  /* --- Корзина --- */
  function addToCart(product, size) {
    const key = `${product.id}__${size||''}`;
    const found = state.cart.find(i => i.key === key);
    if (found) {
      found.qty += 1;
    } else {
      state.cart.push({
        key,
        id: product.id,
        title: product.title,
        price: Number(product.price) || 0,
        size: size || "",
        qty: 1
      });
    }
    setBadge();
    renderCart();
  }

  function removeFromCart(key) {
    state.cart = state.cart.filter(i => i.key !== key);
    setBadge();
    renderCart();
  }

  function changeQty(key, delta) {
    const it = state.cart.find(i => i.key === key);
    if (!it) return;
    it.qty += delta;
    if (it.qty <= 0) return removeFromCart(key);
    renderCart();
  }

  function renderCart() {
    if (!el.cartList || !el.cartTotal) return;
    if (!state.cart.length) {
      el.cartList.innerHTML = `<div class="muted">Корзина пуста</div>`;
      el.cartTotal.textContent = rub(0);
      return;
    }
    el.cartList.innerHTML = state.cart.map(i => `
      <div class="cart-row" data-key="${i.key}">
        <div class="cart-title">${escapeHtml(i.title)} ${i.size?`<span class="chip">${i.size}</span>`:''}</div>
        <div class="cart-qty">
          <button data-action="minus" class="qbtn">–</button>
          <span>${i.qty}</span>
          <button data-action="plus" class="qbtn">+</button>
        </div>
        <div class="cart-sum">${rub(i.price * i.qty)}</div>
        <button class="cart-remove" data-action="remove">×</button>
      </div>
    `).join('');
    const total = state.cart.reduce((s,i)=> s + i.price*i.qty, 0);
    el.cartTotal.textContent = rub(total);
  }

  /* --- Оформление --- */
  function openCheckout() {
    if (!state.cart.length) {
      toast("Сначала добавьте товары в корзину");
      return;
    }
    openSheet(el.formSheet);
  }

  function submitOrder() {
    const payload = {
      full_name: el.fFullName?.value?.trim() || "",
      phone: (el.fPhone?.value || "").replace(/\s/g,''),
      address: el.fAddress?.value?.trim() || "",
      comment: el.fComment?.value?.trim() || "",
      telegram: el.fTelegram?.value?.trim() || "",
      items: state.cart.map(i => ({
        product_id: i.id,
        size: i.size,
        qty: i.qty
      }))
    };

    // валидация
    if (!payload.full_name) return toast("Укажите ФИО");
    if (!phoneValid(payload.phone)) return toast("Телефон: формат +7XXXXXXXXXX");
    if (!payload.address) return toast("Укажите адрес / СДЭК");

    try {
      tg?.sendData(JSON.stringify(payload));
      toast("Заявка отправлена!");
      closeSheet(el.formSheet);
      closeSheet(el.cartSheet);
      // очищаем корзину
      state.cart = [];
      setBadge();
      renderCart();
    } catch(e) {
      console.error(e);
      // запасной REST
      fetch('/api/order', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      }).then(r=>r.json()).then(() => {
        toast("Заявка отправлена!");
        closeSheet(el.formSheet);
        closeSheet(el.cartSheet);
        state.cart = [];
        setBadge();
        renderCart();
      }).catch(()=> toast("Не удалось отправить заявку, попробуйте ещё раз"));
    }
  }

  /* --- Слушатели --- */
  document.addEventListener('click', async (e) => {
    const t = e.target;

    // Открыть корзину (иконка)
    if (t.closest('[data-action="open-cart"]')) {
      renderCart();
      openSheet(el.cartSheet);
      return;
    }

    // Добавить в корзину
    if (t.closest('[data-action="add"]')) {
      const btn = t.closest('[data-action="add"]');
      const id  = Number(btn.dataset.id);
      const card= btn.closest('[data-product-id]');
      const sizeSel = card?.querySelector('[data-el="size"]');
      const size = sizeSel?.value || "";

      // достаем актуальный продукт из последней загрузки
      const prods = await api.products(state.category, state.subcategory);
      const prod = prods.find(p => Number(p.id) === id);
      if (!prod) return;

      addToCart(prod, size);
      toast("Добавлено в корзину");
      return;
    }

    // Кнопки в корзине
    if (t.closest('[data-el="cart-list"]')) {
      const row = t.closest('.cart-row');
      if (!row) return;
      const key = row.dataset.key;

      if (t.dataset.action === 'minus') return changeQty(key, -1);
      if (t.dataset.action === 'plus')  return changeQty(key, +1);
      if (t.dataset.action === 'remove')return removeFromCart(key);
    }

    // «Написать»
    if (t.closest('[data-action="write"]')) {
      const url = `tg://user?id=${MANAGER_ID}`;
      if (tg?.openTelegramLink) tg.openTelegramLink(url);
      else window.location.href = url;
      return;
    }

    // «Оформить»
    if (t.closest('[data-action="checkout"]')) {
      openCheckout();
      return;
    }

    // Закрытия шитов, если клик по data-close
    if (t.closest('[data-close="sheet"]')) {
      const sh = t.closest('.sheet');
      closeSheet(sh);
      return;
    }
  });

  // Отправка формы (если есть кнопка type=submit)
  el.form?.addEventListener('submit', (e) => {
    e.preventDefault();
    submitOrder();
  });

  /* --- Хелперы UI --- */
  function toast(text) {
    if (tg?.showPopup) {
      tg.showPopup({message: text});
    } else {
      alert(text);
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, m => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'
    }[m]));
  }

  /* --- Старт --- */
  initCategories().catch(console.error);
})();