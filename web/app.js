/* ===== LAYOUTPLACE SHOP WebApp logic (UI intact) ===== */

const tg = window.Telegram?.WebApp;
try { tg?.ready(); tg?.expand(); } catch (_) {}

/* ---- SELECTORS (под твои текущие id/классы) ----
   Если в твоём index.html другие id — просто поправь значения ниже.
*/
const SELECTORS = {
  // верхняя кнопка корзины и счётчик
  cartBtn:    '#cartBtn, [data-role="cart-btn"]',
  cartCount:  '#cartCount, [data-role="cart-count"]',

  // панель/слой корзины (внутри: список, сумма, кнопки)
  cartDrawer: '#cartDrawer, [data-role="cart-drawer"]',
  cartList:   '#cartItems, [data-role="cart-items"]',
  cartTotal:  '#cartTotal, [data-role="cart-total"]',
  cartClose:  '#cartClose, [data-role="cart-close"]',

  // кнопки внизу
  writeBtn:   '#writeBtn, [data-role="write-btn"]',
  checkoutBtn:'#checkoutBtn, [data-role="checkout-btn"]',

  // контейнеры каталога
  catsWrap:   '#catsWrap, [data-role="cats-wrap"]',
  goodsWrap:  '#goodsWrap, [data-role="goods-wrap"]',

  // шаблон карточки (если используешь темплейт)
  card:       '.product-card, [data-role="product-card"]',
  addBtn:     '.add-btn, [data-role="add-btn"]',
  sizeSelect: '.size-select, [data-role="size-select"]'
};

function $(sel){ return document.querySelector(sel); }
function $all(sel){ return Array.from(document.querySelectorAll(sel)); }

const DOM = Object.fromEntries(Object.entries(SELECTORS).map(([k,sel])=>[k, $(sel)]));

/* ---- Корзина (память в localStorage, чтобы сохранялось между перезагрузками) ---- */
const CART_KEY = 'lp_cart_v1';

function loadCart(){
  try { return JSON.parse(localStorage.getItem(CART_KEY)) || []; } catch { return []; }
}
function saveCart(cart){ localStorage.setItem(CART_KEY, JSON.stringify(cart)); }
let cart = loadCart();

function cartCount(){
  return cart.reduce((s,i)=>s + (Number(i.qty)||0), 0);
}
function cartSum(){
  return cart.reduce((s,i)=>s + (Number(i.price)||0)*(Number(i.qty)||0), 0);
}
function syncCartBadge(){
  if (DOM.cartCount) DOM.cartCount.textContent = String(cartCount());
}
function openCart(){
  if (!DOM.cartDrawer) return;
  DOM.cartDrawer.classList.add('is-open');
  renderCart();
}
function closeCart(){
  if (!DOM.cartDrawer) return;
  DOM.cartDrawer.classList.remove('is-open');
}
function renderCart(){
  if (!DOM.cartList) return;
  DOM.cartList.innerHTML = '';
  if (!cart.length){
    DOM.cartList.innerHTML = '<div class="muted">Корзина пуста</div>';
  } else {
    cart.forEach((it, idx)=>{
      const row = document.createElement('div');
      row.className = 'cart-row';
      row.innerHTML = `
        <div class="cart-title">${escapeHtml(it.title)} <span class="muted">[${escapeHtml(it.size||'—')}]</span></div>
        <div class="cart-qty">
          <button type="button" class="qty-dec" data-idx="${idx}">−</button>
          <span>${it.qty}</span>
          <button type="button" class="qty-inc" data-idx="${idx}">+</button>
        </div>
        <div class="cart-price">${(it.price * it.qty).toLocaleString('ru-RU')} ₽</div>
        <button type="button" class="cart-del" title="Удалить" data-idx="${idx}">×</button>
      `;
      DOM.cartList.appendChild(row);
    });
  }
  if (DOM.cartTotal) DOM.cartTotal.textContent = cartSum().toLocaleString('ru-RU') + ' ₽';

  // события на кнопки qty/del
  $all('.qty-dec').forEach(b=>b.addEventListener('click', onQtyDec));
  $all('.qty-inc').forEach(b=>b.addEventListener('click', onQtyInc));
  $all('.cart-del').forEach(b=>b.addEventListener('click', onDel));
}
function onQtyDec(e){
  const idx = Number(e.currentTarget.dataset.idx);
  if (cart[idx]){
    cart[idx].qty = Math.max(1, (Number(cart[idx].qty)||1) - 1);
    saveCart(cart); syncCartBadge(); renderCart();
  }
}
function onQtyInc(e){
  const idx = Number(e.currentTarget.dataset.idx);
  if (cart[idx]){
    cart[idx].qty = (Number(cart[idx].qty)||1) + 1;
    saveCart(cart); syncCartBadge(); renderCart();
  }
}
function onDel(e){
  const idx = Number(e.currentTarget.dataset.idx);
  cart.splice(idx,1);
  saveCart(cart); syncCartBadge(); renderCart();
}

/* ---- Каталог ---- */
async function fetchJSON(url){
  const r = await fetch(url, {credentials:'same-origin'});
  if (!r.ok) throw new Error('HTTP '+r.status);
  return r.json();
}

async function loadCategories(){
  try{
    const cats = await fetchJSON('/api/categories');
    if (DOM.catsWrap){
      DOM.catsWrap.innerHTML = '';
      cats.forEach(c=>{
        const btn = document.createElement('button');
        btn.className = 'cat-btn';
        btn.type = 'button';
        btn.textContent = c.title || c;
        btn.addEventListener('click', ()=>loadProducts(c.title || c));
        DOM.catsWrap.appendChild(btn);
      });
    }
    // авто-загрузка первой категории
    if (cats?.length) loadProducts(cats[0].title || cats[0]);
  }catch(err){
    console.error('categories:', err);
  }
}

async function loadProducts(category, subcategory=''){
  try{
    const qs = new URLSearchParams({category, subcategory});
    const goods = await fetchJSON('/api/products?'+qs.toString());
    if (!DOM.goodsWrap) return;
    DOM.goodsWrap.innerHTML = '';
    goods.forEach(p=>{
      const card = document.createElement('div');
      card.className = 'product-card';
      const sizes = (p.sizes || '').split(',').map(s=>s.trim()).filter(Boolean);
      const sizeSelect = sizes.length
        ? `<select class="size-select" ${SELECTORS.sizeSelect.includes('#')?'id="sizeSelect_'+p.id+'"' : ''}>
            ${sizes.map(s=>`<option value="${escapeAttr(s)}">${escapeHtml(s)}</option>`).join('')}
           </select>`
        : `<select class="size-select"><option>ONE SIZE</option></select>`;

      card.innerHTML = `
        <div class="product-title">${escapeHtml(p.title||'Товар')}</div>
        <div class="product-price">${Number(p.price||0).toLocaleString('ru-RU')} ₽</div>
        ${sizeSelect}
        <button type="button" class="add-btn" data-id="${p.id}">В корзину</button>
      `;
      DOM.goodsWrap.appendChild(card);
    });

    // навешиваем обработчики
    $all(SELECTORS.addBtn).forEach(btn=>{
      btn.addEventListener('click', ()=>{
        const id = Number(btn.dataset.id);
        // ищем контейнер карточки и селект размера
        const card = btn.closest(SELECTORS.card.split(',')[0]) || btn.parentElement;
        const sel  = card.querySelector(SELECTORS.sizeSelect);
        const size = sel ? sel.value : '';
        const p    = goods.find(g=>Number(g.id)===id);
        if (!p) return;

        // кладём в корзину (агрегируем по id+size)
        const key = `${id}__${size||''}`;
        const ex  = cart.find(x=>`${x.product_id}__${x.size||''}`===key);
        if (ex) ex.qty = (Number(ex.qty)||0) + 1;
        else {
          cart.push({
            product_id: id,
            title: p.title,
            price: Number(p.price||0),
            size: size || '',
            qty: 1
          });
        }
        saveCart(cart);
        syncCartBadge();

        // лёгкий отклик
        try { tg?.HapticFeedback?.impactOccurred('light'); } catch (_) {}
      });
    });

  }catch(err){
    console.error('products:', err);
  }
}

/* ---- Отправка формы «Оформить» ----
   Мы отправляем через tg.sendData({items, full_name, phone, address, comment, telegram})
   Бот принимает это в on_webapp_data.
*/
function makeOrderPayload(){
  return {
    items: cart.map(i=>({
      product_id: i.product_id,
      size: i.size || '',
      qty: Number(i.qty)||1,
    })),
    full_name: getVal('#orderFullName, [data-role="order-fullname"]'),
    phone:     getVal('#orderPhone,    [data-role="order-phone"]'),
    address:   getVal('#orderAddress,  [data-role="order-address"]'),
    comment:   getVal('#orderComment,  [data-role="order-comment"]'),
    telegram:  getVal('#orderTelegram, [data-role="order-telegram"]'),
  };
}
function getVal(sel){
  const el = $(sel);
  return el ? (el.value || '').trim() : '';
}

/* ---- Утилиты ---- */
function escapeHtml(s=''){
  return s.replace(/[&<>"']/g, m=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[m]));
}
function escapeAttr(s=''){
  return escapeHtml(String(s)).replace(/"/g,'&quot;');
}

/* ---- Навешиваем поведение ---- */
function bindUi(){
  // Корзина
  if (DOM.cartBtn)  DOM.cartBtn.addEventListener('click', openCart);
  if (DOM.cartClose)DOM.cartClose.addEventListener('click', closeCart);

  // «Написать» (открываем чат с менеджером по user_id)
  const MANAGER_ID = 6773668793;
  if (DOM.writeBtn){
    DOM.writeBtn.addEventListener('click', ()=>{
      const deeplink = `tg://user?id=${MANAGER_ID}`;
      try { tg?.openTelegramLink(deeplink); }
      catch { window.location.href = `https://t.me/${MANAGER_ID}`; }
    });
  }

  // «Оформить»
  if (DOM.checkoutBtn){
    DOM.checkoutBtn.addEventListener('click', ()=>{
      if (!cart.length){
        alert('Корзина пуста');
        return;
      }
      const payload = makeOrderPayload();
      try {
        tg?.sendData(JSON.stringify(payload));
        // можно сразу очистить корзину локально
        cart = []; saveCart(cart); syncCartBadge(); renderCart();
      } catch (e){
        console.error('sendData failed', e);
        // запасной REST-вариант (если sendData не сработал)
        fetch('/api/order', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        }).then(r=>r.json()).then(()=> {
          cart = []; saveCart(cart); syncCartBadge(); renderCart();
          alert('Заказ отправлен');
        }).catch(err=>{
          console.error(err);
          alert('Не удалось отправить заказ. Проверьте интернет и попробуйте снова.');
        });
      }
    });
  }

  // закрытие корзины по клику вне содержимого (если сделан оверлей)
  if (DOM.cartDrawer){
    DOM.cartDrawer.addEventListener('click', (e)=>{
      if (e.target === DOM.cartDrawer) closeCart();
    });
  }

  syncCartBadge();
}

/* ---- Старт ---- */
document.addEventListener('DOMContentLoaded', async ()=>{
  bindUi();
  await loadCategories();
});