const tg = window.Telegram?.WebApp;
tg?.ready();

// ========= Константы проекта =========
const API = ""; // относительные пути к бекенду
const MANAGER_ID = 6773668793; // tg://user?id=...
const CLOTHES_SIZES = ["XS","S","M","L","XL","XXL"];
const SHOES_SIZES   = ["36","37","38","39","40","41","42","43","44","45"];

// ========= Состояние =========
let state = {
  category: null,
  cart: [] // [{id,title,price,size,qty}]
};

const $ = (sel) => document.querySelector(sel);
const categoriesEl = $("#categories");
const productsEl   = $("#products");
const cartBtn      = $("#cartBtn");
const cartCount    = $("#cartCount");
const writeBtn     = $("#writeBtn");
const checkoutBtn  = $("#checkoutBtn");
const sheet        = $("#sheet");
const backdrop     = $("#backdrop");

// ========= Утилиты =========
function openSheet(html) {
  sheet.innerHTML = html;
  sheet.classList.remove("hidden");
  backdrop.classList.remove("hidden");
  backdrop.onclick = closeSheet;
}
function closeSheet() {
  sheet.classList.add("hidden");
  backdrop.classList.add("hidden");
  sheet.innerHTML = "";
}
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
}
function money(n){ return (n||0).toLocaleString('ru-RU') + " ₽"; }

// ========= API =========
async function getJSON(url){
  const r = await fetch(url);
  if(!r.ok) throw new Error("HTTP "+r.status);
  return r.json();
}

async function loadCategories(){
  const data = await getJSON(`${API}/api/categories`);
  // поддержка форматов: ["А", "B"] или [{title,image_url}]
  return (data||[]).map(c => (typeof c==="string") ? {title:c} : {title:c.title, image_url:c.image_url||""});
}
async function loadProducts(category, sub=""){
  const u = new URL(`${API}/api/products`, location.origin);
  if (category)   u.searchParams.set("category", category);
  if (sub != null) u.searchParams.set("subcategory", sub);
  return getJSON(u);
}

// ========= Рендер =========
function renderCategories(list){
  categoriesEl.innerHTML = "";
  const grid = document.createDocumentFragment();
  list.forEach(cat=>{
    const div = document.createElement("div");
    div.className = "cat";
    div.textContent = cat.title;
    div.onclick = () => { state.category = cat.title; drawProducts(); };
    grid.appendChild(div);
  });
  categoriesEl.appendChild(grid);
}
async function drawProducts(){
  productsEl.innerHTML = "";
  const items = await loadProducts(state.category || "");
  items.forEach(p=>{
    // вычислим набор размеров: если sizes_text есть — используем его; если категория «Обувь» — цифры; иначе — одежда
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
      tg?.HapticFeedback?.impactOccurred("medium");
    };
  });
}

// ========= Корзина =========
function openCart(){
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
        <button data-a="minus" data-i="${idx}">–</button>
        <button data-a="plus"  data-i="${idx}">+</button>
        <button data-a="rm"    data-i="${idx}">✕</button>
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

  sheet.onclick = (e)=>{
    const a = e.target?.dataset?.a;
    if(!a) return;
    const i = +e.target.dataset.i;
    if(a==="plus")  state.cart[i].qty++;
    if(a==="minus") state.cart[i].qty = Math.max(1, state.cart[i].qty-1);
    if(a==="rm")    state.cart.splice(i,1);
    updateCartBadge();
    closeSheet(); openCart();
  };
  $("#toCheckout").onclick = () => { closeSheet(); openCheckout(); };
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

    // валидация телефона по маске +7XXXXXXXXXX
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

    // отправляем в бота
    try { tg?.sendData?.(JSON.stringify(payload)); } catch(e){}

    // резервно продублируем на backend
    try {
      await fetch(`${API}/api/order`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(payload)
      });
    } catch(e){}

    tg?.HapticFeedback?.notificationOccurred("success");
    closeSheet();
  };
}

// ========= Кнопки внизу =========
writeBtn.onclick = () => {
  // открываем чат с менеджером по id
  const url = `tg://user?id=${MANAGER_ID}`;
  if (tg?.openTelegramLink) tg.openTelegramLink(url);
  else window.location.href = url;
};
checkoutBtn.onclick = () => openCheckout();
cartBtn.onclick = () => openCart();

// ========= Инициализация =========
(async function init(){
  try {
    const cats = await loadCategories();
    renderCategories(cats);
    state.category = (cats[0]?.title) || null;
  } catch(e){
    // если категорий нет — просто не рендерим сетку (UI остаётся)
  }
  await drawProducts();
  updateCartBadge();
})();
