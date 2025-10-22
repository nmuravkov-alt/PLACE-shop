// web/app.js
const tg = window.Telegram?.WebApp;
tg?.ready();

/** ========= Константы ========= */
const API = "";                         // корень (оставляем пустым: /api/*)
const MANAGER_ID = 6773668793;          // tg://user?id=...
const CLOTHES_SIZES = ["XS","S","M","L","XL","XXL"];
const SHOES_SIZES   = ["36","37","38","39","40","41","42","43","44","45"];

/** ========= Состояние ========= */
let state = {
  category: null,
  cart: [] // [{key,id,title,price,size,qty}]
};

/** ========= DOM ========= */
const $ = (sel) => document.querySelector(sel);
const categoriesEl = $("#categories");
const productsEl   = $("#products");
const cartBtn      = $("#cartBtn");
const cartCount    = $("#cartCount");
const writeBtn     = $("#writeBtn");
const checkoutBtn  = $("#checkoutBtn");
const sheet        = $("#sheet");
const backdrop     = $("#backdrop");

/** ========= Утилиты ========= */
function lockScroll(lock) {
  if (lock) {
    document.body.dataset.scrollY = String(window.scrollY || 0);
    document.body.style.position = "fixed";
    document.body.style.top = `-${document.body.dataset.scrollY}px`;
    document.body.style.left = "0";
    document.body.style.right = "0";
    document.body.style.width = "100%";
  } else {
    const y = parseInt(document.body.dataset.scrollY || "0", 10);
    document.body.style.position = "";
    document.body.style.top = "";
    document.body.style.left = "";
    document.body.style.right = "";
    document.body.style.width = "";
    window.scrollTo(0, y);
  }
}
function openSheet(html) {
  sheet.innerHTML = html;
  sheet.classList.remove("hidden");
  backdrop.classList.remove("hidden");
  lockScroll(true);
  backdrop.onclick = closeSheet;
}
function closeSheet() {
  sheet.classList.add("hidden");
  backdrop.classList.add("hidden");
  sheet.innerHTML = "";
  lockScroll(false);
}
function money(n){ return (n||0).toLocaleString("ru-RU") + " ₽"; }
function updateCartBadge() {
  const n = state.cart.reduce((s,i)=>s+i.qty,0);
  cartCount.textContent = n;
}
function addToCart(p, size) {
  const key = `${p.id}:${size||""}`;
  const f = state.cart.find(it => it.key === key);
  if (f) f.qty += 1;
  else state.cart.push({ key, id:p.id, title:p.title, price:p.price, size:size||"", qty:1 });
  updateCartBadge();
  tg?.HapticFeedback?.impactOccurred("medium");
}

/** ========= API ========= */
async function getJSON(url){
  const r = await fetch(url, { credentials: "same-origin" });
  if(!r.ok) throw new Error("HTTP "+r.status);
  return r.json();
}
async function loadCategories(){
  const data = await getJSON(`${API}/api/categories`);
  return (data||[]).map(c => (typeof c==="string") ? {title:c} : {title:c.title, image_url:c.image_url||""});
}
async function loadProducts(category, sub=""){
  const u = new URL(`${API}/api/products`, window.location.origin);
  if (category)    u.searchParams.set("category", category);
  if (sub != null) u.searchParams.set("subcategory", sub);
  return getJSON(u);
}

/** ========= Рендер ========= */
function renderCategories(list){
  categoriesEl.innerHTML = "";
  const frag = document.createDocumentFragment();
  list.forEach(cat=>{
    const div = document.createElement("div");
    div.className = "cat";
    div.textContent = cat.title;
    div.onclick = () => { state.category = cat.title; drawProducts(); };
    frag.appendChild(div);
  });
  categoriesEl.appendChild(frag);
}

async function drawProducts(){
  productsEl.innerHTML = "";
  const items = await loadProducts(state.category || "");
  items.forEach(p=>{
    // выбираем размеры
    let sizes = [];
    if (p.sizes_text) {
      sizes = String(p.sizes_text).split(",").map(s=>s.trim()).filter(Boolean);
    } else if ((p.category||"").toLowerCase().includes("обув")) {
      sizes = SHOES_SIZES;
    } else {
      sizes = CLOTHES_SIZES;
    }

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="title">${p.title}</div>
      <div class="price">${money(p.price)}</div>
      <div class="size-row">
        <select id="size-${p.id}">
          ${sizes.map(s=>`<option value="${s}">${s}</option>`).join("")}
        </select>
      </div>
      <div style="margin-top:10px">
        <button class="btn primary" id="btn-${p.id}">В корзину</button>
      </div>
    `;
    productsEl.appendChild(card);

    $("#btn-"+p.id).onclick = () => {
      const sz = $("#size-"+p.id).value;
      addToCart(p, sz);
    };
  });
}

/** ========= Корзина ========= */
function renderCartSheet() {
  if (state.cart.length === 0){
    openSheet(`<div class="row"><b>Корзина пуста</b></div>`);
    return;
  }
  const rows = state.cart.map((it,idx)=>`
    <div class="row">
      <div>
        <div><b>${it.title}</b> ${it.size?`[${it.size}]`:""}</div>
        <div>${money(it.price)} × ${it.qty}</div>
      </div>
      <div>
        <button class="qty" data-a="minus" data-i="${idx}">–</button>
        <button class="qty" data-a="plus"  data-i="${idx}">+</button>
        <button class="qty" data-a="rm"    data-i="${idx}">✕</button>
      </div>
    </div>
  `).join("");
  const total = state.cart.reduce((s,i)=>s+i.price*i.qty,0);

  openSheet(`
    <h3>Корзина</h3>
    ${rows}
    <div class="row"><b>Итого:</b><b>${money(total)}</b></div>
    <button id="toCheckout" class="btn primary">Оформить</button>
  `);
}
function openCart(){
  renderCartSheet();
  // делегирование — работает и на iOS
  sheet.onclick = (e)=>{
    const a = e.target?.dataset?.a;
    if(!a) return;
    const i = +e.target.dataset.i;
    if(a==="plus")  state.cart[i].qty++;
    if(a==="minus") state.cart[i].qty = Math.max(1, state.cart[i].qty-1);
    if(a==="rm")    state.cart.splice(i,1);
    updateCartBadge();
    renderCartSheet();            // перерисовываем без закрытия
  };
  sheet.querySelector("#toCheckout")?.addEventListener("click", () => {
    openCheckout();
  }, { once:true });
}

function openCheckout(){
  const total = state.cart.reduce((s,i)=>s+i.price*i.qty,0);
  openSheet(`
    <h3>Оформление</h3>
    <div class="row">
      <label>ФИО</label>
      <input id="fio" placeholder="Иванов Иван"/>
    </div>
    <div class="row">
      <label>Телефон (+7XXXXXXXXXX)</label>
      <input id="phone" inputmode="tel" placeholder="+7XXXXXXXXXX"/>
    </div>
    <div class="row">
      <label>Адрес/СДЭК</label>
      <textarea id="addr" rows="2" placeholder="Город, пункт выдачи..."></textarea>
    </div>
    <div class="row">
      <label>Комментарий к заказу (размер)</label>
      <textarea id="comment" rows="2" placeholder="Например: размер L, цвет черный"></textarea>
    </div>
    <div class="row">
      <label>Telegram (для связи с Вами)</label>
      <input id="tguser" placeholder="@username"/>
    </div>
    <div class="row"><b>Сумма:</b><b>${money(total)}</b></div>
    <button id="submitOrder" class="btn primary">Отправить</button>
  `);

  $("#submitOrder").onclick = async () => {
    const fio   = $("#fio");
    const phone = $("#phone");
    const addr  = $("#addr");
    const comm  = $("#comment");
    const tguser= $("#tguser");

    // строгая проверка телефона: +7XXXXXXXXXX (11 цифр)
    const okPhone = /^\+7\d{10}$/.test(phone.value.trim());
    [fio, phone].forEach(el=>el.classList.remove("bad"));
    if (!fio.value.trim()) { fio.classList.add("bad"); return; }
    if (!okPhone)          { phone.classList.add("bad"); return; }

    const payload = {
      full_name: fio.value.trim(),
      phone: phone.value.trim(),
      address: addr.value.trim(),
      comment: comm.value.trim(),
      telegram: tguser.value.trim(),
      items: state.cart.map(it=>({
        product_id: it.id, size: it.size, qty: it.qty
      }))
    };

    // отправка в бота
    try { tg?.sendData?.(JSON.stringify(payload)); } catch(e){}

    // резервная отправка на backend
    try {
      await fetch(`${API}/api/order`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(payload),
        credentials: "same-origin"
      });
    } catch(e){}

    tg?.HapticFeedback?.notificationOccurred("success");
    closeSheet();
  };
}

/** ========= Кнопки ========= */
writeBtn.onclick = () => {
  const url = `tg://user?id=${MANAGER_ID}`;
  if (tg?.openTelegramLink) tg.openTelegramLink(url);
  else window.location.href = url;
};
checkoutBtn.onclick = () => openCheckout();
cartBtn.onclick = () => openCart();

/** ========= Инициализация ========= */
(async function init(){
  try {
    const cats = await loadCategories();
    renderCategories(cats);
    state.category = (cats[0]?.title) || null;
  } catch(_) {
    // категорий может не быть — ок
  }
  await drawProducts();
  updateCartBadge();

  // ESC закрывает модалку
  window.addEventListener("keydown", (e)=>{
    if (e.key === "Escape" && !sheet.classList.contains("hidden")) closeSheet();
  });
})();
