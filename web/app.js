// ===== helpers =====
const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand?.(); }

const grid = document.getElementById("grid");
const categoriesEl = document.getElementById("categories");
const subSelect = document.getElementById("subSelect");
const cartBtn = document.getElementById("cartBtn");
const cartCount = document.getElementById("cartCount");
const contactBtn = document.getElementById("contactBtn");
const checkoutBtn = document.getElementById("checkoutBtn");
const checkoutModal = document.getElementById("checkoutModal");
const orderForm = document.getElementById("orderForm");
const phoneInput = document.getElementById("phone");
const cancelOrder = document.getElementById("cancelOrder");

let currentCategory = null;
let cart = []; // {id,title,price,size,qty,category}

// phone mask/validation: allow "+7" then digits, keep only + and digits in view
phoneInput.addEventListener("input", () => {
  let v = phoneInput.value.replace(/[^\d+]/g, "");
  if (!v.startsWith("+7")) v = "+7" + v.replace(/\D/g, "").replace(/^7/, "");
  // trim to "+7" + 10 digits
  v = v.slice(0, 12);
  phoneInput.value = v;
  // live validity
  phoneInput.setCustomValidity(/^\+7\d{10}$/.test(v) ? "" : "Следуйте формату: +7XXXXXXXXXX");
});

// open/close modal
checkoutBtn.addEventListener("click", () => checkoutModal.showModal());
cancelOrder.addEventListener("click", () => checkoutModal.close());

// contact button: open DM to менеджера (замени id при желании)
contactBtn.addEventListener("click", () => {
  // если есть username – открываем compose, иначе просто подсветим поле Telegram
  document.getElementById("telegram")?.focus();
});

// cart helpers
function updateCartBadge() {
  const n = cart.reduce((s, i) => s + i.qty, 0);
  cartCount.textContent = n;
  checkoutBtn.disabled = n === 0;
}

function addToCart(product, size) {
  const key = `${product.id}|${size}`;
  const ex = cart.find(i => `${i.id}|${i.size}` === key);
  if (ex) ex.qty += 1;
  else cart.push({ id: product.id, title: product.title, price: product.price, category: product.category, size, qty: 1 });
  updateCartBadge();
}

cartBtn.addEventListener("click", () => {
  if (cart.length === 0) {
    alert("Корзина пуста");
    return;
  }
  const lines = cart.map(i => `${i.title} [${i.size}] × ${i.qty} — ${i.price * i.qty} ₽`);
  alert("Корзина:\n\n" + lines.join("\n"));
});

// ===== sizes logic =====
function getSizesForCategory(category) {
  const c = (category || "").toLowerCase();
  // одежда
  if (
    c.includes("футболк") || c.includes("лонгслив") || c.includes("рубаш")
    || c.includes("толстовк") || c.includes("свитер")
    || c.includes("куртк") || c.includes("бомбер")
    || c.includes("джинс") || c.includes("брюк")
    || c.includes("юбк") || c.includes("шорт")
  ) {
    return ["XS", "S", "M", "L", "XL", "XXL"];
  }
  // обувь
  if (c.includes("обув") || c.includes("кросс")) {
    return Array.from({ length: 10 }, (_, i) => String(36 + i)); // 36–45
  }
  // шапки/кепки/аксессуары/сумки
  return ["ONE SIZE"];
}

function createSizeSelect(product) {
  const sizes = getSizesForCategory(product.category || "");
  const select = document.createElement("select");
  select.className = "size-select";
  sizes.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s; opt.textContent = s;
    select.appendChild(opt);
  });
  return select;
}

// ===== rendering =====
async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function loadCategories() {
  const cats = await fetchJSON("/api/categories");
  categoriesEl.innerHTML = "";
  cats.forEach(c => {
    const el = document.createElement("button");
    el.className = "cat";
    el.innerHTML = `<img src="${c.image_url || "/web/placeholder_clothes.jpg"}" alt="">
                    <div class="t">${c.title}</div>`;
    el.addEventListener("click", () => pickCategory(c.title));
    categoriesEl.appendChild(el);
  });
}

async function pickCategory(catTitle) {
  currentCategory = catTitle;
  // подкатегории
  const subs = await fetchJSON(`/api/subcategories?category=${encodeURIComponent(catTitle)}`);
  subSelect.innerHTML = "";
  if (subs && subs.length) {
    subSelect.hidden = false;
    const allOpt = new Option("Все", "", true, true);
    subSelect.appendChild(allOpt);
    subs.forEach(s => subSelect.appendChild(new Option(s, s)));
  } else {
    subSelect.hidden = true;
  }
  await renderProducts();
}

async function renderProducts() {
  const sub = subSelect.hidden ? "" : (subSelect.value || "");
  const url = `/api/products?category=${encodeURIComponent(currentCategory || "")}&subcategory=${encodeURIComponent(sub)}`;
  const items = await fetchJSON(url);
  grid.innerHTML = "";
  items.forEach(p => {
    const card = document.createElement("div");
    card.className = "card";

    card.innerHTML = `
      <div class="title">${p.title}</div>
      <div class="price">${(p.price ?? 0).toLocaleString("ru-RU")} ₽</div>
    `;

    const sizeSelect = createSizeSelect(p);
    card.appendChild(sizeSelect);

    const btn = document.createElement("button");
    btn.className = "btn primary";
    btn.textContent = "В корзину";
    btn.addEventListener("click", () => addToCart(p, sizeSelect.value));
    card.appendChild(btn);

    grid.appendChild(card);
  });
}

// подкатегория меняется — перегружаем товары
subSelect.addEventListener("change", renderProducts);

// ===== checkout (sendData) =====
orderForm.addEventListener("submit", (e) => {
  e.preventDefault();

  // финальная валидация телефона
  const raw = phoneInput.value.trim();
  const normalized = raw.replace(/[^\d+]/g, "");
  if (!/^\+7\d{10}$/.test(normalized)) {
    phoneInput.setCustomValidity("Следуйте формату: +7XXXXXXXXXX");
    phoneInput.reportValidity();
    return;
  } else {
    phoneInput.setCustomValidity("");
  }

  const form = new FormData(orderForm);
  const payload = {
    full_name: form.get("full_name")?.toString().trim(),
    phone: normalized,
    address: form.get("address")?.toString().trim(),
    comment: form.get("comment")?.toString().trim(),
    telegram: form.get("telegram")?.toString().trim(),
    items: cart.map(i => ({
      product_id: i.id,
      size: i.size,
      qty: i.qty
    }))
  };

  if (!payload.items.length) {
    alert("Корзина пуста");
    return;
  }

  // отправка в бота
  try {
    tg?.sendData?.(JSON.stringify(payload));
    checkoutModal.close();
    alert("Заказ отправлен. Спасибо!");
    // очистим корзину
    cart = [];
    updateCartBadge();
  } catch (e) {
    console.error(e);
    alert("Не удалось отправить заказ. Попробуйте ещё раз.");
  }
});

// старт
(async () => {
  try {
    await loadCategories();
  } catch (e) {
    console.error(e);
  }
  updateCartBadge();
})();
