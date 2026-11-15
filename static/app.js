'use strict';
const $ = id => document.getElementById(id);
let apiKey = '', allSlots = [], selected = null, nextCursor = null, historyEmail = '', pending = null;
const date = value => new Date(value).toLocaleDateString(undefined, {weekday:'short', month:'short', day:'numeric', year:'numeric'});
const time = value => new Date(value).toLocaleTimeString(undefined, {hour:'2-digit', minute:'2-digit'});
function message(text='') { $('message').textContent = text; }
function node(tag, text, className) { const e = document.createElement(tag); e.textContent = text; if(className)e.className=className; return e; }
async function api(path, options={}) {
  const response = await fetch(path, {...options, headers:{'X-API-Key':apiKey, 'Content-Type':'application/json', ...options.headers}});
  const body = await response.json();
  if(!response.ok) {
    let text = body.error || 'Request failed. Please try again.';
    if(response.status===429) text += ` Please wait ${response.headers.get('Retry-After')} seconds.`;
    const error = new Error(text); error.status=response.status; throw error;
  }
  return body;
}
function renderSlots() {
  const box=$('slots'); box.replaceChildren();
  const visible=allSlots.filter(s=>s.available && new Date(s.start)>new Date() && (!$('provider').value || s.provider===$('provider').value));
  if(!visible.length) { box.append(node('p','No available appointments right now. Try another clinician or refresh.','empty')); return; }
  for(const s of visible) {
    const b=node('button','', 'slot'+(selected?.id===s.id?' active':'')); b.type='button'; b.setAttribute('aria-pressed', selected?.id===s.id?'true':'false');
    const detail=node('span',''); detail.append(node('strong',s.provider),node('small',date(s.start)));
    b.append(detail,node('span',time(s.start)+' – '+time(s.end),'time'));
    b.onclick=()=>{selected=s;pending=null;$('confirmation').hidden=true;$('selected').textContent=`${s.provider} · ${date(s.start)} · ${time(s.start)} – ${time(s.end)}`;$('book').disabled=false;renderSlots();};
    box.append(b);
  }
}
async function loadSlots() {
  allSlots=(await api('/slots')).slots;
  const previous=$('provider').value;
  $('provider').replaceChildren(new Option('All clinicians',''), ...[...new Set(allSlots.map(s=>s.provider))].sort().map(p=>new Option(p,p)));
  if([...$('provider').options].some(o=>o.value===previous))$('provider').value=previous;
  if(selected && !allSlots.some(s=>s.id===selected.id && s.available)) {selected=null;$('book').disabled=true;$('selected').textContent='Choose another available time.';}
  renderSlots();
}
$('connect').onsubmit=async e=>{e.preventDefault();message();apiKey=$('api-key').value.trim();try{await loadSlots();for(const id of ['refresh','provider','find','lookup'])$(id).disabled=false;message('Connected. Choose an appointment below.');}catch(err){apiKey='';for(const id of ['refresh','provider','find','lookup','book'])$(id).disabled=true;message(err.message);}};
$('provider').onchange=renderSlots;
$('refresh').onclick=()=>loadSlots().then(()=>message()).catch(e=>message(e.message));
$('booking-form').onsubmit=async e=>{
  e.preventDefault();if(!selected)return;message();$('book').disabled=true;
  const body=JSON.stringify({slot_id:selected.id,name:$('name').value,email:$('email').value});
  if(!pending || pending.body!==body)pending={body,key:crypto.randomUUID()};
  let booked=false;
  try {
    const booking=await api('/bookings',{method:'POST',body,headers:{'Idempotency-Key':pending.key}});
    booked=true;pending=null;selected=null;
    const box=$('confirmation');box.replaceChildren(node('h3','You’re booked.'),node('p',`${booking.name}, your appointment is confirmed.`),node('p','Booking reference: '+booking.id),node('p','Keep this reference, or find your booking below using your email.'));
    box.hidden=false;box.focus();$('selected').textContent='Your place is saved.';$('history-email').value=booking.email;
    await loadSlots();
  } catch(err){message((booked?'Appointment confirmed, but refreshing slots failed. ': '')+err.message);if(err.status && err.status!==429)pending=null;}
  finally{$('book').disabled=!selected;}
};
function bookingRow(b) {
  const row=node('div','','booking-row'), details=node('div','');const slot=allSlots.find(s=>s.id===b.slot_id);
  details.append(node('strong',slot?slot.provider:'Appointment '+b.slot_id),node('p',slot?date(slot.start)+' · '+time(slot.start):b.name),node('small',b.id),node('div',b.status,'badge'+(b.status==='cancelled'?' cancelled':'')));
  row.append(details);
  if(b.status==='confirmed') {const cancel=node('button','Cancel','text-button');cancel.onclick=async()=>{if(!window.confirm('Cancel this appointment and release the slot?'))return;cancel.disabled=true;try{await api('/bookings/'+encodeURIComponent(b.id),{method:'DELETE'});row.replaceWith(bookingRow({...b,status:'cancelled'}));await loadSlots();message('Appointment cancelled.');}catch(err){message(err.message);cancel.disabled=false;}};row.append(cancel);}
  return row;
}
async function loadHistory(more=false) {
  const params=new URLSearchParams({email:historyEmail,limit:'5'});if(more && nextCursor)params.set('cursor',nextCursor);
  const page=await api('/bookings?'+params);if(!more)$('history-results').replaceChildren();
  if(!more && !page.bookings.length)$('history-results').append(node('p','No bookings found for this email.','hint'));
  for(const b of page.bookings)$('history-results').append(bookingRow(b));nextCursor=page.next_cursor;$('more').hidden=!nextCursor;
}
$('history-form').onsubmit=async e=>{e.preventDefault();historyEmail=$('history-email').value.trim();$('find').disabled=true;try{await loadHistory();message();}catch(err){message(err.message);}finally{$('find').disabled=false;}};
$('more').onclick=async()=>{$('more').disabled=true;try{await loadHistory(true);}catch(err){message(err.message);}finally{$('more').disabled=false;}};
$('lookup-form').onsubmit=async e=>{e.preventDefault();try{const b=await api('/bookings/'+encodeURIComponent($('booking-id').value.trim()));$('lookup-result').replaceChildren(bookingRow(b));message();}catch(err){$('lookup-result').replaceChildren();message(err.message);}};
