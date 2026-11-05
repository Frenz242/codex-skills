import test from 'node:test';
import assert from 'node:assert/strict';
import {handleReview,byteRange} from '../scripts/review-service.mjs';
import {publicationKey,digest} from '../scripts/review-bundle.mjs';
import {fixture} from './fixtures/review-bundles.mjs';
import {storage} from './fixtures/review-storage.mjs';
const origin='https://review.example.chatgpt.site',prefix='/api/review/v1/';
function call(env,route,options={}){return handleReview(new Request(origin+prefix+route,{...options,headers:options.headers||{'X-Review-Publisher':'synthetic-writer-key'}}),env);}
async function bundle(){const m=await fixture(),bytes=new TextEncoder().encode('synthetic output\n');m.assets=[{id:'output',role:'output',filename:'result.txt',mime:'text/plain',bytes:bytes.length,sha256:await digest(bytes),caption:'Synthetic output fixture',width:null,height:null,duration_ms:null,codec:null}];m.publication.key=await publicationKey(m);return {m,bytes};}
function upload(env,m,bytes,extra=false){const f=new FormData();f.append('manifest',JSON.stringify(m));f.append('output',new Blob([bytes],{type:'text/plain'}),'result.txt');if(extra)f.append('extra','bad');return call(env,'publications',{method:'POST',body:f});}
test('writer boundary, idempotency, media bytes, HEAD/range and signed-out rejection',async()=>{
 const env=storage();try{
 const {m,bytes}=await bundle();
 for(const headers of [{},{'oai-authenticated-user-id':'viewer'},{'X-Review-Publisher':'wrong'},{'X-Review-Publisher':env.REVIEW_PUBLISHER_KEY,Origin:origin},{'X-Review-Publisher':env.REVIEW_PUBLISHER_KEY,Cookie:'session=1'}])assert.equal((await call(env,'publications',{method:'POST',headers,body:'bad'})).status,403);
 const response=await upload(env,m,bytes);assert.equal(response.status,200);const receipt=await response.json();assert.equal(receipt.version,1);assert.equal(receipt.disposition,'current');
 assert.equal((await (await upload(env,m,bytes)).json()).status,'unchanged');
 const route='media/'+encodeURIComponent(m.publication.key)+'/output';
 for(const method of ['GET','HEAD']){assert.equal((await call(env,route,{method,headers:{Range:'bytes=0-2'}})).status,401);}
 const file=await call(env,route);assert.deepEqual(new Uint8Array(await file.arrayBuffer()),bytes);assert.match(file.headers.get('cache-control'),/private/);
 const head=await call(env,route,{method:'HEAD'});assert.equal(Number(head.headers.get('content-length')),bytes.length);
 const range=await call(env,route,{headers:{'oai-authenticated-user-id':'viewer',Range:'bytes=0-2'}});assert.equal(range.status,206);assert.equal(await range.text(),'syn');
 assert.equal((await call(env,route,{headers:{'oai-authenticated-user-id':'viewer',Range:'bytes=-0'}})).status,416);
 const lookup=await (await call(env,'publications/'+encodeURIComponent(m.publication.key))).json();assert.equal(lookup.publication_key,m.publication.key);
 }finally{env.close();}
});
test('bad bytes and multipart mismatch are rejected before storage',async()=>{
 const env=storage();try{const {m,bytes}=await bundle();assert.equal((await upload(env,m,bytes,true)).status,422);assert.equal((await upload(env,m,new Uint8Array(bytes.length))).status,422);assert.equal(env.objects.size,0);}finally{env.close();}
});
test('R2 then DB failure preserves previous review; retry recovers once',async()=>{
 const env=storage();try{
 const {m,bytes}=await bundle();await upload(env,m,bytes);
 const n=structuredClone(m);n.summary.changed='Second capture';n.publication.expected_current_version=1;n.publication.key=await publicationKey(n);
 env.DB.fail=true;assert.equal((await upload(env,n,bytes)).status,503);env.DB.fail=false;
 const first=await (await call(env,'reviews?project=github.example%3A101')).json();assert.equal(first.reviews[0].publication_key,m.publication.key);
 assert.equal((await call(env,'publications/'+encodeURIComponent(n.publication.key))).status,404);
 assert.equal((await upload(env,n,bytes)).status,200);
 assert.equal((await (await upload(env,n,bytes)).json()).status,'unchanged');
 }finally{env.close();}
});
test('late/stale publication cannot displace newer observed-head evidence',async()=>{
 const env=storage();try{
 const {m,bytes}=await bundle();await upload(env,m,bytes);
 const newer=structuredClone(m);newer.revision.head_sha='c'.repeat(40);newer.demonstration.source_sha=newer.revision.head_sha;newer.observed_github.head_sha=newer.revision.head_sha;newer.observed_github.observed_at='2026-01-02T00:00:00Z';newer.publication.expected_current_version=1;newer.publication.key=await publicationKey(newer);await upload(env,newer,bytes);
 const late=structuredClone(m);late.summary.changed='Late capture';late.publication.key=await publicationKey(late);late.publication.expected_current_version=1;
 assert.equal((await upload(env,late,bytes)).status,409);
 late.publication.expected_current_version=2;assert.equal((await upload(env,late,bytes)).status,409,'refreshing CAS alone is insufficient');
 late.observed_github=structuredClone(newer.observed_github);
 const historical=await (await upload(env,late,bytes)).json();assert.equal(historical.disposition,'historical');assert.equal(historical.freshness,'stale');
 const rows=await (await call(env,'reviews?project=github.example%3A101')).json();assert.equal(rows.reviews[0].publication_key,newer.publication.key);
 }finally{env.close();}
});
test('observations are guarded and never change publication identity or promote history',async()=>{
 const env=storage();try{
 const {m,bytes}=await bundle();await upload(env,m,bytes);const observed={...m.observed_github,head_sha:null,observed_at:'2026-01-02T00:00:00Z'};
 const patch={method:'PATCH',body:JSON.stringify({pr_key:'github.example:101:7',expected_current_version:1,observed_github:observed})};
 assert.equal((await call(env,'observations',patch)).status,200);assert.equal((await call(env,'observations',patch)).status,409);
 const record=await (await call(env,'publications/'+encodeURIComponent(m.publication.key))).json();assert.equal(record.freshness,'unknown');assert.equal(record.publication_key,m.publication.key);
 }finally{env.close();}
});
test('different repositories with equal PR numbers persist independently',async()=>{
 const env=storage();try{
 const {m,bytes}=await bundle();await upload(env,m,bytes);
 const n=structuredClone(m);n.repository.id=102;n.pull_request.base.repository.id=102;n.pull_request.head.repository.id=102;n.publication.key=await publicationKey(n);await upload(env,n,bytes);
 const projects=await (await call(env,'projects')).json();assert.equal(projects.projects.length,2);assert.deepEqual(projects.projects.map(p=>p.count),[1,1]);
 }finally{env.close();}
});
test('range parser rejects malformed/multipart/unsafe integers and supports suffix',()=>{
 assert.deepEqual(byteRange('bytes=-2',10),{start:8,end:9,status:206});
 for(const value of ['bytes=-0','bytes=12-','bytes=5-3','bytes=0-1,4-5','bytes=99999999999999999-','bogus'])assert.equal(byteRange(value,10),null);
});

test('simultaneous same-PR publications preserve one current pointer and both histories',async()=>{
 const env=storage();try{
 const {m,bytes}=await bundle(),n=structuredClone(m);n.summary.changed='Competing capture';n.publication.key=await publicationKey(n);
 const put=env.BUCKET.put.bind(env.BUCKET);let count=0,release;const gate=new Promise(r=>release=r);
 env.BUCKET.put=async(...args)=>{await put(...args);if(++count===2)release();await gate;};
 const responses=await Promise.all([upload(env,m,bytes),upload(env,n,bytes)]);
 assert.deepEqual(responses.map(r=>r.status).sort(),[200,409]);
 const rows=await (await call(env,'reviews?project=github.example%3A101')).json();assert.equal(rows.reviews.length,1);assert.equal(rows.reviews[0].version,1);
 const history=await (await call(env,'history?pr=github.example%3A101%3A7')).json();assert.equal(history.publications.length,2);
 for(const record of history.publications)assert.equal((await call(env,'media/'+encodeURIComponent(record.publication_key)+'/output')).status,200);
 }finally{env.close();}
});
test('simultaneous different PRs do not lose either update',async()=>{
 const env=storage();try{
 const {m,bytes}=await bundle(),n=structuredClone(m);n.pull_request.number=8;n.pull_request.url=n.repository.url+'/pull/8';n.publication.key=await publicationKey(n);
 const results=await Promise.all([upload(env,m,bytes),upload(env,n,bytes)]);assert.deepEqual(results.map(r=>r.status),[200,200]);
 const rows=await (await call(env,'reviews?project=github.example%3A101')).json();assert.equal(rows.reviews.length,2);
 }finally{env.close();}
});
test('bounded request, reserved fields and unavailable media fail without claiming delivery',async()=>{
 const env=storage();try{
 assert.equal((await call(env,'publications',{method:'POST',headers:{'X-Review-Publisher':env.REVIEW_PUBLISHER_KEY,'Content-Length':String(22*1024*1024)},body:'x'})).status,413);
 const {m,bytes}=await bundle();m.assets[0].id='manifest';m.publication.key=await publicationKey(m);assert.equal((await upload(env,m,bytes)).status,422);
 m.assets[0].id='output';m.publication.key=await publicationKey(m);env.BUCKET.fail=true;assert.equal((await upload(env,m,bytes)).status,503);env.BUCKET.fail=false;
 assert.equal((await call(env,'publications/'+encodeURIComponent(m.publication.key))).status,404);
 await upload(env,m,bytes);env.objects.clear();
 for(const method of ['GET','HEAD'])assert.equal((await call(env,'media/'+encodeURIComponent(m.publication.key)+'/output',{method})).status,503);
 }finally{env.close();}
});
