// Telegram SDK
const tg = window.Telegram?.WebApp; tg?.ready(); tg?.expand();

const $  = (s, el=document) => el.querySelector(s);
const $$ = (s, el=document) => [...el.querySelectorAll(s)];

async function jget(u){ const r = await fetch(u); if(!r.ok) throw new Error(u); return r.json(); }
async function jpost(u,d){ const r = await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)}); return r.json().catch(()=>({})); }

function toast(msg){
  if (tg?.showPopup) tg.showPopup({title:'', message:msg, buttons:[{type:'close'}]});
  else alert(msg);
}
function openManagerChat(){
  const id = 6773668793; // менеджер
  try { tg?.openTelegramLink(`tg://user?id=${id}`); }
  catch { toast('Напишите менеджеру в Telegram: откройте чат с магазином и нажмите «Написать».'); }
}

// ---------- state ----------
let state = { cat: null, sub: null, products: [], cart: [] }; // cart: {id,title,price,size,qty}

function setCartBadge(){
  const n = state.cart.reduce((a,x)=>a+x.qty,0);
  $("#cartQty").textContent = n;
  updateBottomBar();
}
function updateBottomBar(){
  const primary = $("#primaryAction");
  if (primary) primary.disabled = (state.cart.length === 0);
}

// ---------- catalog ----------
async function loadCategories(){
  let list = [];
  try { list = await jget('/api/categories'); } catch { list = []; }

  const cats = (list||[]).map(x => ({
    title: (x && typeof x === 'object') ? (x.title || x.name || x.category || '') : String(x||''),
    image_url: (x && typeof x === 'object') ? (x.image_url || x.image || '') : ''
  })).filter(c => c.title);

  const wrap = $("#cats"); wrap.innerHTML = '';
  if (!cats.length){ wrap.style.display='none'; return; }
  wrap.style.display='flex';

  cats.forEach(c=>{
    const b = document.createElement('button');
    b.className = 'chip' + (state.cat===c.title?' active':'');
    b.textContent = c.title;
    b.onclick = ()=>{ state.cat=c.title; state.sub=null; renderActiveCats(); loadSubcategories(); loadProducts(); };
    wrap.appendChild(b);
  });

  function renderActiveCats(){
    $$('#cats .chip').forEach(el=>el.classList.toggle('active', el.textContent===state.cat));
  }
  if (!state.cat){ state.cat = cats[0].title; renderActiveCats(); }
}

async function loadSubcategories(){
  const wrap = $("#subcats"); wrap.innerHTML = '';
  if (!state.cat){ wrap.style.display='none'; return; }
  let subs = [];
  try { subs = await jget('/api/subcategories?category='+encodeURIComponent(state.cat)); }
  catch { subs = []; }

  const titles = (subs||[]).map(s => (typeof s === 'string' ? s : (s?.title || s?.name || ''))).filter(Boolean);
  if (!titles.length){ wrap.style.display='none'; return; }
  wrap.style.display='flex';

  const addChip = (txt, active) => {
    const b = document.createElement('button');
    b.className = 'chip' + (active ? ' active':'');
    b.textContent = txt;
    b.onclick = ()=>{ state.sub = (txt==='Все') ? null : txt; renderSubs(); loadProducts(); };
    wrap.appendChild(b);
  };

  addChip('Все', state.sub===null);
  titles.forEach(s => addChip(s, state.sub===s));

  function renderSubs(){
    $$('#subcats .chip').forEach(el=>{
      const txt = el.textContent;
      el.classList.toggle('active', (state.sub===null && txt==='Все') || (state.sub===txt));
    });
  }
}

async function loadProducts(){
  const params = new URLSearchParams();
  if (state.cat) params.set('category', state.cat);
  if (state.sub !== null && state.sub !== undefined) params.set('subcategory', state.sub || '');
  let list = [];
  try { list = await jget('/api/products?'+params.toString()); } catch { list = []; }

  const prods = (list||[]).map(p => ({
    id: Number(p.id),
    title: p.title || '',
    price: Number(p.price || 0),
    image_url: p.image_url || p.image || '',
    sizes: Array.isArray(p.sizes) ? p.sizes
      : (typeof p.sizes === 'string' ? p.sizes.split(/[,\|]/).map(s=>s.trim()).filter(Boolean) : [])
  })).filter(p => p.id && p.title);

  state.products = prods;
  renderProducts();
}

function renderProducts(){
  const g = $("#grid"); g.innerHTML = '';
  state.products.forEach(p=>{
    const card = document.createElement('div'); card.className = 'card';

    const img = document.createElement('img');
    img.src = p.image_url || (state.cat && state.cat.toLowerCase().includes('аксесс') ? './placeholder_acc.jpg' : './placeholder_clothes.jpg');
    img.alt = p.title; img.style.width='100%'; img.style.borderRadius='12px';
    card.appendChild(img);

    const h4 = document.createElement('h4'); h4.textContent = p.title; card.appendChild(h4);

    const price = document.createElement('div'); price.className = 'price'; price.textContent = `${p.price.toLocaleString('ru-RU')} ₽`;
    card.appendChild(price);

    const sel = document.createElement('select'); sel.className = 'select';
    const sizes = Array.isArray(p.sizes) ? p.sizes : [];
    if (sizes.length){
      sizes.forEach(s => { const o=document.createElement('option'); o.value=s; o.textContent=s; sel.appendChild(o); });
    } else {
      const o=document.createElement('option'); o.value=''; o.textContent='—'; sel.appendChild(o);
    }
    card.appendChild(sel);

    const btn = document.createElement('button'); btn.className='btn'; btn.textContent='В корзину';
    btn.onclick = ()=> addToCart(p, sel.value || '');
    card.appendChild(btn);

    g.appendChild(card);
  });
}

function addToCart(p, size){
  const same = state.cart.find(i=>i.id===p.id && i.size===size);
  if (same) same.qty += 1;
  else state.cart.push({id:p.id,title:p.title,price:p.price,size,qty:1});
  setCartBadge(); toast('Добавлено в корзину');
}

// ---------- cart & checkout ----------
function openCart(){
  const list = $("#cartList"); list.innerHTML='';
  if(state.cart.length===0){
    list.innerHTML = '<div class="muted">Пока пусто</div>';
  } else {
    state.cart.forEach((it,idx)=>{
      const line = document.createElement('div'); line.className='cart-line';
      line.innerHTML = `
        <div>
          <div><b>${it.title}</b></div>
          <div class="muted">${it.size || '—'} × ${it.qty}</div>
        </div>
        <div><b>${(it.qty*it.price).toLocaleString('ru-RU')} ₽</b></div>`;
      line.onclick = () => {
        it.qty -= 1; if (it.qty<=0) state.cart.splice(idx,1);
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
  if (state.cart.length===0){ toast('Корзина пуста'); return; }
  $("#cartDialog").close();
  $("#checkout").showModal();
}
function closeCheckout(){ $("#checkout").close(); }

async function submitOrder(e){
  e.preventDefault();
  if (state.cart.length===0){ toast('Корзина пуста'); return; }

  const fd = new FormData(e.target);
  const payload = {
    full_name: fd.get('full_name')?.trim(),
    phone:     fd.get('phone')?.trim(),
    address:   fd.get('address')?.trim(),
    comment:   fd.get('comment')?.trim(),
    telegram:  fd.get('telegram')?.trim(),
    items: state.cart.map(x=>({ product_id:x.id, size:x.size, qty:x.qty }))
  };

  try { tg?.sendData(JSON.stringify(payload)); } catch {}
  try { await jpost('/api/order', payload); } catch {}

  state.cart = []; setCartBadge();
  $("#checkout").close();
  toast('Заказ отправлен. Мы свяжемся с вами!');
}

// listeners
$("#openCart").onclick = openCart;
$("#toCheckout").onclick = toCheckout;
$("#closeCheckout").onclick = closeCheckout;
$("#orderForm").addEventListener('submit', submitOrder);
$("#contactAction").onclick = openManagerChat;
$("#primaryAction").onclick = toCheckout;

// init
(async function init(){
  try{
    await loadCategories();
    await loadSubcategories();
    await loadProducts();
  }catch(e){
    console.error(e);
    toast('Ошибка загрузки каталога');
  }
  setCartBadge(); updateBottomBar();
})();
