import {validateConfig,validateManifest,validateAssetBytes,identities,digest} from './review-bundle.mjs';
export function verifySite(config,site,readAt,now=Date.now()){
 if(!site||site.id!==config.site.project_id||site.current_user_role!=='owner'||site.current_live_url!==config.site.origin)throw Error('Native Site identity/origin/ownership mismatch');
 if(!Number.isFinite(Date.parse(readAt))||now-Date.parse(readAt)>120000||Date.parse(readAt)>now+5000)throw Error('Refresh native Site metadata immediately before publishing');
 const p=site.access_policy;
 if(site.access_mode!=='custom'||!p||p.access_mode!=='custom'||p.allowed_users?.length!==1||p.allowed_users[0].role!=='owner'||p.allowed_users[0].is_external||p.allowed_account_user_ids?.length!==1||p.allowed_account_user_ids[0]!==p.allowed_users[0].account_user_id||p.external_visitor_count!==0||p.allowed_groups?.length!==0||p.allowed_workspace_group_ids?.length!==0||p.allowed_tenant_group_ids?.length!==0||(p.allowed_editors?.length||0)!==0)throw Error('Destination must be verified owner-private; sharing was not changed');
 if(!site.siwc_bypass_bearer_token)throw Error('Native Site service credential unavailable');
}
async function bounded(response,limit){
 const reader=response.body?.getReader();if(!reader)return new Uint8Array();
 const chunks=[];let length=0;for(;;){const {done,value}=await reader.read();if(done)break;length+=value.length;if(length>limit){await reader.cancel();throw Error('Service response exceeds limit');}chunks.push(value);}
 const bytes=new Uint8Array(length);let at=0;for(const b of chunks){bytes.set(b,at);at+=b.length;}return bytes;
}
export async function publishReview({config,manifest,assets,site,metadataReadAt,publisherKey,observe,fetchImpl=fetch}){
 const c=validateConfig(config);if(!c.enabled)return {status:'disabled',site_mutations:0};
 verifySite(c,site,metadataReadAt);
 if(typeof publisherKey!=='string'||publisherKey.length<24)throw Error('Publisher credential unavailable');
 const m=structuredClone(manifest),id=await validateManifest(m);
 if(m.repository.id!==c.repository.id||m.repository.host!==c.repository.host)throw Error('Configured repository does not match evidence');
 if(assets.size!==m.assets.length)throw Error('Asset inventory mismatch');
 for(const a of m.assets){await validateAssetBytes(a,assets.get(a.id));if(a.bytes>c.media.max_file_bytes)throw Error('Configured file limit exceeded');}
 if(id.bytes>c.media.max_bundle_bytes)throw Error('Configured bundle limit exceeded');
 const base=c.site.origin+'/api/review/v1/',headers={'OAI-Sites-Authorization':'Bearer '+site.siwc_bypass_bearer_token,'X-Review-Publisher':publisherKey};
 const request=async(route,options={})=>{
  let r;try{r=await fetchImpl(base+route,{...options,headers:{...headers,...options.headers},redirect:'error',signal:AbortSignal.timeout(30000)});}catch{throw Error('Site request failed or timed out; reconcile the publication key before retrying');}
  if(r.status>=300&&r.status<400)throw Error('Site redirect rejected');
  return r;
 };
 const data=async(r)=>{try{return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(await bounded(r,1024*1024)));}catch{throw Error('Invalid service response');}};
 const expect=async(r,allow404=false)=>{if(allow404&&r.status===404)return null;if(!r.ok)throw Error(r.status===409?'Publication conflict: refresh GitHub and Site state before another attempt':r.status===401||r.status===403?'Site authentication or publisher authorization failed':'Site operation failed with status '+r.status);return data(r);};
 const cap=await expect(await request('capabilities'));
 if(cap.schema_version!==1||cap.transport!=='multipart'||cap.publisher!==true)throw Error('Unsupported publisher capabilities');
 if(!Number.isSafeInteger(cap.max_file_bytes)||!Number.isSafeInteger(cap.max_bundle_bytes)||id.bytes>cap.max_bundle_bytes||m.assets.some(a=>a.bytes>cap.max_file_bytes))throw Error('Service upload limit exceeded');
 // observe must verify repository ID, PR number, head/base repos and refs via gh.
 m.observed_github=await observe();
 let result=await expect(await request('publications/'+encodeURIComponent(m.publication.key)),true);
 if(!result){
  const current=await expect(await request('review?pr='+encodeURIComponent(id.pr_key)),true);
  m.publication.expected_current_version=current?.version||0;
  const form=new FormData();form.append('manifest',JSON.stringify(m));
  for(const a of m.assets)form.append(a.id,new Blob([assets.get(a.id)],{type:a.mime}),a.filename);
  let response;
  try{response=await request('publications',{method:'POST',body:form});}
  catch{result=await expect(await request('publications/'+encodeURIComponent(m.publication.key)),true);if(!result)throw Error('Upload outcome unknown; no duplicate write attempted. Retry this finalized bundle later.');}
  if(response){
   if(response.status>=500){result=await expect(await request('publications/'+encodeURIComponent(m.publication.key)),true);if(!result)throw Error('Upload not confirmed; local evidence retained for retry');}
   else result=await expect(response);
  }
 }
 function checkReceipt(r){
  if(!r||r.publication_key!==m.publication.key||r.tested_sha!==m.revision.head_sha||!Number.isSafeInteger(r.version)||!['published','unchanged'].includes(r.status)||!['current','historical'].includes(r.disposition)||r.asset_hashes?.length!==m.assets.length||m.assets.some(a=>!r.asset_hashes.some(h=>h.id===a.id&&h.sha256===a.sha256)))throw Error('Receipt does not match evidence');
 }
 checkReceipt(result);
 for(const a of m.assets){
  const r=await request('media/'+encodeURIComponent(m.publication.key)+'/'+a.id);
  if(!r.ok||r.headers.get('Content-Type')!==a.mime)throw Error('Stored asset unavailable or wrong type');
  const bytes=await bounded(r,a.bytes);if(bytes.length!==a.bytes||await digest(bytes)!==a.sha256)throw Error('Stored asset integrity check failed');
 }
 let finalObservation,limitation='';
 try{finalObservation=await observe();}catch{finalObservation={...m.observed_github,head_sha:null,observed_at:new Date().toISOString(),checks:'unknown',reviews:'unknown'};limitation='Final GitHub check failed; freshness unknown';}
 let observationFailed=false;
 try { const update=await request('observations',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({pr_key:id.pr_key,expected_current_version:result.version,observed_github:finalObservation})});
 if(!update.ok){observationFailed=true;limitation=limitation||'Observation refresh conflicted or failed; newer stored evidence was preserved';}
 } catch {observationFailed=true;limitation=limitation||'Observation refresh unavailable; publication retained, freshness unknown';}
 const final=await expect(await request('publications/'+encodeURIComponent(m.publication.key)));checkReceipt(final);
 return {...final,status:result.status,project_url:c.site.origin+'/?project='+encodeURIComponent(id.project_key),review_url:c.site.origin+'/?project='+encodeURIComponent(id.project_key)+'&pr='+m.pull_request.number,
 ...(limitation?{limitation}:{}),freshness:observationFailed||finalObservation.head_sha===null?'unknown':final.freshness,completed_at:new Date().toISOString(),stored_bytes_verified:true};
}
