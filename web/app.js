const tg = window.Telegram.WebApp;
tg.expand();

const api = {
  async json(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  },
  categories: () => api.json("/api/categories"),
  subcategories: (category) => api.json("/api/subcategories?category=" + encodeURIComponent(category)),
  products: (params) => {
    const qs = new URLSearchParams(params || {});
    return api.json("/api/products?" + qs.toString());
  }
};

// --- State ---
let state = {
  view: "categories", // categories | subcategories | products | cart | checkout
  category: null,
  subcategory: null,
  cart: [] // {product_id, title, price, size, qty, image_url}
};

// --- UI helpers ---
const $ = (sel) => document.querySelector(sel);
function page(html) { $("#app").innerHTML = html; }

function topbar(title, onBack) {
  return `
    <div class="topbar">
      ${onBack ? `<button class="back" id="backBtn">←</button>` : '<div></div>'}
      <div class="title">${title}</div>
      <button class="cart" id="cartBtn">🛒</button>
    </div>
  `;
}

function grid(items) {
  return `<div class="grid">${items.join("")}</div>`;
}

// --- Views ---
async function showCategories() {
  state.view = "categories"; state.category = null; state.subcategory = null;
  const cats = await api.categories();
  const items = cats.map(c =>
    `<div class="card cat" data-cat="${c}">
       <img src="/web/placeholder_clothes.jpg" alt="">
       <div class="name">${c}</div>
     </div>`);
  page(`
    ${topbar("PLACE", null)}
    <div class="pad">${grid(items)}</div>
  `);
  bindCommon();
  document.querySelectorAll(".card.cat").forEach(el => {
    el.addEventListener("click", async () => {
      state.category = el.dataset.cat;
      const subs = await api.subcategories(state.category);
      if (subs.length) showSubcategories(); else showProducts();
    });
  });
}

async function showSubcategories() {
  state.view = "subcategories";
  const subs = await api.subcategories(state.category);
  const items = subs.map(s =>
    `<div class="card sub" data-sub="${s}">
       <img src="/web/placeholder_acc.jpg" alt="">
       <div class="name">${s}</div>
     </div>`);
  page(`
    ${topbar(state.category, () => showCategories())}
    <div class="pad">${grid(items)}</div>
  `);
  bindCommon(true);
  document.querySelectorAll(".card.sub").forEach(el => {
    el.addEventListener("click", () => {
      state.subcategory = el.dataset.sub;
      showProducts();
    });
  });
}

async function showProducts() {
  state.view = "products";
  const products = await api.products({
    category: state.category || "",
    subcategory: state.subcategory || ""
  });

  const cards = products.map(p => {
    const sizes = (p.sizes && p.sizes.length ? p.sizes : ["—"]).map(s => `<option value="${s}">${s}</option>`).join("");
    return `
      <div class="pitem" data-id="${p.id}">
        <img class="pimg" src="${p.image_url || '/web/placeholder_acc.jpg'}" alt="">
        <div class="ptitle">${p.title}</div>
        <div class="pprice">${p.price} ₽</div>
        <select class="psize">${sizes}</select>
        <button class="add">В корзину</button>
      </div>
    `;
  }).join("");

  page(`
    ${topbar(state.subcategory || state.category || "Товары", () => {
      if (state.subcategory) { state.subcategory = null; showCategories(); }
      else showCategories();
    })}
    <div class="pad products">${cards || '<div class="empty">Пока пусто</div>'}</div>
  `);
  bindCommon(true);
  document.querySelectorAll(".pitem .add").forEach(btn => {
    btn.addEventListener("click", () => {
      const el = btn.closest(".pitem");
      const id = Number(el.dataset.id);
      const title = el.querySelector(".ptitle").textContent;
      const price = Number(el.querySelector(".pprice").textContent.replace(/\D/g,""));
      const size = el.querySelector(".psize").value || "";
      const img = el.querySelector(".pimg").src;

      const existing = state.cart.find(i => i.product_id === id && i.size === size);
      if (existing) existing.qty += 1;
      else state.cart.push({product_id: id, title, price, size, qty: 1, image_url: img});

      tg.HapticFeedback.notificationOccurred("success");
    });
  });
}

function showCart() {
  state.view = "cart";
  const items = state.cart.map((i, idx) => `
    <div class="citem">
      <img src="${i.image_url}" alt="">
      <div class="cmain">
        <div class="ctitle">${i.title} ${i.size ? `(${i.size})` : ""}</div>
        <div class="crow">
          <button class="dec" data-idx="${idx}">−</button>
          <div class="qty">${i.qty}</div>
          <button class="inc" data-idx="${idx}">+</button>
          <div class="price">${i.price * i.qty} ₽</div>
        </div>
      </div>
    </div>`).join("");
  const total = state.cart.reduce((s,i)=>s+i.price*i.qty,0);

  page(`
    ${topbar("Корзина", () => showProducts())}
    <div class="pad">${items || '<div class="empty">Корзина пуста</div>'}</div>
    <div class="bottom">
      <div class="total">Итого: <b>${total} ₽</b></div>
      <button id="toCheckout" ${total? "": "disabled"}>Оформить</button>
    </div>
  `);
  bindCommon(true);

  $(".bottom #toCheckout")?.addEventListener("click", showCheckout);
  document.querySelectorAll(".inc,.dec").forEach(b=>{
    b.addEventListener("click", ()=>{
      const idx = Number(b.dataset.idx);
      if (b.classList.contains("inc")) state.cart[idx].qty += 1;
      else state.cart[idx].qty = Math.max(0, state.cart[idx].qty - 1);
      state.cart = state.cart.filter(i=>i.qty>0);
      showCart();
    });
  });
}

function showCheckout() {
  state.view = "checkout";
  const total = state.cart.reduce((s,i)=>s+i.price*i.qty,0);
  page(`
    ${topbar("Оформление", () => showCart())}
    <div class="pad form">
      <input id="fio" placeholder="ФИО">
      <input id="phone" placeholder="Телефон">
      <input id="addr" placeholder="Адрес/СДЭК">
      <textarea id="comment" placeholder="Комментарий (необязательно)"></textarea>
    </div>
    <div class="bottom">
      <div class="total">Итого: <b>${total} ₽</b></div>
      <button id="pay" ${total? "": "disabled"}>Отправить заказ</button>
    </div>
  `);
  bindCommon(true);
  $("#pay").addEventListener("click", ()=>{
    const payload = {
      full_name: $("#fio").value.trim(),
      phone: $("#phone").value.trim(),
      address: $("#addr").value.trim(),
      comment: $("#comment").value.trim(),
      items: state.cart.map(i => ({ product_id:i.product_id, size:i.size, qty:i.qty }))
    };
    tg.sendData(JSON.stringify(payload));
    tg.close();
  });
}

function bindCommon(withBack=true){
  $("#cartBtn")?.addEventListener("click", showCart);
  $("#backBtn")?.addEventListener("click", ()=>{
    if (state.view === "subcategories") showCategories();
    else if (state.view === "products") showCategories();
    else if (state.view === "cart") showProducts();
    else if (state.view === "checkout") showCart();
  });
}

// --- Start ---
document.addEventListener("DOMContentLoaded", showCategories);
