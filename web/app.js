const TWA = window.Telegram?.WebApp;
const API = {
  categories: "/api/categories",
  subcats:    "/api/subcategories?category=",
  products:   "/api/products?category={cat}&subcategory={sub}",
  order:      "/api/order"
};

const CLOTHES_SIZES = ["XS","S","M","L","XL","XXL"];
let cart = []; // {id,title,price,size,qty}

function $(sel){ return document.querySelector(sel); }
function el(tag, attrs={}, ...children){
  const n = document.createElement(tag);
  Object.entries(attrs).forEach(([k,v])=>{
    if(k==='class') n.className=v; else if(k==='html') n.innerHTML=v; else n.setAttribute(k,v);
  });
  children.forEach(c=> n.appendChild(typeof c==='string'? document.createTextNode(c): c));
  return n;
}

async function init(){
  try{
    const cats = await (await fetch(API.categories)).json();
    renderCats(cats);
    if (cats.length) loadProducts(cats[0].title);
  }catch(e){ console.error(e); }
  updateBadge();
  if(TWA){ TWA.ready(); TWA.expand(); }
}
function renderCats(cats){
  const wrap = $("#cats"); wrap.innerHTML = "";
  cats.forEach(c=>{
    const b = el("button",{class:"category", onclick:()=>loadProducts(c.title)}, c.title);
    wrap.appendChild(b);
  });
}
async function loadProducts(category){
  const list = $("#products"); list.innerHTML = "";
  const url = API.products.replace("{cat}", encodeURIComponent(category)).replace("{sub}","");
  const items = await (await fetch(url)).json();
  items.forEach(p=> list.appendChild(productCard(p)));
}
function productCard(p){
  const sizes = (p.sizes && p.sizes.length)? p.sizes : CLOTHES_SIZES;
  const sel = el("select",{id:`size-${p.id}`});
  sizes.forEach(s=> sel.appendChild(el("option",{value:s}, s)));
  const btn = el("button",{class:"btn", onclick:()=>addToCart(p, sel.value)}, "В корзину");
  return el("div",{class:"card"},
    el("h4",{}, p.title),
    el("div",{class:"price"}, `${p.price.toLocaleString('ru-RU')} ₽`),
    sel, btn
  );
}
function addToCart(p, size){
  const ex = cart.find(it=> it.id===p.id && it.size===size);
  if(ex){ ex.qty += 1; } else { cart.push({id:p.id,title:p.title,price:p.price,size,qty:1}); }
  updateBadge();
  if(TWA) TWA.HapticFeedback.impactOccurred('light');
}
function updateBadge(){
  const n = cart.reduce((a,b)=>a+b.qty,0);
  $("#cartCount").textContent = n;
}
function openCart(){
  if(!cart.length){ alert("Корзина пуста"); return; }
  const lines = cart.map(it=> `${it.title} [${it.size}] × ${it.qty} — ${it.price*it.qty} ₽`);
  alert(lines.join("\n"));
}

function writeManager(){
  window.location.href = "tg://user?id=6773668793";
}

function openCheckout(){ $("#modal").classList.remove("hidden"); }
function closeCheckout(){ $("#modal").classList.add("hidden"); }

function validatePhone(p){ return /^\+7\d{10}$/.test(p.trim()); }
function validateTelegram(t){ return /^@?[a-zA-Z0-9_]{5,}$/.test(t.trim()); }

async function submitOrder(){
  const fio = $("#fio").value.trim();
  const phone = $("#phone").value.trim();
  const address = $("#address").value.trim();
  const comment = $("#comment").value.trim();
  const telegram = $("#telegram").value.trim();

  if(!validatePhone(phone)){ return showError("Телефон должен быть в формате +7XXXXXXXXXX"); }
  if(!cart.length){ return showError("Корзина пуста"); }

  const payload = {
    items: cart.map(it=> ({product_id: it.id, size: it.size, qty: it.qty})),
    full_name: fio, phone, address, comment, telegram
  };

  if (TWA && TWA.sendData){
    TWA.sendData(JSON.stringify(payload));
    closeCheckout();
    return;
  }
  try{
    const r = await fetch(API.order,{method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)});
    const j = await r.json();
    if(j.ok){ closeCheckout(); alert("Заказ оформлен!"); cart=[]; updateBadge(); }
    else showError("Не удалось оформить заказ");
  }catch(e){ console.error(e); showError("Ошибка сети"); }
}

function showError(msg){ $("#formError").textContent = msg; setTimeout(()=>$("#formError").textContent="", 3000); }

init();
