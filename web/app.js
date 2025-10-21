// ====== базовые вещи ======
const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

const $ = (s, el=document) => el.querySelector(s);
const $$ = (s, el=document) => [...el.querySelectorAll(s)];

// API
async function jget(url){ const r = await fetch(url); if(!r.ok) throw new Error(url); return r.json(); }
async function jpost(url, data){ const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}); return r.json().catch(()=>({})); }

// ====== состояние ======
let state = {
  cat: null,
  sub: null,
  products: [],
  cart: [] // {id, title, price, size, qty}
};

function setCartBadge(){
  const n = state.cart.reduce((a,x)=>a+x.qty,0);
  $("#cartQty").textContent = n;
}

// ====== рендер категорий / подкатегорий ======
async function loadCategories(){
  const cats = await jget('/api/categories'); // [{name, image}]
  const wrap = $("#cats"); wrap.innerHTML = '';
  cats.forEach(c=>{
    const b = document.createElement('button');
    b.className = 'chip' + (state.cat===c.name?' active':'');
    b.textContent = c.name;
    b.onclick = ()=>{ state.cat=c.name; state.sub=null; renderCats(); loadSubcategories(); loadProducts(); };
    wrap.appendChild(b);
  });
  function renderCats(){
    $$('#cats .chip').forEach(el=>el.classList.toggle('active', el.textContent===state.cat));
  }
  if (!state.cat && cats[0]) { state.cat = cats[0].name; renderCats(); }
}

async function loadSubcategories(){
  const wrap = $("#subcats"); wrap.innerHTML = '';
  if(!state.cat) return;

  // бекенд должен отдавать список подкатегорий
  // если его нет — просто скрываем блок
  let subs = [];
  try { subs = await jget('/api/subcategories?category='+encodeURIComponent(state.cat)); }
  catch{ /* нет эндпойнта — ничего страшного */ }

  if (!subs || subs.length===0){ wrap.style.display='none'; return; }
  wrap.style.display='flex';

  const allBtn = document.createElement('button');
  allBtn.className = 'chip' + (!state.sub?' active':'');
  allBtn.textContent = 'Все';
  allBtn.onclick = ()=>{ state.sub=null; renderSubs(); loadProducts(); };
  wrap.appendChild(allBtn);

  subs.forEach(s=>{
    const b = document.createElement('button');
    b.className = 'chip' + (state.sub===s ? ' active':'');
    b.textContent = s;
    b.onclick = ()=>{ state.sub=s; renderSubs(); loadProducts(); };
    wrap.appendChild(b);
  });

  function renderSubs(){
    $$('#subcats .chip').forEach(el=>{
      el.classList.toggle('active',
        (!state.sub && el.textContent==='Все') || (state.sub && el.textContent===state.sub)
      );
    });
  }
}

// ====== рендер товаров ======
async function loadProducts(){
  const params = new URLSearchParams();
  if(state.cat) params.set('category', state.cat);
  if(state.sub) params.set('subcategory', state.sub);

  state.products = await jget('/api/products?'+params.toString());
  renderProducts();
}

function renderProducts(){
  const g = $("#grid"); g.innerHTML = '';
  state.products.forEach(p=>{
    const card = document.createElement('div');
    card.className = 'card';

    const img = document.createElement('img');
    img.src = p.image || (p.category === 'Одежда' ? './placeholder_clothes.jpg' : './placeholder_acc.jpg');
    img.alt = p.title; img.style.width='100%'; img.style.borderRadius='12px';
    card.appendChild(img);

    const h4 = document.createElement('h4');
    h4.textContent = p.title; card.appendChild(h4);

    const price = document.createElement('div');
    price.className = 'price'; price.textContent = `${p.price.toLocaleString('ru-RU')} ₽`;
    card.appendChild(price);

    // sizes
    const sizes = (p.sizes || '').split('|').map(s=>s.trim()).filter(Boolean);
    const sel = document.createElement('select');
    sel.className = 'select';
    if (sizes.length) sizes.forEach(s=>{
      const o = document.createElement('option'); o.value=s; o.textContent=s; sel.appendChild(o);
    }); else {
      const o = document.createElement('option'); o.value=''; o.textContent='—'; sel.appendChild(o);
    }
    card.appendChild(sel);

    const btn = document.createElement('button');
    btn.className='btn'; btn.textContent='В корзину';
    btn.onclick = ()=> addToCart(p, sel.value || '');
    card.appendChild(btn);

    g.appendChild(card);
  });
}

function addToCart(p, size){
  const same = state.cart.find(i=>i.id===p.id && i.size===size);
  if(same) same.qty += 1;
  else state.cart.push({id:p.id,title:p.title,price:p.price,size,qty:1});

  setCartBadge();
  toast('Добавлено в корзину');
}

function toast(t){
  if (tg) { tg.showPopup({title:'', message:t, buttons:[{type:'close'}]}); return; }
  console.log(t);
}

// ====== корзина / оформление ======
function openCart(){
  const list = $("#cartList"); list.innerHTML='';
  if(state.cart.length===0){
    list.innerHTML = '<div class="muted">Пока пусто</div>';
  } else {
    state.cart.forEach((it,idx)=>{
      const line = document.createElement('div');
      line.className='cart-line';
      line.innerHTML = `
        <div>
          <div><b>${it.title}</b></div>
          <div class="muted">${it.size || '—'} × ${it.qty}</div>
        </div>
        <div><b>${(it.qty*it.price).toLocaleString('ru-RU')} ₽</b></div>
      `;
      line.onclick = () => { // уменьшить по тапу
        it.qty -= 1;
        if(it.qty<=0) state.cart.splice(idx,1);
        setCartBadge(); openCart();
      };
      list.appendChild(line);
    });
  }
  const total = state.cart.reduce((a,x)=>a+x.qty*x.price,0);
  $("#cartTotal").textContent = `Итого: ${total.toLocaleString('ru-RU')} ₽`;
  $("#cartDialog").showModal();
}

function toCheckout(){
  $("#cartDialog").close();
  if(state.cart.length===0){ toast('Корзина пуста'); return; }
  $("#checkout").showModal();
}

function closeCheckout(){ $("#checkout").close(); }

async function submitOrder(e){
  e.preventDefault();
  if(state.cart.length===0){ toast('Корзина пуста'); return; }

  const fd = new FormData(e.target);
  const payload = {
    full_name: fd.get('full_name')?.trim(),
    phone: fd.get('phone')?.trim(),
    address: fd.get('address')?.trim(),
    comment: fd.get('comment')?.trim(),
    items: state.cart.map(x=>({
      product_id: x.id, size: x.size, qty: x.qty
    }))
  };

  // 1) отправляем в бот (обработчик F.web_app_data)
  try { tg?.sendData(JSON.stringify(payload)); } catch{}

  // 2) дублируем на бекенд как резерв
  try { await jpost('/api/order', payload); } catch{}

  // локальная очистка
  state.cart = []; setCartBadge();
  $("#checkout").close();

  toast('Заказ отправлен. Мы свяжемся с вами!');
}

// ====== listeners ======
$("#openCart").onclick = openCart;
$("#toCheckout").onclick = toCheckout;
$("#closeCheckout").onclick = closeCheckout;
$("#orderForm").addEventListener('submit', submitOrder);
$("#primaryAction").onclick = toCheckout;

// старт
(async function init(){
  try{
    await loadCategories();
    await loadSubcategories();
    await loadProducts();
  }catch(e){
    console.error(e);
    toast('Ошибка загрузки каталога');
  }
  setCartBadge();
})();
