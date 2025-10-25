// ===== Telegram WebApp boot =====
const tg = window.Telegram?.WebApp;
tg?.ready();

// ========= Константы проекта =========
const MANAGER_USERNAME = "layoutplacebuy";   // @ без @
const MANAGER_ID       = 6773668793;         // резерв по id

// Относительный API (бот и статика на одном домене)
const API = "";

// Размеры по умолчанию
const CLOTHES_SIZES = ["XS","S","M","L","XL","XXL"];
const SHOES_SIZES   = ["36","37","38","39","40","41","42","43","44","45"];

// ========= Состояние =========
let state = {
  category: null,   // null → главная с медиа (видео/логотип)
  cart: []          // [{key,id,title,price,size,qty}]
};

// ========= DOM =========
const $ = (sel) => document.querySelector(sel);
const heroEl       = $("#hero");
const categoriesEl = $("#categories");
const productsEl   = $("#products");
const cartBtn      = $("#cartBtn");
const cartCount    = $("#cartCount");
const writeBtn     = $("#writeBtn");
const checkoutBtn  = $("#checkoutBtn");
const sheet        = $("#sheet");
const backdrop     = $("#backdrop");
const titleEl      = $("#shopTitle");
const subtitleEl   = $("#subtitle");

// ========= Утилиты =========
function esc(s){
  return String(s ?? "")
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;")
    .replace(/'/g,"&#39;");
}
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

// --- нормализация ссылок ---
function normalizeImageUrl(urlRaw) {
  if (!urlRaw) return "";
  let u = String(urlRaw).trim();
  if (u.startsWith("/images/")) return u; // локальные
  const qIdx = u.indexOf("?");
  if (qIdx > -1) u = u.slice(0, qIdx);
  const m = u.match(/drive\.google\.com\/file\/d\/([^/]+)/i);
  if (m && m[1]) return `https://drive.google.com/uc?export=view&id=${m[1]}`;
  u = u.replace(
    /raw\.githubusercontent\.com\/([^/]+)\/([^/]+)\/refs\/heads\/main\//i,
    "raw.githubusercontent.com/$1/$2/main/"
  );
  return u;
}
const normalizeVideoUrl = normalizeImageUrl; // те же правила, что и для картинок

// ========= API =========
async function getJSON(url){
  const r = await fetch(url, { credentials: "same-origin" });
  if(!r.ok) throw new Error("HTTP "+r.status);
  return r.json();
}
async function loadConfig(){
  try {
    return await getJSON(`${API}/api/config`);
  } catch {
    return { title: "LAYOUTPLACE Shop", logo_url: "", video_url: "" };
  }
}
async function loadCategories(){
  const data = await getJSON(`${API}/api/categories`);
  return (data||[]).map(c => (typeof c==="string") ? {title:c} : {title:c.title, image_url:c.image_url||""});
}
async function loadProducts(category, sub=""){
  const u = new URL(`${API}/api/products`, window.location.origin);
  if (category)    u.searchParams.set("category", category);
  if (sub != null) u.searchParams.set("subcategory", sub);
  return getJSON(u.toString());
}

// ========= Рендер =========
function renderHome(logoUrl, videoUrl){
  productsEl.innerHTML = "";

  const hasVideo = !!(videoUrl && String(videoUrl).trim());
  const hasImage = !!(logoUrl  && String(logoUrl).trim());

  if (!hasVideo && !hasImage) {
    heroEl.classList.add("hidden");
    return;
  }

  heroEl.innerHTML = ""; // очистка

  const box = document.createElement("div");
  box.className = "hero-img"; // используем готовые стили квадратного контейнера

  if (hasVideo) {
    const src = normalizeVideoUrl(videoUrl);
    box.innerHTML = `
      <video
        src="${src}"
        autoplay
        muted
        loop
        playsinline
        preload="auto"
        style="width:100%;height:100%;object-fit:cover;border-radius:12px;"
        controlslist="nodownload noplaybackrate noremoteplayback nofullscreen">
      </video>
    `;
  } else {
    const src = normalizeImageUrl(logoUrl);
    box.innerHTML = `
      <img src="${src}" alt="brand logo" loading="lazy" referrerpolicy="no-referrer" />
    `;
  }

  heroEl.appendChild(box);

  // Подпись (можно убрать, если не нужна)
  const tagline = document.createElement("div");
  tagline.className = "subtitle";
  tagline.style.textAlign = "center";
  tagline.style.marginTop = "8px";
  tagline.textContent = "https://t.me/akumastreetwear"; 
  heroEl.appendChild(tagline);

  heroEl.classList.remove("hidden");

  // iOS WebView иногда блокирует автоплей — пробуем вручную
  const v = heroEl.querySelector("video");
  if (v) {
    v.play().catch(() => {
      v.setAttribute("controls","controls");
    });
  }
}

function renderCategories(list){
  categoriesEl.innerHTML = "";
  const frag = document.createDocumentFragment();
  list.forEach(cat=>{
    const div = document.createElement("div");
    div.className = "cat";
    div.textContent = cat.title;
    div.onclick = () => {
      state.category = cat.title;
      heroEl.classList.add("hidden"); // ушли с главной — прячем медиа
      drawProducts();
    };
    frag.appendChild(div);
  });
  categoriesEl.appendChild(frag);
}

async function drawProducts(){
  productsEl.innerHTML = "";
  const items = await loadProducts(state.category || "");
  items.forEach(p=>{
    // размеры
    let sizes = [];
    if (p.sizes_text && String(p.sizes_text).trim()) {
      sizes = String(p.sizes_text).split(",").map(s=>s.trim()).filter(Boolean);
    } else if ((p.category||"").toLowerCase().includes("обув")) {
      sizes = SHOES_SIZES;
    } else {
      sizes = CLOTHES_SIZES;
    }

    const imgUrl = normalizeImageUrl(p.image_url || p.image || "");
    const desc   = (p.description || "").trim();

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      ${imgUrl ? `
        <div class="thumb">
          <img src="${imgUrl}" alt="${esc(p.title)}" loading="lazy" referrerpolicy="no-referrer" />
        </div>` : ``}
      <div class="title">${esc(p.title)}</div>
      <div class="price">${money(p.price)}</div>
      ${desc ? `<div class="desc">${esc(desc)}</div>` : ``}
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

    const img = card.querySelector("img");
    if (img) {
      img.onerror = () => {
        const th = img.closest(".thumb");
        if (th) th.style.display = "none";
      };
    }

    $("#btn-"+p.id).onclick = () => {
      const sz = $("#size-"+p.id).value;
      addToCart(p, sz);
      tg?.HapticFeedback?.impactOccurred?.("medium");
    };
  });
}

// ========= Корзина и оформление =========
function openCart(){
  if (state.cart.length === 0){
    openSheet(`<div class="row"><b>Корзина пуста</b></div>`);
    return;
  }
  const rows = state.cart.map((it,idx)=>`
    <div class="row">
      <div>
        <div><b>${esc(it.title)}</b> ${it.size?`[${esc(it.size)}]`:""}</div>
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
    <div class="row"><label>ФИО</label><input id="fio" placeholder="Иванов Иван"/></div>
    <div class="row"><label>Телефон (+7XXXXXXXXXX)</label><input id="phone" inputmode="tel" placeholder="+7XXXXXXXXXX"/></div>
    <div class="row"><label>Адрес/СДЭК</label><textarea id="addr" rows="2" placeholder="Город, пункт выдачи..."></textarea></div>
    <div class="row"><label>Комментарий к заказу (размер)</label><textarea id="comment" rows="2" placeholder="Например: размер L, цвет черный"></textarea></div>
    <div class="row"><label>Telegram (для связи с Вами)</label><input id="tguser" placeholder="@username"/></div>
    <div class="row"><b>Сумма:</b><b>${money(total)}</b></div>
    <button id="submitOrder" class="btn primary">Отправить</button>
  `);

  $("#submitOrder").onclick = async () => {
    const fio   = $("#fio");
    const phone = $("#phone");
    const addr  = $("#addr");
    const comm  = $("#comment");
    const tguser= $("#tguser");

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
      items: state.cart.map(it=>({ product_id: it.id, size: it.size, qty: it.qty }))
    };

    try { tg?.sendData?.(JSON.stringify(payload)); } catch(e){}
    try {
      await fetch(`${API}/api/order`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(payload)
      });
    } catch(e){}

    tg?.HapticFeedback?.notificationOccurred?.("success");
    closeSheet();
  };
}

// ========= Нижние кнопки =========
writeBtn.onclick = () => {
  if (MANAGER_USERNAME) {
    const url = `https://t.me/${MANAGER_USERNAME}`;
    if (tg?.openLink) tg.openLink(url); else window.open(url, "_blank");
  } else {
    const url = `tg://user?id=${MANAGER_ID}`;
    if (tg?.openTelegramLink) tg.openTelegramLink(url); else window.location.href = url;
  }
};
checkoutBtn.onclick = () => openCheckout();
cartBtn.onclick = () => openCart();

// ========= Инициализация =========
(async function init(){
  try {
    const cfg = await loadConfig();
    if (cfg?.title) {
      if (titleEl)   titleEl.textContent = cfg.title;
      document.title = cfg.title;
      if (subtitleEl && !subtitleEl.textContent.trim()) {
        subtitleEl.textContent = "";
      }
    }
    // Показать видео (если есть) или логотип
    renderHome(cfg?.logo_url || "", cfg?.video_url || "");
  } catch (e) {
    heroEl?.classList?.add("hidden");
  }

  try {
    const cats = await loadCategories();
    renderCategories(cats);
  } catch {}

  updateCartBadge();
})();

// ========= Просмотр фото (карточки товаров) =========
const imgViewer = document.querySelector("#imgViewer");
const imgViewerImg = imgViewer?.querySelector("img");

if (productsEl && imgViewer && imgViewerImg) {
  productsEl.addEventListener("click", (e) => {
    const target = e.target;
    const img = target && target.closest ? target.closest(".thumb img") : null;
    if (!img) return;
    const src = img.getAttribute("src");
    if (!src) return;
    imgViewerImg.src = src;
    imgViewer.classList.add("show");
  });

  imgViewer.addEventListener("click", () => {
    imgViewer.classList.remove("show");
    imgViewerImg.src = "";
  });
}