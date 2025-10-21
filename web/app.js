
const tg = window.Telegram?.WebApp;
if (tg) tg.expand();

let state = {
  categories: [],
  products: [],
  cat: null,
  cart: [] // {id,title,price,size,qty}
};

const qs = (sel)=>document.querySelector(sel);
const qsa = (sel)=>Array.from(document.querySelectorAll(sel));

function rub(n){ return new Intl.NumberFormat('ru-RU').format(n) + ' ₽'; }

async function api(path){
  const r = await fetch(path, {credentials:'same-origin'});
  return r.json();
}

async function loadCats(){
  state.categories = await api('/api/categories');
  const wrap = qs('#catGrid'); wrap.innerHTML='';
  const tpl = qs('#catTpl').content;
  const imgMap = {};
  state.categories.forEach(c=>{
    const node = tpl.cloneNode(true);
    const btn = node.querySelector('button');
    btn.querySelector('span.title').textContent = c;
    btn.querySelector('img').src = '/web/placeholder_'+(c==='Одежда'?'clothes':'acc')+'.jpg';
    btn.addEventListener('click', ()=>openCat(c));
    wrap.appendChild(node);
  });
}

async function openCat(c){
  state.cat = c;
  qs('#listTitle').textContent = c;
  qs('#cats').classList.add('hidden');
  qs('#list').classList.remove('hidden');
  const data = await api('/api/products?category='+encodeURIComponent(c));
  state.products = data;
  renderList();
}
function backToCats(){
  qs('#list').classList.add('hidden');
  qs('#cartPanel').classList.add('hidden');
  qs('#cats').classList.remove('hidden');
}

function renderList(){
  const wrap = qs('#prodList'); wrap.innerHTML='';
  const tpl = qs('#prodTpl').content;
  state.products.forEach(p=>{
    const node = tpl.cloneNode(true);
    node.querySelector('.cover').src = p.photo_url || '';
    node.querySelector('.title').textContent = p.title;
    node.querySelector('.desc').textContent = p.description || '';
    node.querySelector('.price').innerHTML = rub(p.price) + (p.discount?` <span class=\"badge\">-${p.discount}%</span>`:'');
    const sizes = (p.sizes||'ONESIZE').split(',').map(s=>s.trim()).filter(Boolean);
    const select = node.querySelector('.sizeSel');
    sizes.forEach(s=>{ const o=document.createElement('option'); o.value=s; o.textContent=s; select.appendChild(o); });
    node.querySelector('.sizes').textContent = 'Размеры: ' + sizes.join(', ');
    const favBtn = document.createElement('button'); favBtn.className='fav'; favBtn.textContent='❤';
    const actions = node.querySelector('.actions'); actions.appendChild(favBtn);
    const favSet = new Set(JSON.parse(localStorage.getItem('fav')||'[]'));
    if (favSet.has(p.id)) favBtn.classList.add('active');
    favBtn.addEventListener('click', ()=>{ if (favSet.has(p.id)){ favSet.delete(p.id); favBtn.classList.remove('active'); } else { favSet.add(p.id); favBtn.classList.add('active'); } localStorage.setItem('fav', JSON.stringify(Array.from(favSet))); });
    node.querySelector('.add').addEventListener('click', ()=>{
      addToCart({id:p.id,title:p.title,price:p.price,size:select.value});
    });
    wrap.appendChild(node);
  });
}

function addToCart(item){
  const key = item.id+'|'+item.size;
  const ex = state.cart.find(i=>i.id+'|'+i.size===key);
  if (ex) ex.qty += 1; else state.cart.push({...item, qty:1});
  openCart();
}

function openCart(){
  qs('#cats').classList.add('hidden');
  qs('#list').classList.add('hidden');
  qs('#cartPanel').classList.remove('hidden');
  renderCart();
}

function renderCart(){
  const wrap = qs('#cartList'); wrap.innerHTML='';
  const tpl = qs('#cartItemTpl').content;
  let total = 0;
  state.cart.forEach((it, idx)=>{
    const node = tpl.cloneNode(true);
    node.querySelector('.t').textContent = it.title;
    node.querySelector('.s').textContent = '['+it.size+']';
    node.querySelector('.q').textContent = it.qty;
    node.querySelector('.p').textContent = rub(it.price*it.qty);
    node.querySelector('.inc').addEventListener('click', ()=>{ it.qty++; renderCart(); });
    node.querySelector('.dec').addEventListener('click', ()=>{ it.qty--; if(it.qty<=0){ state.cart.splice(idx,1);} renderCart(); });
    wrap.appendChild(node);
    total += it.price*it.qty;
  });
  qs('#total').textContent = rub(total);
}

function submitOrder(){
  if (state.cart.length===0){ alert('Корзина пуста'); return; }
  const payload = {
    full_name: qs('#fullName').value.trim(),
    address: qs('#address').value.trim(),
    phone: qs('#phone').value.trim(),
    comment: qs('#comment').value.trim(),
    items: state.cart.map(i=>({product_id:i.id, size:i.size, qty:i.qty}))
  };
  if (!payload.full_name || !payload.address || !payload.phone){
    alert('Заполните ФИО, адрес и телефон'); return;
  }
  if (tg && tg.sendData){
    tg.sendData(JSON.stringify(payload));
  } else {
    fetch('/api/order', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)})
      .then(r=>r.json()).then(resp=>{ alert('Заказ оформлен #' + resp.order_id); });
  }
}

qs('#btnBack').addEventListener('click', backToCats);
qs('#btnBackFromCart').addEventListener('click', ()=>{
  qs('#cartPanel').classList.add('hidden');
  qs('#list').classList.remove('hidden');
});
qs('#btnCart').addEventListener('click', openCart);
qs('#btnCheckout').addEventListener('click', submitOrder);


// --- Bottom navigation & favorites ---
const tabs = {
  discounts: document.getElementById('tabDiscounts'),
  fav: document.getElementById('tabFav'),
  home: document.getElementById('tabHome'),
  cart: document.getElementById('tabCart'),
  write: document.getElementById('tabWrite'),
};
Object.values(tabs).forEach(b=>b&&b.addEventListener('click', ()=>onTab(b)));

function setActiveTab(btn){
  qsa('.bottom-nav button').forEach(x=>x.classList.remove('active'));
  btn.classList.add('active');
}
function onTab(btn){
  switch(btn){
    case tabs.discounts:
      setActiveTab(btn);
      qs('#cats').classList.add('hidden'); qs('#cartPanel').classList.add('hidden');
      qs('#list').classList.remove('hidden'); qs('#listTitle').textContent='Скидки';
      api('/api/products').then(data=>{ state.products = data.sort((a,b)=>a.price-b.price); renderList(true); });
      break;
    case tabs.fav:
      setActiveTab(btn);
      qs('#cats').classList.add('hidden'); qs('#cartPanel').classList.add('hidden');
      qs('#list').classList.remove('hidden'); qs('#listTitle').textContent='Избранное';
      const favIds = new Set((JSON.parse(localStorage.getItem('fav')||'[]')));
      api('/api/products').then(data=>{
        state.products = data.filter(p=>favIds.has(p.id));
        renderList();
      });
      break;
    case tabs.home:
      setActiveTab(btn); backToCats(); break;
    case tabs.cart:
      setActiveTab(btn); openCart(); break;
    case tabs.write:
      if (tg && tg.openTelegramLink){ tg.openTelegramLink('https://t.me/layoutplacebuy'); } else { alert('Напишите нам в чат бота'); }
      break;
  }
}

loadCats();
