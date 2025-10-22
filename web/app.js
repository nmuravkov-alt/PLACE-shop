// === Telegram Bootstrap ===
const tg = window.Telegram?.WebApp;
tg?.expand();

// ---- Константы магазина ----
const CURRENCY = "₽";

// Менеджер — ID и (необяз.) username
const MANAGER_ID = 6773668793;
const MANAGER_USERNAME = ""; // например "layoutplace" (без @). Можно оставить пусто.

// ==== Ссылки на элементы ====
const catGrid = document.getElementById("catGrid");
const productsBox = document.getElementById("products");
const cartBtn = document.getElementById("cartBtn");
const cartCount = document.getElementById("cartCount");

const bottomWrite = document.getElementById("bottomWrite");
const bottomCheckout = document.getElementById("bottomCheckout");

const sheet = document.getElementById("sheet");
const closeSheet = document.getElementById("closeSheet");
const cartList = document.getElementById("cartList");
const orderForm = document.getElementById("orderForm");
const totalRub = document.getElementById("totalRub");
const contactBtn = document.getElementById("contactBtn");
const checkoutBtn = document.getElementById("checkoutBtn");

// ==== Состояние ====
let state = {
  category: null,
  subcategory: null,
  cart: [] // {id,title,price,size,qty,category}
};

// ==== Размеры ====
const CLOTHES = ["XS","S","M","L","XL","XXL"];
const SHOES = Array.from({length: 45-36+1}, (_,i)=> String(36+i));
const ONE = ["ONE SIZE"];

// ==== Утилиты ====
function fmtRub(n){ return `${n.toLocaleString("ru-RU")} ${CURRENCY}` }
function sumCart(){
  return state.cart.reduce((s,i)=> s + i.price * i.qty, 0);
}
function updateCartBadge(){
  const qty = state.cart.reduce((s,i)=> s+i.qty,0);
  cartCount.textContent = String(qty);
}

// ==== API ====
async function getJSON(url){
  const r = await fetch(url, {credentials:"same-origin"});
  if(!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.json();
}

// ==== Рендер категорий ====
async function loadCategories(){
  const cats = await getJSON("/api/categories"); // [{title,image_url}]
  catGrid.innerHTML = "";
  cats.forEach(c=>{
    const div = document.createElement("button");
    div.className = "cat";
    div.innerHTML = `
      <div class="thumb">${c.image_url ? `<img src="${c.image_url}" alt="">` : "📦"}</div>
      <div class="name">${c.title}</div>`;
    div.addEventListener("click",()=>{
      state.category = c.title;
      state.subcategory = null;
      loadProducts();
    });
    catGrid.appendChild(div);
  });
}

// ==== Рендер товаров ====
async function loadProducts(){
  productsBox.innerHTML = "";
  let url = `/api/products?category=${encodeURIComponent(state.category||"")}`;
  if(state.subcategory) url += `&subcategory=${encodeURIComponent(state.subcategory)}`;

  const items = await getJSON(url); // [{id,title,price,image_url,category,sizes?,size_type?}]
  if(!items.length){
    productsBox.innerHTML = `<div class="muted">Товары не найдены</div>`;
    return;
  }
  for (const p of items){
    const card = document.createElement("div");
    card.className = "card";

    const picture = p.image_url ? `<img src="${p.image_url}" alt="">` : "";
    const isShoes = /обув/i.test(p.category||"") || /sneak|shoes/i.test(p.title||"");
    let sizeOptions = CLOTHES;
    if (isShoes) sizeOptions = SHOES;
    if ((p.sizes||"").toUpperCase().includes("ONE")) sizeOptions = ONE;
    if (Array.isArray(p.sizes) && p.sizes.length) sizeOptions = p.sizes;

    const opts = sizeOptions.map(v=>`<option value="${v}">${v}</option>`).join("");

    card.innerHTML = `
      ${picture}
      <div class="title">${p.title}</div>
      <div class="price">${fmtRub(p.price)}</div>
      <div class="row">
        <select data-role="size">${opts}</select>
        <button class="add">В корзину</button>
      </div>
    `;

    const addBtn = card.querySelector(".add");
    const sizeSel = card.querySelector('select[data-role="size"]');

    addBtn.addEventListener("click", ()=>{
      const size = sizeSel.value || "";
      const existed = state.cart.find(i => i.id===p.id && i.size===size);
      if (existed) existed.qty += 1;
      else state.cart.push({id:p.id,title:p.title,price:p.price,size,qty:1,category:p.category||""});
      updateCartBadge();
    });

    productsBox.appendChild(card);
  }
}

// ==== Корзина / оформление ====
function renderCart(){
  cartList.innerHTML = "";
  if(!state.cart.length){
    cartList.innerHTML = `<div class="muted" style="padding:8px 2px">Корзина пуста</div>`;
  } else {
    for (const it of state.cart){
      const row = document.createElement("div");
      row.className = "cart-row";
      row.innerHTML = `
        <div>${it.title} <span class="muted">[${it.size||"—"}]</span> × ${it.qty}</div>
        <div><b>${fmtRub(it.qty * it.price)}</b></div>
      `;
      cartList.appendChild(row);
    }
  }
  totalRub.textContent = fmtRub(sumCart());
}

function openSheet(){
  renderCart();
  sheet.classList.remove("hidden");
}
function closeSheetFn(){
  sheet.classList.add("hidden");
}

cartBtn.addEventListener("click", openSheet);
bottomCheckout.addEventListener("click", openSheet);
closeSheet.addEventListener("click", closeSheetFn);

// Кнопка "Написать" (нижняя и внутри шита)
function openChat(){
  if (window.Telegram?.WebApp?.openTelegramLink) {
    window.Telegram.WebApp.openTelegramLink(`tg://user?id=${MANAGER_ID}`);
  } else if (MANAGER_USERNAME) {
    window.open(`https://t.me/${MANAGER_USERNAME}`, "_blank");
  } else {
    alert("Укажите MANAGER_USERNAME в app.js, чтобы открывать чат через t.me/username");
  }
}
bottomWrite.addEventListener("click", openChat);
contactBtn.addEventListener("click", openChat);

// Проверка формы перед отправкой
function validateForm(){
  const fd = new FormData(orderForm);
  const phone = (fd.get("phone") || "").trim();
  const phoneOk = /^\+7\d{10}$/.test(phone);
  if (!phoneOk){
    alert("Телефон должен быть в формате +7XXXXXXXXXX");
    return null;
  }
  return {
    full_name: (fd.get("full_name")||"").trim(),
    phone,
    address: (fd.get("address")||"").trim(),
    comment: (fd.get("comment")||"").trim(),
    telegram: (fd.get("telegram")||"").trim(),
  };
}

async function submitOrder(){
  if (!state.cart.length){
    alert("Добавьте товары в корзину");
    return;
  }
  const form = validateForm();
  if (!form) return;

  const payload = {
    ...form,
    items: state.cart.map(i => ({
      product_id: i.id,
      size: i.size,
      qty: i.qty
    }))
  };

  // Если запущено внутри мини-аппа — отдаём данные в бота
  if (tg?.sendData){
    tg.sendData(JSON.stringify(payload));
  } else {
    // Фолбэк — REST
    await fetch("/api/order", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });
  }

  // UX: очистить корзину и закрыть
  state.cart = [];
  updateCartBadge();
  closeSheetFn();
  alert("Заявка отправлена! Мы свяжемся с вами.");
}

checkoutBtn.addEventListener("click", submitOrder);

// ==== Старт ====
(async function(){
  try{
    await loadCategories();
    await loadProducts();
  }catch(e){
    console.error(e);
    productsBox.innerHTML = `<div class="muted">Ошибка загрузки</div>`;
  }
})();
