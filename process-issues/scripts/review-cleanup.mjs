import {validateConfig} from './review-bundle.mjs';
import {verifySite} from './review-publish.mjs';
export async function cleanupEvidence({config,site,metadataReadAt,publisherKey,observe,
 localPrKeys=[],cleanLocal=async()=>({status:'none'}),fetchImpl=fetch,apply=false,sweepState={}}) {
 const c=validateConfig(config);
 if(!c.enabled||!c.cleanup?.merged_prs)return {status:'disabled',site_mutations:0};
 verifySite(c,site,metadataReadAt);
 if(!/^[A-Za-z0-9_-]{32,128}$/.test(publisherKey||''))throw Error('Publisher credential unavailable');
 const project=c.repository.host+':'+c.repository.id,base=c.site.origin+'/api/review/v1/';
 const request=async(route,body)=>{
  const r=await fetchImpl(base+route,{method:body?'POST':'GET',
   headers:{'OAI-Sites-Authorization':'Bearer '+site.siwc_bypass_bearer_token,'X-Review-Publisher':publisherKey,...(body?{'Content-Type':'application/json'}:{})},
   ...(body?{body:JSON.stringify(body)}:{}),redirect:'error',signal:AbortSignal.timeout(30000)});
  if(!r.ok)throw Error('Cleanup service returned '+r.status+'; rerun to resume');
  const reader=r.body.getReader(),chunks=[];let size=0;
  for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>1024*1024){await reader.cancel();throw Error('Cleanup response too large');}chunks.push(value);}
  const bytes=new Uint8Array(size);let at=0;for(const chunk of chunks){bytes.set(chunk,at);at+=chunk.length;}
  return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
 };
 const cap=await request('capabilities');
 if(cap.cleanup_version!==1||cap.publisher!==true)throw Error('Deploy cleanup-capable service first');
 const keys=new Set(localPrKeys);let after='';
 for(let page=0;page<100;page++){
  const r=await request('cleanup/inventory?project='+encodeURIComponent(project)+'&after='+encodeURIComponent(after));
  for(const key of r.pr_keys)keys.add(key);
  after=r.next;if(!after)break;
 }
 if(after)throw Error('Inventory exceeds bounded cleanup run');
 const results=[];
 for(const pr of keys) {
  if(!pr.startsWith(project+':')||!/^\d+$/.test(pr.slice(project.length+1)))throw Error('Cleanup inventory repository mismatch');
  let proof=await observe(pr);
  if(proof.pr_key!==pr)throw Error('GitHub PR identity mismatch');
  if(proof.state!=='merged'||!proof.merged_at){results.push({pr_key:pr,status:'preserved',reason:'not merged'});continue;}
  let remote;
  for(let batch=0;batch<20;batch++) {
   if(batch)proof=await observe(pr);
   if(proof.pr_key!==pr||proof.state!=='merged'||!proof.merged_at)throw Error('Merge verification changed');
   remote=await request('cleanup/merged',{pr_key:pr,merged_at:proof.merged_at,checked_at:proof.checked_at,apply});
   if(remote.pr_key!==pr||!['planned','pending','complete'].includes(remote.status))throw Error('Invalid cleanup receipt');
   if(remote.status!=='pending'||remote.reason==='active upload')break;
  }
  const local=remote.status==='complete'||!apply?await cleanLocal(pr,apply):{status:'pending'};
  results.push({pr_key:pr,status:remote.status,local});
 }
 const sweeps=[];
 for(const phase of ['legacy','uploads']) {
  let cursor=sweepState[phase]||'',r;
  for(let page=0;page<20;page++){
   r=await request('cleanup/orphans',{project_key:project,phase,cursor,grace_hours:c.cleanup.orphan_grace_hours,apply});
   if(r.phase!==phase||!['planned','swept'].includes(r.status))throw Error('Invalid sweep receipt');
   sweeps.push({phase,eligible:r.eligible,deleted:r.deleted});cursor=r.next;if(!cursor)break;
  }
  sweepState[phase]=cursor||'';
 }
 return {status:apply?'processed':'planned',results,sweeps,sweep_state:sweepState};
}
