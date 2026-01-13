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

  // ✅ FIX: Telegram iOS "кнопки не нажимаются" -> pointerup + click
  function bindTap(el, fn) {
    if (!el) return;

    // iOS/Telegram может стрелять и pointerup и click -> анти-дабл
    let last = 0;

    const handler = (e) => {
      const now = Date.now();
      if (now - last < 350) return;
      last = now;

      try { e.preventDefault?.(); } catch {}
      try { e.stopPropagation?.(); } catch {}
      fn(e);
    };

    el.addEventListener("pointerup", handler, { passive: false });
    el.addEventListener("click", handler, { passive: false });

    el.style.touchAction = "manipulation";
    el.style.webkitTapHighlightColor = "transparent";
  }

  // ✅ Нормализация ссылок (Drive/GitHub/jsDelivr/локальные)
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
    fetch(url, { credentials: "same-origin" }).then(r => {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });

  const loadConfig = async () => {
    try { return await getJSON(`${API}/api/config`); }
    catch { return { title: "LAYOUTPLACE Shop", logo_url: "", video_url: "" }; }
  };

  const loadCategories = () => getJSON(`${API}/api/categories`);

  const loadProducts = (c) => {
    const u = new URL(`${API}/api/products`, location.origin);
    if (c) u.searchParams.set("category", c);
    return getJSON(u.toString());
  };

  // ===== Sheet helpers (корзина/оформление) =====
  function openSheet(html) {
    if (sheet) sheet.innerHTML = html;
    sheet?.classList?.remove("hidden");
    backdrop?.classList?.remove("hidden");
    if (backdrop) backdrop.onclick = closeSheet;
  }

  function closeSheet() {
    sheet?.classList?.add("hidden");
    backdrop?.classList?.add("hidden");
    if (sheet) sheet.innerHTML = "";
  }

  // ===== Корзина =====
  function openCart(){
    if (!state.cart.length){
      openSheet(`<div class="row"><b>Корзина пуста</b></div>`);
      return;
    }

    const rows = state.cart.map((it,idx)=>`
      <div class="row">
        <div>
          <div><b>${esc(it.title)}</b> ${it.size ? `[${esc(it.size)}]` : ""}</div>
          <div>${money(it.price)} × ${it.qty}</div>
        </div>
        <div style="display:flex;gap:6px">
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

    // ⚠️ важно: обработчик на sheet, а не document
    sheet.onclick = (e)=>{
      const a = e.target?.dataset?.a;
      if(!a) return;
      const i = Number(e.target.dataset.i);
      if (Number.isNaN(i) || !state.cart[i]) return;

      if(a==="plus")  state.cart[i].qty++;
      if(a==="minus") state.cart[i].qty = Math.max(1, state.cart[i].qty-1);
      if(a==="rm")    state.cart.splice(i,1);

      updateCartBadge();
      closeSheet(); openCart();
    };

    const toCheckout = $("#toCheckout");
    if (toCheckout) toCheckout.onclick = () => { closeSheet(); openCheckout(); };
  }

  // ===== Оформление =====
  function openCheckout(){
    const total = state.cart.reduce((s,i)=>s+i.price*i.qty,0);

    openSheet(`
      <h3>Оформление</h3>
      <div class="row"><label>ФИО</label><input id="fio" placeholder="Иванов Иван"/></div>
      <div class="row"><label>Телефон (+7XXXXXXXXXX)</label><input id="phone" inputmode="tel" placeholder="+7XXXXXXXXXX"/></div>
      <div class="row"><label>Адрес/СДЭК</label><textarea id="addr" rows="2" placeholder="Город, пункт выдачи..."></textarea></div>
      <div class="row"><label>Комментарий</label><textarea id="comment" rows="2" placeholder="Например: размер L, цвет черный"></textarea></div>
      <div class="row"><label>Telegram (для связи)</label><input id="tguser" placeholder="@username"/></div>
      <div class="row"><b>Сумма:</b><b>${money(total)}</b></div>
      <button id="submitOrder" class="btn primary">Отправить</button>
    `);

    const submit = $("#submitOrder");
    if (!submit) return;

    submit.onclick = async () => {
      const fio   = $("#fio");
      const phone = $("#phone");
      const addr  = $("#addr");
      const comm  = $("#comment");
      const tguser= $("#tguser");

      const okPhone = /^\+7\d{10}$/.test((phone?.value || "").trim());
      [fio, phone].forEach(el=>el?.classList?.remove("bad"));

      if (!fio?.value?.trim()) { fio?.classList?.add("bad"); return; }
      if (!okPhone)            { phone?.classList?.add("bad"); return; }

      const payload = {
        full_name: fio.value.trim(),
        phone: phone.value.trim(),
        address: (addr?.value || "").trim(),
        comment: (comm?.value || "").trim(),
        telegram: (tguser?.value || "").trim(),
        items: state.cart.map(it=>({ product_id: it.id, size: it.size, qty: it.qty }))
      };

      try { tg?.sendData?.(JSON.stringify(payload)); } catch {}
      try {
        await fetch(`${API}/api/order`, {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify(payload)
        });
      } catch {}

      tg?.HapticFeedback?.notificationOccurred?.("success");
      closeSheet();
    };
  }

  // ✅ ВСПОМОГАТЕЛЬНОЕ: попытки автозапуска видео (Telegram iOS)
  function forceAutoplay(videoEl){
    if (!videoEl) return;

    // важные атрибуты для iOS
    try { videoEl.muted = true; } catch {}
    try { videoEl.autoplay = true; } catch {}
    try { videoEl.playsInline = true; } catch {}

    videoEl.setAttribute("muted", "");
    videoEl.setAttribute("autoplay", "");
    videoEl.setAttribute("playsinline", "");
    videoEl.setAttribute("webkit-playsinline", "");

    const tryPlay = () => {
      try {
        const p = videoEl.play();
        if (p && typeof p.catch === "function") p.catch(()=>{});
      } catch {}
    };

    // несколько попыток сразу/с задержками (часто нужно именно так в Telegram)
    requestAnimationFrame(tryPlay);
    setTimeout(tryPlay, 120);
    setTimeout(tryPlay, 600);
    setTimeout(tryPlay, 1200);

    // если iOS всё равно блокнул — первая микро-любой жест запустит
    document.addEventListener("touchstart", tryPlay, { once:true, passive:true });
    document.addEventListener("click", tryPlay, { once:true });

    // Telegram WebApp события — тоже удобный триггер
    try { tg?.onEvent?.("viewportChanged", tryPlay); } catch {}
    try { tg?.onEvent?.("themeChanged", tryPlay); } catch {}
  }

  // ===== render home (видео/лого) =====
  function renderHome(logoUrl, videoUrl) {
    if (!heroEl) return;

    const hasVideo = !!(videoUrl && String(videoUrl).trim());
    const hasLogo  = !!(logoUrl  && String(logoUrl).trim());

    if (!hasVideo && !hasLogo) {
      heroEl.classList.add("hidden");
      return;
    }

    heroEl.innerHTML = "";

    const box = document.createElement("div");
    box.className = "hero-img";

    if (hasVideo) {
      const src = normalizeVideoUrl(videoUrl);
      const poster = hasLogo ? normalizeImageUrl(logoUrl) : "";

      // ✅ КЛЮЧЕВОЕ: autoplay + muted + playsinline + preload="auto"
      box.innerHTML = `
        <video
          src="${src}"
          ${poster ? `poster="${poster}"` : ""}
          muted
          autoplay
          loop
          playsinline
          webkit-playsinline
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

    const tagline = document.createElement("div");
    tagline.className = "subtitle";
    tagline.style.textAlign = "center";
    tagline.style.marginTop = "8px";
    tagline.textContent = "https://t.me/akumastreetwear";
    heroEl.appendChild(tagline);

    heroEl.classList.remove("hidden");

    // ✅ Автозапуск (максимально возможный)
    const v = heroEl.querySelector("video");
    if (v) forceAutoplay(v);
  }

  function renderCategories(list){
    if (!categoriesEl) return;
    categoriesEl.innerHTML = "";
    list.forEach(c=>{
      const d = document.createElement("div");
      d.className = "cat";
      d.textContent = c.title || c;

      d.onclick = () => {
        state.category = d.textContent;
        heroEl?.classList?.add("hidden");
        drawProducts();
      };

      categoriesEl.appendChild(d);
    });
  }

  function buildAlbum(p){
    const cover = normalizeImageUrl(p.image_url || p.image || "");
    let list = [];
    if (p.images_urls && String(p.images_urls).trim()) {
      list = String(p.images_urls)
        .split("|")
        .map(s => normalizeImageUrl(s))
        .filter(Boolean);
    }
    const album = [];
    if (cover) album.push(cover);
    for (const u of list) if (u && !album.includes(u)) album.push(u);
    return album;
  }

  async function drawProducts(){
    if (!productsEl) return;
    productsEl.innerHTML = "";
    const items = await loadProducts(state.category || "");

    items.forEach(p=>{
      let sizes=[];
      if(p.sizes_text) sizes = String(p.sizes_text).split(",").map(s=>s.trim()).filter(Boolean);
      else if((p.category||"").toLowerCase().includes("обув")) sizes = SHOES_SIZES;
      else sizes = CLOTHES_SIZES;

      const desc = (p.description || "").trim();

      const album = buildAlbum(p);
      const hasGallery = album.length > 0;

      const galleryHtml = hasGallery ? `
        <div class="thumb">
          <div class="gallery" data-images-count="${album.length}">
            <div class="gallery-track" style="transform: translateX(0);">
              ${album.map((src)=>`
                <div class="gallery-slide">
                  <img
                    src="${src}"
                    alt="${esc(p.title)}"
                    loading="lazy"
                    referrerpolicy="no-referrer"
                    data-album="${esc(album.join("|"))}"
                  />
                </div>
              `).join("")}
            </div>

            ${album.length > 1 ? `
              <div class="gallery-dots">
                ${album.map((_,i)=>`<span class="gallery-dot ${i===0?'active':''}"></span>`).join("")}
              </div>
            ` : ``}
          </div>
        </div>
      ` : ``;

      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        ${galleryHtml}

        <div class="title">${esc(p.title)}</div>
        <div class="price">${money(p.price)}</div>
        ${desc ? `<div class="desc">${esc(desc)}</div>` : ``}

        <select id="size-${p.id}">
          ${sizes.map(s=>`<option value="${esc(s)}">${esc(s)}</option>`).join("")}
        </select>

        <button class="btn primary" id="btn-${p.id}">В корзину</button>
      `;
      productsEl.appendChild(card);

      const gallery = card.querySelector(".gallery");
      if (gallery) {
        const track = gallery.querySelector(".gallery-track");
        const dotsWrap = gallery.querySelector(".gallery-dots");
        const dots = dotsWrap ? Array.from(dotsWrap.querySelectorAll(".gallery-dot")) : [];
        const count = Number(gallery.dataset.imagesCount || 0);

        let gIdx = 0;
        const setIdx = (n, animate=true) => {
          if (!track || count <= 0) return;
          gIdx = Math.max(0, Math.min(n, count - 1));
          track.style.transition = animate ? "transform .22s ease" : "none";
          track.style.transform = `translateX(${-gIdx * 100}%)`;
          if (dots.length) dots.forEach((d,i)=>d.classList.toggle("active", i===gIdx));
        };

        let startX = 0, startY = 0, dx = 0, dragging = false;

        gallery.addEventListener("touchstart", (e) => {
          if (count <= 1) return;
          const t = e.touches[0];
          startX = t.clientX;
          startY = t.clientY;
          dx = 0;
          dragging = true;
          if (track) track.style.transition = "none";
        }, {passive:true});

        gallery.addEventListener("touchmove", (e) => {
          if (!dragging || count <= 1 || !track) return;
          const t = e.touches[0];
          const moveX = t.clientX - startX;
          const moveY = t.clientY - startY;
          if (Math.abs(moveY) > Math.abs(moveX)) return;

          dx = moveX;
          track.style.transform = `translateX(calc(${-gIdx * 100}% + ${dx}px))`;
        }, {passive:true});

        gallery.addEventListener("touchend", () => {
          if (!dragging || count <= 1) return;
          dragging = false;

          const threshold = 40;
          if (dx > threshold && gIdx > 0) setIdx(gIdx - 1);
          else if (dx < -threshold && gIdx < count - 1) setIdx(gIdx + 1);
          else setIdx(gIdx);
        });

        gallery.querySelectorAll("img").forEach(img=>{
          img.onerror = () => {
            const th = img.closest(".thumb");
            if (th) th.style.display = "none";
          };
        });
      }

      const btn = $("#btn-" + p.id);
      if (btn) {
        btn.onclick = () => {
          const sel = $("#size-" + p.id);
          const size = sel ? sel.value : "";

          const key = `${p.id}:${size || ""}`;
          const f = state.cart.find(it => it.key === key);
          if (f) f.qty += 1;
          else state.cart.push({ key, id:p.id, title:p.title, price:p.price, size, qty:1 });

          updateCartBadge();
          tg?.HapticFeedback?.impactOccurred?.("medium");
        };
      }
    });
  }

  // ====== FIX: Telegram iOS кнопки не нажимаются ======
  bindTap(writeBtn, () => {
    const url = MANAGER_USERNAME
      ? `https://t.me/${MANAGER_USERNAME}`
      : `tg://user?id=${MANAGER_ID}`;

    if (tg?.openLink && url.startsWith("https://")) tg.openLink(url);
    else if (tg?.openTelegramLink && url.startsWith("tg://")) tg.openTelegramLink(url);
    else window.location.href = url;
  });

  bindTap(cartBtn, () => openCart());
  bindTap(checkoutBtn, () => openCheckout());

  // ===== init =====
  (async()=>{
    try {
      const cfg = await loadConfig();
      if (cfg?.title) {
        if (titleEl) titleEl.textContent = cfg.title;
        document.title = cfg.title;
        if (subtitleEl) subtitleEl.textContent = "";
      }
      renderHome(cfg?.logo_url || "", cfg?.video_url || "");
    } catch {}

    try {
      const cats = await loadCategories();
      renderCategories(cats);
    } catch {}

    updateCartBadge();
  })();
}