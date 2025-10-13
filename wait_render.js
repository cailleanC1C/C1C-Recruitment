const API='https://api.render.com/v1', KEY=process.env.RENDER_API_KEY, SID=process.env.RENDER_SERVICE_ID;
if(!KEY||!SID){console.error('Missing RENDER_API_KEY or RENDER_SERVICE_ID');process.exit(1);}
async function req(p,i={}){const r=await fetch(`${API}${p}`,{...i,headers:{'Authorization':`Bearer ${KEY}`,'Content-Type':'application/json',...(i.headers||{})}});if(!r.ok)throw new Error(`${r.status} ${r.statusText}: ${await r.text()}`);return r.json();}
async function latest(){const r=await req(`/services/${SID}/deploys?limit=1`);return r&&r.length?r[0]:null;}
const active=st=>['build_in_progress','update_in_progress','live_update_in_progress','canceled_by_user_pending','pre_deploy_in_progress'].includes(st);
async function cancel(id){await req(`/deploys/${id}/cancel`,{method:'POST'});}
(async function(){const start=Date.now(),timeout=10*60*1000;for(;;){const d=await latest();const st=d?.status||d?.deploy?.status||'';const id=d?.id||d?.deploy?.id||'';if(active(st)){try{await cancel(id);console.log('Canceled:',id,st);}catch(e){console.log('Cancel failed:',e.message);}await new Promise(r=>setTimeout(r,5000));if(Date.now()-start>timeout)throw new Error('Timeout waiting for lane');}else{console.log('Lane clear:',st||'none');process.exit(0);}}})().catch(e=>{console.error(e.message);process.exit(1);});
