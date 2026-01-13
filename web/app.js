document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

function initApp() {
  // ===== Telegram WebApp boot =====
  const tg = window.Telegram?.WebApp;
  tg?.ready?.();
  tg?.expand?.();

  const MANAGER_USERNAME = "layoutplacebuy";
  const MANAGER_ID = 6773668793;
  const API = "";

  const CLOTHES_SIZES = ["XS","S","M","L","XL","XXL"];
  const SHOES_SIZES   = ["36","37","38","39","40","41","42","43","44","45"];

  let state = { category: null, cart: [] };

  const $ = (s) => document.querySelector(s);
  const heroEl = $("#hero");
  const categoriesEl = $("#categories");
  const productsEl = $("#products");
  const cartBtn = $("#cartBtn");
  const cartCount = $("#cartCount");
  const writeBtn = $("#writeBtn");
  const checkoutBtn = $("#checkoutBtn");
  const sheet = $("#sheet");
  const backdrop = $("#backdrop");
  const titleEl = $("#shopTitle");
  const subtitleEl = $("#subtitle");

  // ===== utils =====
  const esc = s => String(s ?? "").replace(/[&<>"']/g,m=>({
    "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
  }[m]));

  const money = n => (n||0).toLocaleString("ru-RU")+" ₽";

  function updateCartBadge() {
    if (!cartCount) return;
    cartCount.textContent = state.cart.reduce((s,i)=>s+i.qty,0);
  }

  // ===== нормализация URL =====
  function normalizeImageUrl(u){
    if(!u) return "";
    u = String(u).trim();
    if (u.startsWith("/images/")) return u;

    const m = u.match(/drive\.google\.com\/file\/d\/([^/]+)/i);
    if(m) return `https://drive.google.com/uc?export=view&id=${m[1]}`;

    u = u.replace(
      /raw\.githubusercontent\.com\/([^/]+)\/([^/]+)\/refs\/heads\/main\//i,
      "raw.githubusercontent.com/$1/$2/main/"
    );

    const q = u.indexOf("?");
    if(q > -1) u = u.slice(0,q);
    return u;
  }

  function normalizeVideoUrl(u){
    if(!u) return "";
    u = String(u).trim();
    if (u.startsWith("/images/")) return u;

    const m = u.match(/drive\.google\.com\/file\/d\/([^/]+)/i);
    if(m) return `https://drive.google.com/uc?export=view&id=${m[1]}`;

    u = u.replace(
      /raw\.githubusercontent\.com\/([^/]+)\/([^/]+)\/refs\/heads\/main\//i,
      "raw.githubusercontent.com/$1/$2/main/"
    );
    return u;
  }

  // ===== API =====
  const getJSON = (url) =>
    fetch(url).then(r => {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });

  const loadConfig = async () => {
    try { return await getJSON(`${API}/api/config`); }
    catch { return { title: "AKUMA SHOP", logo_url: "", video_url: "" }; }
  };

  const loadCategories = () => getJSON(`${API}/api/categories`);
  const loadProducts = (c) => {
    const u = new URL(`${API}/api/products`, location.origin);
    if (c) u.searchParams.set("category", c);
    return getJSON(u.toString());
  };

  // ===== HERO (ВИДЕО — FIXED) =====
  function renderHome(logoUrl, videoUrl) {
    if (!heroEl) return;

    const hasVideo = !!videoUrl;
    const hasLogo  = !!logoUrl;

    heroEl.innerHTML = "";

    const box = document.createElement("div");
    box.className = "hero-img";

    if (hasVideo) {
      const src = normalizeVideoUrl(videoUrl);
      const poster = hasLogo ? normalizeImageUrl(logoUrl) : "";

      box.innerHTML = `
        <video
          src="${src}"
          ${poster ? `poster="${poster}"` : ""}
          muted
          autoplay
          loop
          playsinline
          preload="auto"
          style="width:100%;height:100%;object-fit:cover;border-radius:12px;"
        ></video>
      `;
    } else if (hasLogo) {
      box.innerHTML = `<img src="${normalizeImageUrl(logoUrl)}" />`;
    }

    heroEl.appendChild(box);
    heroEl.classList.remove("hidden");

    // 🔥 КЛЮЧЕВОЙ ФИКС TELEGRAM iOS
    const v = heroEl.querySelector("video");
    if (v) {
      v.muted = true;
      v.playsInline = true;

      const tryPlay = () => {
        const p = v.play();
        if (p && p.catch) p.catch(()=>{});
      };

      setTimeout(tryPlay, 0);
      document.addEventListener("click", tryPlay, { once:true });
      document.addEventListener("touchstart", tryPlay, { once:true });
    }
  }

  // ===== CATEGORIES =====
  function renderCategories(list){
    categoriesEl.innerHTML = "";
    list.forEach(c=>{
      const d = document.createElement("div");
      d.className = "cat";
      d.textContent = c.title || c;
      d.onclick = () => {
        state.category = d.textContent;
        heroEl.classList.add("hidden");
        drawProducts();
      };
      categoriesEl.appendChild(d);
    });
  }

  // ===== PRODUCTS =====
  async function drawProducts(){
    productsEl.innerHTML = "";
    const items = await loadProducts(state.category || "");

    items.forEach(p=>{
      const album = [
        normalizeImageUrl(p.image_url),
        ...(p.images_urls ? p.images_urls.split("|").map(normalizeImageUrl) : [])
      ].filter(Boolean);

      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        ${album[0] ? `<img src="${album[0]}" loading="lazy">` : ``}
        <div class="title">${esc(p.title)}</div>
        <div class="price">${money(p.price)}</div>
        <button class="btn primary">В корзину</button>
      `;
      productsEl.appendChild(card);
    });
  }

  // ===== INIT =====
  (async()=>{
    const cfg = await loadConfig();
    if (titleEl) titleEl.textContent = cfg.title;
    document.title = cfg.title;
    renderHome(cfg.logo_url, cfg.video_url);

    const cats = await loadCategories();
    renderCategories(cats);
    updateCartBadge();
  })();
}
