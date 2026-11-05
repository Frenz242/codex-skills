import {handleCleanup,publicationPrefix,uploadPrefix} from './review-cleanup-service.mjs';
import {validateManifest,validateAssetBytes,validateObservation,digest,LIMITS} from './review-bundle.mjs';
export const CAPABILITIES={schema_version:1,transport:'multipart',max_file_bytes:8*1024*1024,max_bundle_bytes:20*1024*1024,max_request_bytes:21*1024*1024,cleanup_version:1};
const privateHeaders={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'};
const json=(data,status=200)=>Response.json(data,{status,headers:privateHeaders});
const fail=(status,message)=>{const e=new Error(message);e.status=status;throw e;};
const encoder=new TextEncoder();
export async function isWriter(request,env){
 const supplied=request.headers.get('X-Review-Publisher');
 if(!env.REVIEW_PUBLISHER_KEY||!supplied||supplied.length>1024||request.headers.has('Origin')||request.headers.has('Cookie'))return false;
 const [a,b]=await Promise.all([digest(encoder.encode(supplied)),digest(encoder.encode(env.REVIEW_PUBLISHER_KEY))]);
 let diff=0;for(let i=0;i<a.length;i++)diff|=a.charCodeAt(i)^b.charCodeAt(i);return diff===0;
}
async function boundedBody(request,limit){
 const length=request.headers.get('Content-Length');
 if(length&&(!/^\d+$/.test(length)||Number(length)>limit))fail(413,'Request too large');
 if(!request.body)fail(400,'Missing body');
 const reader=request.body.getReader(),chunks=[];let size=0;
 for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>limit){await reader.cancel();fail(413,'Request too large');}chunks.push(value);}
 const bytes=new Uint8Array(size);let at=0;for(const chunk of chunks){bytes.set(chunk,at);at+=chunk.length;}return bytes;
}
const readJson=async(request)=>{try{return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(await boundedBody(request,LIMITS.manifest)));}catch(e){if(e.status)throw e;fail(400,'Invalid JSON');}};
const keyOK=k=>typeof k==='string'&&/^[a-z0-9.-]+:[1-9][0-9]*:[1-9][0-9]*(?::[a-f0-9]{40}:[a-f0-9]{64})?$/.test(k);
const statement=(db,sql,...args)=>db.prepare(sql).bind(...args);
const stmtCleanup=(db,pr)=>statement(db,'SELECT pr_key FROM cleanup_receipts WHERE pr_key=?',pr).first();
async function review(db,key){return statement(db,'SELECT * FROM reviews WHERE pr_key=?',key).first();}
async function publication(db,key){return statement(db,'SELECT * FROM publications WHERE publication_key=?',key).first();}
function freshness(record,observed){return !observed?.head_sha?'unknown':observed.head_sha===record.revision.head_sha?'matches observed head':'stale';}
function receipt(record,current,status='published'){
 const m=JSON.parse(record.manifest),base='/?project='+encodeURIComponent(record.project_key);
 const observation=current?JSON.parse(current.observation):null;
 return {status,disposition:current?.current_key===record.publication_key?'current':'historical',
 publication_key:record.publication_key,tested_sha:m.revision.head_sha,version:current?.version||0,
 project_path:base,review_path:base+'&pr='+m.pull_request.number,asset_hashes:m.assets.map(a=>({id:a.id,sha256:a.sha256})),
 freshness:freshness(m,observation)};
}
async function publish(request,env){
 const raw=await boundedBody(request,CAPABILITIES.max_request_bytes);
 let form;try{form=await new Response(raw,{headers:{'Content-Type':request.headers.get('Content-Type')||''}}).formData();}catch{fail(400,'Multipart form required');}
 const values=form.getAll('manifest');if(values.length!==1||typeof values[0]!=='string'||encoder.encode(values[0]).length>LIMITS.manifest)fail(422,'One bounded manifest required');
 let m,identity;try{m=JSON.parse(values[0]);identity=await validateManifest(m);}catch(e){fail(422,e instanceof SyntaxError?'Invalid manifest JSON':e.message);}
 if(identity.bytes>CAPABILITIES.max_bundle_bytes||m.assets.some(a=>a.bytes>CAPABILITIES.max_file_bytes))fail(413,'Bundle exceeds service limits');
 const entries=[...form.entries()];if(entries.length!==1+m.assets.length)fail(422,'Unexpected or duplicate multipart fields');
 const files=[];
 for(const a of m.assets){
  const parts=form.getAll(a.id);if(parts.length!==1||typeof parts[0]==='string'||parts[0].name!==a.filename||parts[0].type!==a.mime)fail(422,'Asset field mismatch');
  const bytes=new Uint8Array(await parts[0].arrayBuffer());try{await validateAssetBytes(a,bytes);}catch(e){fail(422,e.message);}files.push([a,bytes]);
 }
 const db=env.DB,key=m.publication.key,pr=identity.pr_key;
 if(await stmtCleanup(db,pr))fail(410,'Merged PR evidence has been cleaned');
 const existing=await publication(db,key);
 if(existing)return json(receipt(existing,await review(db,pr),'unchanged'));
 const current=await review(db,pr),expected=m.publication.expected_current_version;
 if((current?.version||0)!==expected)fail(409,'Metadata version changed; refresh Site and GitHub before retrying');
 const previousObservation=current?JSON.parse(current.observation):null;
 if(previousObservation&&Date.parse(m.observed_github.observed_at)<Date.parse(previousObservation.observed_at))fail(409,'GitHub observation is older than stored state');
 const prefix=uploadPrefix(identity.project_key,crypto.randomUUID()),started=new Date().toISOString();
 const registered=await statement(db,"INSERT INTO upload_jobs(storage_prefix,pr_key,project_key,state,created_at,expires_at) SELECT ?,?,?,'uploading',?,? WHERE NOT EXISTS(SELECT 1 FROM cleanup_receipts WHERE pr_key=?)",prefix,pr,identity.project_key,started,new Date(Date.now()+15*60000).toISOString(),pr).run();
 if(registered.meta.changes!==1)fail(410,'Merged PR evidence has been cleaned');
 try {
 for(const [a,bytes] of files)await env.BUCKET.put(prefix+a.id+'/'+a.sha256,bytes,{httpMetadata:{contentType:a.mime}});

 const currentPublication=current?.current_key?await publication(db,current.current_key):null;
 const currentRevision=currentPublication?JSON.parse(currentPublication.manifest).revision:null;
 const olderCapture=currentRevision?.head_sha===m.revision.head_sha&&
  Date.parse(m.revision.captured_at)<Date.parse(currentRevision.captured_at);
 const promote=!olderCapture&&(m.observed_github.head_sha===m.revision.head_sha||!current?.current_key);
 const now=new Date().toISOString(),nextKey=promote?key:current.current_key;
 const result=await db.batch([
  statement(db,"INSERT OR IGNORE INTO publications(publication_key,pr_key,project_key,manifest,created_at,storage_prefix) SELECT ?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM upload_jobs WHERE storage_prefix=? AND state='uploading' AND expires_at>?) AND NOT EXISTS(SELECT 1 FROM cleanup_receipts WHERE pr_key=?)",key,pr,identity.project_key,JSON.stringify(m),now,prefix,prefix,now,pr),
  statement(db,'INSERT OR IGNORE INTO reviews(pr_key,project_key,repository,pr_number,version,current_key,observation,updated_at) SELECT ?,?,?,?,0,NULL,?,? WHERE EXISTS(SELECT 1 FROM publications WHERE publication_key=?) AND NOT EXISTS(SELECT 1 FROM cleanup_receipts WHERE pr_key=?)',pr,identity.project_key,JSON.stringify(m.repository),m.pull_request.number,JSON.stringify(m.observed_github),now,key,pr),
  statement(db,'UPDATE reviews SET version=version+1,current_key=?,observation=?,repository=?,updated_at=? WHERE pr_key=? AND version=? AND EXISTS(SELECT 1 FROM publications WHERE publication_key=?) AND NOT EXISTS(SELECT 1 FROM cleanup_receipts WHERE pr_key=?)',nextKey,JSON.stringify(m.observed_github),JSON.stringify(m.repository),now,pr,expected,key,pr)
 ]);
 if(result[2].meta.changes!==1)fail(409,'Concurrent publication retained as history; refresh Site and GitHub');
 return json(receipt(await publication(db,key),await review(db,pr)));
 } finally {
  // A committed prefix is protected by its publication. Uncommitted prefixes
  // remain discoverable after failures, interrupted responses and expired leases.
  try {
   const stored=await publication(db,key);
   if(stored?.storage_prefix===prefix)await statement(db,'DELETE FROM upload_jobs WHERE storage_prefix=?',prefix).run();
   else await statement(db,"UPDATE upload_jobs SET state='abandoned',expires_at=? WHERE storage_prefix=?",new Date().toISOString(),prefix).run();
  } catch { /* A later sweep reconciles the durable upload job. */ }
 }
}
async function observations(request,env){
 const b=await readJson(request);
 if(!b||Object.keys(b).sort().join(',')!=='expected_current_version,observed_github,pr_key'||!keyOK(b.pr_key)||!Number.isSafeInteger(b.expected_current_version)||b.expected_current_version<1)fail(422,'Invalid observation update');
 try{validateObservation(b.observed_github);}catch(e){fail(422,e.message);}
 const row=await review(env.DB,b.pr_key);if(!row)fail(404,'Review not found');
 if(Date.parse(b.observed_github.observed_at)<Date.parse(JSON.parse(row.observation).observed_at))fail(409,'Older observation rejected');
 const changed=await statement(env.DB,'UPDATE reviews SET observation=?,version=version+1,updated_at=? WHERE pr_key=? AND version=?',JSON.stringify(b.observed_github),new Date().toISOString(),b.pr_key,b.expected_current_version).run();
 if(changed.meta.changes!==1)fail(409,'Observation conflict; refresh state');
 const current=await review(env.DB,b.pr_key);
 return json({version:current.version,current_key:current.current_key});
}
export function byteRange(value,size){
 if(!value)return {start:0,end:size-1,status:200};
 const m=/^bytes=(\d*)-(\d*)$/.exec(value);
 if(!m||(!m[1]&&!m[2]))return null;
 let start,end=size-1;
 if(!m[1]){const n=Number(m[2]);if(!Number.isSafeInteger(n)||n<=0)return null;start=Math.max(0,size-n);}
 else{start=Number(m[1]);if(m[2])end=Math.min(end,Number(m[2]));}
 if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<0||start>=size||end<start)return null;
 return {start,end,status:206};
}
async function media(request,env,key,id){
 if(!keyOK(key)||!/^[a-z][a-z0-9-]{0,63}$/.test(id))fail(400,'Invalid media identity');
 const record=await publication(env.DB,key);if(!record)fail(404,'Publication not found');
 const asset=JSON.parse(record.manifest).assets.find(a=>a.id===id);if(!asset)fail(404,'Asset not found');
 const range=byteRange(request.headers.get('Range'),asset.bytes);
 if(!range)return new Response(null,{status:416,headers:{...privateHeaders,'Content-Range':'bytes */'+asset.bytes}});
 const length=range.end-range.start+1,headers={...privateHeaders,'Content-Type':asset.mime,'Content-Length':String(length),'Accept-Ranges':'bytes',
 'Content-Disposition':'inline; filename="'+asset.filename+'"','Content-Security-Policy':"default-src 'none'; sandbox"};
 if(range.status===206)headers['Content-Range']=`bytes ${range.start}-${range.end}/${asset.bytes}`;
 const objectKey=publicationPrefix(record)+asset.id+'/'+asset.sha256;
 if(request.method==='HEAD'){if(!await env.BUCKET.head(objectKey))fail(503,'Media unavailable');return new Response(null,{status:range.status,headers});}
 const object=await env.BUCKET.get(objectKey,{range:{offset:range.start,length}});if(!object)fail(503,'Media unavailable');
 return new Response(object.body,{status:range.status,headers});
}
export async function handleReview(request,env){
 try{
  if(!env.DB||!env.BUCKET)fail(503,'Storage unavailable');
  const writer=await isWriter(request,env),viewer=!!request.headers.get('oai-authenticated-user-id');
  const write=!['GET','HEAD'].includes(request.method);
  if(write&&!writer)fail(403,'Publisher authority required');
  if(!write&&!writer&&!viewer)fail(401,'Sign in required');
  const u=new URL(request.url),p=u.pathname.replace(/^\/api\/review\/v1\/?/,'').split('/').map(decodeURIComponent);
  if(p[0]==='cleanup'){if(!writer)fail(403,'Publisher authority required');return await handleCleanup(request,env,p,u,readJson);}
  if(p[0]==='capabilities'&&request.method==='GET')return json({...CAPABILITIES,publisher:writer});
  if(p[0]==='publications'&&p.length===1&&request.method==='POST')return await publish(request,env);
  if(p[0]==='publications'&&p.length===2&&request.method==='GET'){
   if(!keyOK(p[1]))fail(400,'Invalid publication key');const row=await publication(env.DB,p[1]);if(!row)fail(404,'Publication not found');return json(receipt(row,await review(env.DB,row.pr_key),'unchanged'));
  }
  if(p[0]==='observations'&&request.method==='PATCH')return await observations(request,env);
  if(p[0]==='media'&&p.length===3&&['GET','HEAD'].includes(request.method))return await media(request,env,p[1],p[2]);
  if(p[0]==='projects'&&request.method==='GET'){
   const result=await env.DB.prepare('SELECT project_key,COUNT(*) AS count,MAX(updated_at) AS updated_at FROM reviews GROUP BY project_key ORDER BY MAX(updated_at) DESC LIMIT 1001').all();
   if(result.results.length>1000)fail(413,'Project index requires pagination extension');
   const projects=[];for(const row of result.results){const last=await statement(env.DB,'SELECT repository FROM reviews WHERE project_key=? ORDER BY updated_at DESC LIMIT 1',row.project_key).first();projects.push({...row,repository:JSON.parse(last.repository)});}return json({projects});
  }
  if(p[0]==='review'&&request.method==='GET'){
   const pr=u.searchParams.get('pr');if(!keyOK(pr))fail(400,'PR identity required');const row=await review(env.DB,pr);if(!row)fail(404,'Review not found');
   return json({pr_key:row.pr_key,version:row.version,current_key:row.current_key,observed_github:JSON.parse(row.observation)});
  }
  if(p[0]==='reviews'&&request.method==='GET'){
   const project=u.searchParams.get('project'),after=u.searchParams.get('after')||'';
   if(!project||! /^[a-z0-9.-]+:[1-9][0-9]*$/.test(project)||after.length>200)fail(400,'Project required');
   const rows=await statement(env.DB,'SELECT r.*,p.manifest FROM reviews r JOIN publications p ON p.publication_key=r.current_key WHERE r.project_key=? AND r.pr_key>? ORDER BY r.pr_key LIMIT 101',project,after).all();
   const page=rows.results.slice(0,100);
   return json({reviews:page.map(r=>({pr_key:r.pr_key,version:r.version,publication_key:r.current_key,manifest:JSON.parse(r.manifest),observed_github:JSON.parse(r.observation),updated_at:r.updated_at})),next:rows.results.length>100?page.at(-1).pr_key:null});
  }
  if(p[0]==='history'&&request.method==='GET'){
   const pr=u.searchParams.get('pr'),after=u.searchParams.get('after')||'';if(!keyOK(pr)||after.length>300)fail(400,'PR identity required');
   const rows=await statement(env.DB,'SELECT publication_key,manifest,created_at FROM publications WHERE pr_key=? AND publication_key>? ORDER BY publication_key LIMIT 101',pr,after).all();
   return json({publications:rows.results.slice(0,100).map(r=>({publication_key:r.publication_key,manifest:JSON.parse(r.manifest),created_at:r.created_at})),next:rows.results.length>100?rows.results[99].publication_key:null});
  }
  fail(404,'Route not found');
 }catch(e){return json({error:e.status?e.message:'Storage operation failed; reconcile publication key before retrying'},e.status||503);}
}
