import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,lstat,symlink,readdir} from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {handleReview} from '../scripts/review-service.mjs';
import {runCleanup} from '../scripts/review-cleanup-cli.mjs';
import {spawnSync} from 'node:child_process';
import {cleanupEvidence} from '../scripts/review-cleanup.mjs';
import {markEvidenceDirectory,discoverLocalEvidence,removeLocalEvidence} from '../scripts/review-cleanup-local.mjs';
import {validateConfig,publicationKey,digest} from '../scripts/review-bundle.mjs';
import {fixture} from './fixtures/review-bundles.mjs';
import {storage} from './fixtures/review-storage.mjs';
const origin='https://cleanup.example.chatgpt.site',project='github.example:101',pr=project+':7';
const config={schema_version:1,enabled:true,required:false,site:{project_id:'synthetic-site',origin},repository:{host:'github.example',id:101},auth:{method:'sites-service-and-publisher-key',service_token_env:'SITES_TOKEN',publisher_key_env:'PUBLISHER_KEY'},output_directory:'.codex/reviews',media:{target_seconds:10,max_file_bytes:1024*1024,max_bundle_bytes:2*1024*1024,ffmpeg:'ffmpeg',ffprobe:'ffprobe'},cleanup:{merged_prs:true,orphan_grace_hours:24}};
const metadata=()=>({id:'synthetic-site',current_user_role:'owner',current_live_url:origin,access_mode:'custom',siwc_bypass_bearer_token:'synthetic-service',access_policy:{access_mode:'custom',allowed_users:[{account_user_id:'owner',role:'owner'}],allowed_account_user_ids:['owner'],allowed_groups:[],allowed_workspace_group_ids:[],allowed_tenant_group_ids:[],allowed_editors:[],external_visitor_count:0}});
const proof=()=>({pr_key:pr,state:'merged',merged_at:'2026-01-02T00:00:00Z',checked_at:new Date().toISOString()});
const call=(env,route,body,headers)=>handleReview(new Request(origin+'/api/review/v1/'+route,{method:body?'POST':'GET',headers:headers||{'X-Review-Publisher':env.REVIEW_PUBLISHER_KEY,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})}),env);
const merge=(env,apply=true)=>{const {state,...p}=proof();return call(env,'cleanup/merged',{...p,apply});};
const sweep=(env,phase='uploads',apply=true)=>call(env,'cleanup/orphans',{project_key:project,phase,cursor:'',grace_hours:24,apply});
async function bundle(number=7){
 const m=await fixture(),bytes=new TextEncoder().encode('synthetic cleanup fixture');
 m.pull_request.number=number;m.pull_request.url=m.repository.url+'/pull/'+number;
 m.assets=[{id:'output',role:'output',filename:'output.txt',mime:'text/plain',bytes:bytes.length,sha256:await digest(bytes),caption:'Synthetic output',width:null,height:null,duration_ms:null,codec:null}];
 m.publication.key=await publicationKey(m);return {m,bytes};
}
async function upload(env,m,bytes) {
 const f=new FormData();f.append('manifest',JSON.stringify(m));f.append('output',new Blob([bytes],{type:'text/plain'}),'output.txt');
 return handleReview(new Request(origin+'/api/review/v1/publications',{method:'POST',headers:{'X-Review-Publisher':env.REVIEW_PUBLISHER_KEY},body:f}),env);
}
function client(env,extra={}) {
 env.REVIEW_PUBLISHER_KEY='synthetic-publisher-secret-for-cleanup';
 return {config,site:metadata(),metadataReadAt:new Date().toISOString(),publisherKey:env.REVIEW_PUBLISHER_KEY,observe:async()=>proof(),fetchImpl:(u,o)=>handleReview(new Request(u,o),env),...extra};
}
test('cleanup is opt-in and minimum orphan grace is enforced',async()=>{
 const disabled=await cleanupEvidence({config:{...config,cleanup:undefined},fetchImpl:()=>{throw Error('network');}});
 assert.equal(disabled.status,'disabled');
 assert.throws(()=>validateConfig({...config,cleanup:{merged_prs:true,orphan_grace_hours:23}}));
 assert.equal(validateConfig(config).cleanup.orphan_grace_hours,24);
});
test('viewer, browser-origin requests and stale merge proofs cannot delete',async()=>{
 const env=storage();try{
  const b={...proof(),apply:true};delete b.state;
  for(const h of [{},{'oai-authenticated-user-id':'viewer'},{'X-Review-Publisher':env.REVIEW_PUBLISHER_KEY,Origin:origin}])
   assert.equal((await call(env,'cleanup/merged',b,h)).status,403);
  b.checked_at='2020-01-01T00:00:00Z';assert.equal((await call(env,'cleanup/merged',b)).status,422);
  assert.equal(env.sql.prepare('SELECT COUNT(*) AS n FROM cleanup_receipts').get().n,0);
 }finally{env.close();}
});
test('all revisions deleted, another PR preserved, receipt retained and late publication rejected',async()=>{
 const env=storage();try{
  const {m,bytes}=await bundle();assert.equal((await upload(env,m,bytes)).status,200);
  const late=structuredClone(m);late.summary.changed='Second revision';late.publication.key=await publicationKey(late);late.publication.expected_current_version=1;
  assert.equal((await upload(env,late,bytes)).status,200);
  const other=await bundle(8);assert.equal((await upload(env,other.m,other.bytes)).status,200);
  assert.equal((await (await merge(env,false)).json()).status,'planned');assert.equal(env.objects.size,3);
  assert.equal((await (await merge(env)).json()).status,'complete');assert.equal(env.objects.size,1);
  assert.equal(env.sql.prepare('SELECT COUNT(*) AS n FROM publications WHERE pr_key=?').get(pr).n,0);
  assert.equal(env.sql.prepare('SELECT COUNT(*) AS n FROM reviews WHERE pr_key=?').get(pr).n,0);
  assert.ok(env.sql.prepare('SELECT completed_at FROM cleanup_receipts WHERE pr_key=?').get(pr).completed_at);
  assert.equal((await upload(env,m,bytes)).status,410);
  assert.equal((await (await merge(env)).json()).status,'complete');
 }finally{env.close();}
});
test('partial R2 deletion is resumable and never claims completion early',async()=>{
 const env=storage();try{
  const {m,bytes}=await bundle();await upload(env,m,bytes);env.BUCKET.failDelete=true;
  assert.equal((await merge(env)).status,503);assert.equal(env.objects.size,1);
  assert.equal(env.sql.prepare('SELECT completed_at FROM cleanup_receipts WHERE pr_key=?').get(pr).completed_at,null);
  env.BUCKET.failDelete=false;assert.equal((await (await merge(env)).json()).status,'complete');assert.equal(env.objects.size,0);
 }finally{env.close();}
});
test('cleanup fences an upload already in flight and retry removes its abandoned bytes',async()=>{
 const env=storage();try{
  let release,started;const entered=new Promise(r=>{started=r;});const wait=new Promise(r=>{release=r;});const put=env.BUCKET.put.bind(env.BUCKET);
  env.BUCKET.put=async(k,b)=>{started();await wait;return put(k,b);};
  const {m,bytes}=await bundle(),publishing=upload(env,m,bytes);await entered;
  assert.equal((await (await merge(env)).json()).status,'pending');
  release();assert.equal((await publishing).status,409);
  assert.equal((await (await merge(env)).json()).status,'complete');
  assert.equal(env.objects.size,0);assert.equal(env.sql.prepare('SELECT COUNT(*) AS n FROM publications').get().n,0);
 }finally{env.close();}
});
test('orphan grace protects recent, active and committed uploads and scopes repositories',async()=>{
 const env=storage();try{
  const {m,bytes}=await bundle();await upload(env,m,bytes);
  const old=new Date(Date.now()-48*3600000);
  for(const k of env.objects.keys())env.uploaded.set(k,old); // committed media must remain
  const stale='uploads/'+project+'/11111111-1111-1111-1111-111111111111/output/hash';
  const recent='uploads/'+project+'/22222222-2222-2222-2222-222222222222/output/hash';
  const foreign='uploads/github.example:102/33333333-3333-3333-3333-333333333333/output/hash';
  const active='uploads/'+project+'/44444444-4444-4444-4444-444444444444/output/hash';
  for(const k of [stale,recent,foreign,active]){await env.BUCKET.put(k,bytes);if(k!==recent)env.uploaded.set(k,old);}
  env.sql.prepare('INSERT INTO upload_jobs VALUES(?,?,?,?,?,?)').run(active.split('/').slice(0,3).join('/')+'/',pr,project,'uploading',old.toISOString(),new Date(Date.now()+60000).toISOString());
  assert.equal((await (await sweep(env,'uploads',false)).json()).eligible,1);assert.equal(env.objects.size,5);
  assert.equal((await (await sweep(env)).json()).deleted,1);
  assert.equal(env.objects.has(stale),false);for(const k of [recent,foreign,active])assert.ok(env.objects.has(k));
  assert.equal(env.objects.size,4);
 }finally{env.close();}
});
test('legacy committed media remains readable and legacy orphan sweep is safe',async()=>{
 const env=storage();try{
  const {m,bytes}=await bundle();await upload(env,m,bytes);
  const row=env.sql.prepare('SELECT * FROM publications').get(),oldKey=[...env.objects.keys()][0];
  const legacy='evidence/'+m.publication.key+'/output/'+m.assets[0].sha256;
  await env.BUCKET.put(legacy,bytes);await env.BUCKET.delete(oldKey);
  env.sql.prepare('UPDATE publications SET storage_prefix=NULL').run();
  const orphan=legacy.replace(m.publication.key,m.publication.key.slice(0,-1)+(m.publication.key.endsWith('a')?'b':'a'));
  await env.BUCKET.put(orphan,bytes);
  for(const k of env.objects.keys())env.uploaded.set(k,new Date(Date.now()-48*3600000));
  assert.equal((await (await sweep(env,'legacy')).json()).deleted,1);assert.ok(env.objects.has(legacy));
  const media=await call(env,'media/'+encodeURIComponent(m.publication.key)+'/output');assert.equal(media.status,200);
  await merge(env);assert.equal(env.objects.size,0);
 }finally{env.close();}
});
test('expired uploader cannot commit after orphan collection claims its job',async()=>{
 const env=storage();try{
  let release,started;const entered=new Promise(r=>{started=r;});const wait=new Promise(r=>{release=r;});const put=env.BUCKET.put.bind(env.BUCKET);
  env.BUCKET.put=async(k,b)=>{started();await wait;return put(k,b);};
  const {m,bytes}=await bundle(),publishing=upload(env,m,bytes);await entered;
  const old=new Date(Date.now()-48*3600000).toISOString();env.sql.prepare('UPDATE upload_jobs SET created_at=?,expires_at=?').run(old,old);
  await sweep(env);release();assert.equal((await publishing).status,409);
  assert.equal(env.sql.prepare('SELECT COUNT(*) AS n FROM publications').get().n,0);
  for(const k of env.objects.keys())env.uploaded.set(k,new Date(old));
  await sweep(env);assert.equal(env.objects.size,0);
 }finally{env.close();}
});
test('client preserves open/closed PRs and unknown GitHub state fails before mutation',async()=>{
 const env=storage();try{
  const i=client(env,{localPrKeys:[pr],observe:async()=>({...proof(),state:'closed',merged_at:null})});
  const {m,bytes}=await bundle();await upload(env,m,bytes);
  const r=await cleanupEvidence({...i,apply:true});assert.equal(r.results[0].status,'preserved');assert.equal(env.objects.size,1);
  await assert.rejects(cleanupEvidence({...i,apply:true,observe:async()=>{throw Error('GitHub unavailable');}}),/GitHub unavailable/);
  assert.equal(env.objects.size,1);
 }finally{env.close();}
});
test('lost cleanup response resumes from receipt and finishes local cleanup once',async()=>{
 const env=storage();try{
  const i=client(env,{localPrKeys:[pr],apply:true}),{m,bytes}=await bundle();await upload(env,m,bytes);
  let dropped=false,local=0;const fetch=i.fetchImpl;i.cleanLocal=async()=>{local++;return {status:'complete'};};
  i.fetchImpl=async(u,o)=>{const r=await fetch(u,o);if(u.endsWith('cleanup/merged')&&!dropped){dropped=true;throw Error('lost response');}return r;};
  await assert.rejects(cleanupEvidence(i),/lost response/);assert.equal(local,0);assert.equal(env.objects.size,0);
  const r=await cleanupEvidence(i);assert.equal(r.results[0].status,'complete');assert.equal(local,1);
 }finally{env.close();}
});
test('client dry run never mutates objects or local files',async()=>{
 const env=storage();try{
  let localApply;const i=client(env,{localPrKeys:[pr],cleanLocal:async(_,apply)=>{localApply=apply;return {status:'planned'};}});
  const {m,bytes}=await bundle();await upload(env,m,bytes);const r=await cleanupEvidence(i);
  assert.equal(r.status,'planned');assert.equal(localApply,false);assert.equal(env.objects.size,1);
  assert.equal(env.sql.prepare('SELECT COUNT(*) AS n FROM cleanup_receipts').get().n,0);
 }finally{env.close();}
});
test('local cleanup removes only registered PR directories and preserves receipt/config/unowned files',async()=>{
 const root=await mkdtemp(path.join(tmpdir(),'cleanup-local-')),run=path.join(root,'run');
 await mkdir(run);await mkdir(path.join(run,'frames'));await writeFile(path.join(run,'frames','raw.jpg'),'synthetic');
 await writeFile(path.join(root,'unrelated.txt'),'keep');await markEvidenceDirectory(run,pr);
 assert.equal((await discoverLocalEvidence(root)).length,1);
 assert.equal((await removeLocalEvidence(root,run,pr)).status,'planned');assert.ok(await lstat(run));
 await removeLocalEvidence(root,run,pr,{apply:true});assert.deepEqual(await readdir(root),['unrelated.txt']);
});
test('local cleanup rejects root, traversal, foreign ownership and nested mixed PRs before deletion',async()=>{
 const root=await mkdtemp(path.join(tmpdir(),'cleanup-safety-')),run=path.join(root,'run');await mkdir(run);await markEvidenceDirectory(run,pr);
 await assert.rejects(removeLocalEvidence(root,root,pr,{apply:true}),/strictly inside/);
 await assert.rejects(removeLocalEvidence(root,path.dirname(root),pr,{apply:true}),/strictly inside/);
 await assert.rejects(removeLocalEvidence(root,run,project+':8',{apply:true}),/ownership/);
 const nested=path.join(run,'other');await mkdir(nested);await markEvidenceDirectory(nested,project+':8');
 await writeFile(path.join(run,'preserve.txt'),'keep');
 await assert.rejects(removeLocalEvidence(root,run,pr,{apply:true}),/another PR/);
 assert.equal(await readFile(path.join(run,'preserve.txt'),'utf8'),'keep');
});
test('local cleanup refuses junctions and preserves external contents',async()=>{
 const root=await mkdtemp(path.join(tmpdir(),'cleanup-links-')),outside=await mkdtemp(path.join(tmpdir(),'cleanup-outside-')),run=path.join(root,'run');
 await mkdir(run);await markEvidenceDirectory(run,pr);await writeFile(path.join(outside,'keep.txt'),'keep');
 await symlink(outside,path.join(run,'linked'),'junction');
 await assert.rejects(removeLocalEvidence(root,run,pr,{apply:true}),/Linked/);
 assert.equal(await readFile(path.join(outside,'keep.txt'),'utf8'),'keep');
});

test('shared publication receipts are selected by exact PR and cannot erase unrelated files',async()=>{
 const {findPublicationReceipts,removePublicationReceipt}=await import('../scripts/review-cleanup-local.mjs');
 const root=await mkdtemp(path.join(tmpdir(),'cleanup-receipts-')),dir=path.join(root,'receipts');await mkdir(dir);
 const hash='c'.repeat(64),key=pr+':'+'a'.repeat(40)+':'+hash,file=path.join(dir,hash+'.json');
 await writeFile(file,JSON.stringify({publication_key:key}));
 await writeFile(path.join(dir,'unrelated.json'),'{}');
 assert.equal((await findPublicationReceipts(root)).length,1);
 await assert.rejects(removePublicationReceipt(root,file,project+':8'),/identity changed/);
 await removePublicationReceipt(root,file,pr);
 assert.deepEqual(await readdir(dir),['unrelated.json']);
});
test('client does not busy-poll an active upload',async()=>{
 const env=storage();try{
  const i=client(env,{localPrKeys:[pr],apply:true});
  env.sql.prepare('INSERT INTO upload_jobs VALUES(?,?,?,?,?,?)').run('uploads/'+project+'/11111111-1111-1111-1111-111111111111/',pr,project,'uploading',new Date().toISOString(),new Date(Date.now()+60000).toISOString());
  let calls=0;const fetch=i.fetchImpl;i.fetchImpl=(u,o)=>{if(u.endsWith('cleanup/merged'))calls++;return fetch(u,o);};
  const result=await cleanupEvidence(i);
  assert.equal(result.results[0].status,'pending');assert.equal(calls,1);
 }finally{env.close();}
});


test('cleanup CLI handles absent local output: dry-run stays read-only and apply deletes hosted evidence',async()=>{
 const env=storage();try{
  const root=await mkdtemp(path.join(tmpdir(),'review-cleanup-cli-')),cfgFile=path.join(root,'config.json');
  const init=spawnSync('git',['-C',root,'init','-b','main'],{encoding:'utf8'});assert.equal(init.status,0,init.stderr);
  await writeFile(path.join(root,'.git','info','exclude'),'config.json\n.codex/reviews/\n');
  const cfg={...config};
  await writeFile(cfgFile,JSON.stringify(cfg));
  const c=client(env),{m,bytes}=await bundle();await upload(env,m,bytes);
  const repoUrl='https://github.example/sample/widget';let inventoryReads=0;
  const deps={github:args=>args[0]==='repo'?{nameWithOwner:'sample/widget',url:repoUrl}:args.at(-1).includes('/pulls/')?{number:7,base:{repo:{id:101}},merged_at:proof().merged_at,state:'closed'}:{id:101,html_url:repoUrl},
   readSecrets:async()=>({native_site:c.site,metadata_read_at:new Date().toISOString(),publisher_key:c.publisherKey}),
   fetchImpl:(url,options)=>{if(url.includes('/cleanup/inventory'))inventoryReads++;return c.fetchImpl(url,options);}};
  const dry=await runCleanup(['run',cfgFile,root],deps);
  assert.equal(dry.status,'planned');assert.equal(dry.results[0].local.files,0);assert.equal(env.objects.size,1);
  const output=path.join(root,cfg.output_directory);
  await assert.rejects(lstat(output),{code:'ENOENT'});
  const applied=await runCleanup(['run',cfgFile,root,'--apply'],deps);
  assert.equal(applied.status,'processed');assert.equal(applied.results[0].status,'complete');assert.equal(applied.results[0].local.status,'complete');
  assert.equal(env.objects.size,0);assert.equal(inventoryReads,2);
  const receipts=await readdir(path.join(output,'cleanup-receipts'));assert.equal(receipts.length,2);
  const record=JSON.parse(await readFile(path.join(output,'cleanup-receipts',receipts.find(f=>f!=='sweep.json')),'utf8'));
  assert.equal(record.status,'complete');assert.equal(record.pr_key,pr);
 }finally{env.close();}
});
