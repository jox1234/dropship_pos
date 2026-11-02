const dsMoney=n=>'Rp '+new Intl.NumberFormat('id-ID',{maximumFractionDigits:0}).format(n||0);
const dsEsc=s=>{const e=document.createElement('span');e.textContent=s||'';return e.innerHTML};
const dsDate=s=>new Date(s).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'});
async function loadDeadstock(){
 const body=document.querySelector('#deadstock-rows');if(!body)return;
 try{
  const response=await fetch('/api/deadstock/'),data=await response.json();if(!response.ok)throw Error(data.error||'Could not load report');
  document.querySelector('#ds-count').textContent=data.count;document.querySelector('#ds-overdue').textContent=data.overdue;document.querySelector('#ds-remaining').textContent=data.remaining;document.querySelector('#ds-capital').textContent=dsMoney(data.capital);
  body.innerHTML=data.items.map(item=>{
   let actions='';
   if(item.remaining>0&&item.status!=='expired'&&item.status!=='removed'){
    actions=`<span class="pill">${dsEsc(item.status)}</span><div class="deadstock-actions"><form class="deadstock-action" data-id="${item.id}"><input type="hidden" name="action" value="extend"><label>Extend from today (days)<input type="number" name="days" min="1" max="3650" value="30" required></label><button class="button">Extend deadline</button></form><details><summary>Mark expired</summary><form class="deadstock-action" data-id="${item.id}"><input type="hidden" name="action" value="expire"><label>Reason (required)<input name="reason" required maxlength="500" placeholder="Why is this stock expired?"></label><button class="button danger">Confirm expired</button></form></details><details><summary>Remove stock</summary><form class="deadstock-action" data-id="${item.id}"><input type="hidden" name="action" value="remove"><label>Reason (optional)<input name="reason" maxlength="500" placeholder="Optional note"></label><button class="button danger">Remove completely</button></form></details></div>`;
   }else if(item.status==='expired'||item.status==='removed')actions=`<span class="pill">${dsEsc(item.status)}</span>${item.reason?`<small class="deadstock-reason">${dsEsc(item.reason)}</small>`:''}`;
   else actions='<span class="pill">Sold out</span>';
   return `<tr><td><b>${dsEsc(item.name)}</b><small>${dsEsc(item.category)}</small></td><td>${item.initial}</td><td>${item.sold}</td><td>${item.remaining}</td><td>${dsMoney(item.capital)}</td><td>${dsDate(item.deadline)}</td><td>${actions}</td></tr>`;
  }).join('')||'<tr><td colspan="7" class="empty">No stock tracked yet. Add a product with a stock count to begin.</td></tr>';
 }catch(error){body.innerHTML=`<tr><td colspan="7" class="empty">${dsEsc(error.message)}</td></tr>`}
}
document.querySelector('#deadstock-rows')?.addEventListener('submit',async event=>{
 const form=event.target.closest('.deadstock-action');if(!form)return;event.preventDefault();
 const action=new FormData(form).get('action');
 if(action==='remove'&&!confirm('Remove all remaining stock and archive this item? Past sales remain in reports.'))return;
 const token=document.cookie.split('; ').find(x=>x.startsWith('csrftoken='))?.split('=')[1]||document.querySelector('[name=csrfmiddlewaretoken]')?.value||'';
 try{
  const response=await fetch(`/deadstock/${form.dataset.id}/action/`,{method:'POST',body:new FormData(form),headers:{'X-CSRFToken':token,'X-Requested-With':'XMLHttpRequest'}}),data=await response.json();
  if(!response.ok)throw Error(data.error||'Action failed');const notice=document.querySelector('#notice');notice.textContent=data.message;notice.className='toast';await loadDeadstock();
 }catch(error){const notice=document.querySelector('#notice');notice.textContent=error.message;notice.className='toast error'}
});
loadDeadstock();
