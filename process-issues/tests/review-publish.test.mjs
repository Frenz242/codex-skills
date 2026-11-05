import test from 'node:test';
import assert from 'node:assert/strict';
import {publishReview,verifySite} from '../scripts/review-publish.mjs';
import {handleReview} from '../scripts/review-service.mjs';
import {publicationKey} from '../scripts/review-bundle.mjs';
import {fixture} from './fixtures/review-bundles.mjs';
import {storage} from './fixtures/review-storage.mjs';
const origin='https://review.example.chatgpt.site';
const config={schema_version:1,enabled:true,required:false,site:{project_id:'synthetic-site',origin},repository:{host:'github.example',id:101},auth:{method:'sites-service-and-publisher-key',service_token_env:'SITES_TOKEN',publisher_key_env:'PUBLISHER_KEY'},output_directory:'.codex/reviews',media:{target_seconds:10,max_file_bytes:1024*1024,max_bundle_bytes:2*1024*1024,ffmpeg:'ffmpeg',ffprobe:'ffprobe'}};
function metadata(){return {id:'synthetic-site',current_user_role:'owner',current_live_url:origin,access_mode:'custom',siwc_bypass_bearer_token:'synthetic-service',access_policy:{access_mode:'custom',allowed_users:[{account_user_id:'synthetic-owner',role:'owner'}],allowed_account_user_ids:['synthetic-owner'],allowed_groups:[],allowed_workspace_group_ids:[],allowed_tenant_group_ids:[],allowed_editors:[],external_visitor_count:0}};}
async function input(env){const m=await fixture();env.REVIEW_PUBLISHER_KEY='synthetic-publisher-secret-for-tests';return {config,manifest:m,assets:new Map(),site:metadata(),metadataReadAt:new Date().toISOString(),publisherKey:env.REVIEW_PUBLISHER_KEY,observe:async()=>({...m.observed_github,observed_at:new Date().toISOString()}),fetchImpl:async(url,options)=>handleReview(new Request(url,options),env)};}
test('disabled publishing never observes GitHub, writes storage or requests credentials',async()=>{
 const result=await publishReview({config:{schema_version:1,enabled:false},fetchImpl:()=>{throw Error('must not run')}});assert.equal(result.status,'disabled');
});
test('native Site identity, sharing and timestamp checked before networking',()=>{
 for(const change of [s=>s.id='wrong',s=>s.current_live_url='https://wrong.example',s=>s.current_user_role='editor',s=>s.access_mode='public',s=>s.access_policy.external_visitor_count=1,s=>s.access_policy.allowed_users.push({role:'viewer'}),s=>s.access_policy.allowed_editors=[{role:'editor'}],s=>delete s.siwc_bypass_bearer_token]){
  const s=metadata();change(s);assert.throws(()=>verifySite(config,s,new Date().toISOString()));
 }
 assert.throws(()=>verifySite(config,metadata(),'2001-01-01T00:00:00Z'));
});
test('actual client publishes, observes twice, stores one entry and retries without a second POST',async()=>{
 const env=storage();try{const i=await input(env);let posts=0,observations=0;const fetch=i.fetchImpl;i.fetchImpl=(u,o)=>{if(o.method==='POST')posts++;assert.equal(o.redirect,'error');return fetch(u,o);};const observe=i.observe;i.observe=()=>{observations++;return observe();};
 const first=await publishReview(i);assert.equal(first.stored_bytes_verified,true);assert.equal(first.disposition,'current');assert.match(first.review_url,/pr=7$/);assert.equal(observations,2);
 const second=await publishReview(i);assert.equal(second.status,'unchanged');assert.equal(posts,1);
 }finally{env.close();}
});
test('timeout after commit reconciles by key without a duplicate upload',async()=>{
 const env=storage();try{const i=await input(env);let posts=0;const fetch=i.fetchImpl;i.fetchImpl=async(u,o)=>{const result=await fetch(u,o);if(o.method==='POST'){posts++;throw Error('synthetic lost response');}return result;};const r=await publishReview(i);assert.equal(r.publication_key,i.manifest.publication.key);assert.equal(posts,1);}finally{env.close();}
});
test('final GitHub read failure produces unknown freshness, not success at an old head',async()=>{
 const env=storage();try{const i=await input(env);let n=0;const observe=i.observe;i.observe=()=>{if(++n===2)throw Error('offline');return observe();};const r=await publishReview(i);assert.equal(r.freshness,'unknown');assert.match(r.limitation,/Final GitHub/);}finally{env.close();}
});
test('head changing during upload marks evidence stale while preserving tested SHA',async()=>{
 const env=storage();try{const i=await input(env);let n=0;i.observe=async()=>({...i.manifest.observed_github,head_sha:++n===1?i.manifest.revision.head_sha:'f'.repeat(40),observed_at:new Date().toISOString()});const r=await publishReview(i);assert.equal(r.freshness,'stale');assert.equal(r.tested_sha,i.manifest.revision.head_sha);}finally{env.close();}
});
test('redirect responses are rejected without following or forwarding credentials',async()=>{
 const env=storage();try{const i=await input(env);let calls=0;i.fetchImpl=async()=>{calls++;return new Response(null,{status:302,headers:{location:'https://outside.example/'}});};await assert.rejects(publishReview(i),/redirect/);assert.equal(calls,1);}finally{env.close();}
});

test('failed observation PATCH retains publication and reports unknown freshness',async()=>{
 const env=storage();try{const i=await input(env);const fetch=i.fetchImpl;i.fetchImpl=async(u,o)=>{if(o.method==='PATCH')throw Error('synthetic offline');return fetch(u,o);};
 const r=await publishReview(i);assert.equal(r.stored_bytes_verified,true);assert.equal(r.freshness,'unknown');assert.match(r.limitation,/Observation refresh/);
 }finally{env.close();}
});

for(const failure of ['interrupted body','invalid JSON']){
 test('reconciles committed upload with '+failure+' without a second POST',async()=>{
  const env=storage();try{
   const i=await input(env),fetch=i.fetchImpl;let posts=0,lookupsAfterPost=0;
   i.fetchImpl=async(u,o)=>{
    if(posts&&u.includes('/publications/'))lookupsAfterPost++;
    const result=await fetch(u,o);
    if(o.method==='POST'){posts++;return failure==='invalid JSON'?new Response('{',{status:200}):new Response(new ReadableStream({start(c){c.error(Error('synthetic response interruption'));}}),{status:200});}
    return result;
   };
   const r=await publishReview(i);assert.equal(r.publication_key,i.manifest.publication.key);assert.equal(r.stored_bytes_verified,true);assert.equal(posts,1);assert.equal(lookupsAfterPost,2,'one reconciliation lookup plus final receipt read');
  }finally{env.close();}
 });
}
test('unreadable uncommitted upload performs one reconciliation and leaves outcome unknown',async()=>{
 const env=storage();try{
  const i=await input(env),fetch=i.fetchImpl;let posts=0,lookupsAfterPost=0;
  i.fetchImpl=async(u,o)=>{if(o.method==='POST'){posts++;return new Response('{',{status:200});}if(posts&&u.includes('/publications/'))lookupsAfterPost++;return fetch(u,o);};
  await assert.rejects(publishReview(i),/Upload outcome unknown/);assert.equal(posts,1);assert.equal(lookupsAfterPost,1);
 }finally{env.close();}
});
test('known authorization and conflict failures do not trigger ambiguous-upload recovery',async()=>{
 for(const status of [403,409]){
  const env=storage();try{
   const i=await input(env),fetch=i.fetchImpl;let posts=0,lookupsAfterPost=0;
   i.fetchImpl=async(u,o)=>{if(o.method==='POST'){posts++;return new Response(null,{status});}if(posts&&u.includes('/publications/'))lookupsAfterPost++;return fetch(u,o);};
   await assert.rejects(publishReview(i),status===403?/authorization failed/:/Publication conflict/);assert.equal(posts,1);assert.equal(lookupsAfterPost,0);
  }finally{env.close();}
 }
});


for(const newerFirst of [false,true])for(const differentHead of [false,true]){
 test(`retry concurrent ${differentHead?'Git head':'capture'} with newer first=${newerFirst} selects newest evidence without media upload`,async()=>{
  const env=storage();try{
   const old=await input(env),next=await input(env);
   next.manifest.revision.captured_at='2026-01-02T00:00:00Z';
   if(differentHead){next.manifest.revision.head_sha='c'.repeat(40);next.manifest.demonstration.source_sha=next.manifest.revision.head_sha;next.manifest.observed_github.head_sha=next.manifest.revision.head_sha;}
   next.manifest.publication.key=await publicationKey(next.manifest);
   const batch=env.DB.batch.bind(env.DB);let count=0,release;const gate=new Promise(r=>release=r);
   env.DB.batch=async statements=>{if(++count===2)release();await gate;return batch(statements);};
   const ordered=newerFirst?[next,old]:[old,next];
   const results=await Promise.allSettled(ordered.map(i=>publishReview(i)));
   assert.equal(results[0].status,'fulfilled');assert.equal(results[1].status,'rejected');assert.match(results[1].reason.message,/conflict/);
   const retry=ordered[1],transport=retry.fetchImpl;
   let uploads=0,reconciliations=0;
   retry.observe=async()=>({...next.manifest.observed_github,observed_at:new Date().toISOString()});
   retry.fetchImpl=(url,options)=>{if(options.method==='POST'){if(url.endsWith('/publications'))uploads++;else reconciliations++;}return transport(url,options);};
   const receipt=await publishReview(retry);
   assert.equal(receipt.disposition,newerFirst?'historical':'current');assert.equal(uploads,0);assert.equal(reconciliations,1);
   assert.equal(env.sql.prepare('SELECT current_key FROM reviews').get().current_key,next.manifest.publication.key);
   assert.equal(env.sql.prepare('SELECT COUNT(*) AS n FROM publications').get().n,2);
  }finally{env.close();}
 });
}
