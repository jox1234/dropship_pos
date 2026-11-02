(()=>{
 const pageSize=10;
 function attach(table){
  if(table.dataset.tableTools==='ready')return;table.dataset.tableTools='ready';
  const tbody=table.tBodies[0];if(!tbody)return;
  let page=1,query='';
  const bar=document.createElement('div');bar.className='table-tools';
  const search=document.createElement('input');search.type='search';search.className='table-search';search.placeholder='Search this table';search.setAttribute('aria-label','Search table rows');
  const count=document.createElement('span');count.className='table-count';
  const prev=document.createElement('button');prev.type='button';prev.className='button table-page';prev.textContent='Previous';
  const pageLabel=document.createElement('span');pageLabel.className='table-page-label';
  const next=document.createElement('button');next.type='button';next.className='button table-page';next.textContent='Next';
  bar.append(search,count,prev,pageLabel,next);table.parentElement.insertBefore(bar,table);
  function render(){
   const all=[...tbody.rows],empty=all.find(row=>row.querySelector('[colspan]'))||null,rows=all.filter(row=>row!==empty),filtered=rows.filter(row=>row.textContent.toLocaleLowerCase().includes(query));
   const pages=Math.max(1,Math.ceil(filtered.length/pageSize));page=Math.min(page,pages);
   rows.forEach(row=>{const index=filtered.indexOf(row);row.hidden=index<0||Math.floor(index/pageSize)!==page-1});
   if(empty){empty.hidden=rows.length>0&&filtered.length>0;const cell=empty.querySelector('[colspan]');if(rows.length&&cell)cell.textContent=query?'No matching rows.':'No data to show.'}
   count.textContent=filtered.length?`Showing ${(page-1)*pageSize+1}-${Math.min(page*pageSize,filtered.length)} of ${filtered.length}`:'0 results';
   pageLabel.textContent=`Page ${page} of ${pages}`;prev.disabled=page<=1;next.disabled=page>=pages;
  }
  search.addEventListener('input',()=>{query=search.value.trim().toLocaleLowerCase();page=1;render()});
  prev.addEventListener('click',()=>{page=Math.max(1,page-1);render()});next.addEventListener('click',()=>{page++;render()});
  new MutationObserver(render).observe(tbody,{childList:true});render();
 }
 function scan(root=document){root.querySelectorAll('table').forEach(attach)}
 scan();new MutationObserver(records=>records.forEach(record=>record.addedNodes.forEach(node=>{if(node.nodeType===1){if(node.matches?.('table'))attach(node);scan(node)}}))).observe(document.body,{childList:true,subtree:true});
})();
