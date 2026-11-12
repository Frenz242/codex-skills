// Publisher-only maintenance. Merge proof is supplied by the CLI after a fresh gh read.
const stmt=(db,sql,...args)=>db.prepare(sql).bind(...args);
const fail=(status,message)=>{const e=Error(message);e.status=status;throw e;};
const projectOK=s=>typeof s==='string'&&/^[a-z0-9.-]+:[1-9][0-9]*$/.test(s);
const prOK=s=>typeof s==='string'&&/^[a-z0-9.-]+:[1-9][0-9]*:[1-9][0-9]*$/.test(s);
const reply=x=>Response.json(x,{headers:{'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}});
export const uploadPrefix=(project,id)=>'uploads/'+project+'/'+id+'/';
export const publicationPrefix=row=>row.storage_prefix||'evidence/'+row.publication_key+'/';
async function erasePrefix(bucket,prefix) {
 const page=await bucket.list({prefix,limit:100});
 for(const o of page.objects) await bucket.delete(o.key);
 return !(await bucket.list({prefix,limit:1})).objects.length;
}
export async function handleCleanup(request,env,parts,url,readJson) {
 const db=env.DB,now=new Date().toISOString();
 if(parts[1]==='inventory'&&request.method==='GET') {
  const project=url.searchParams.get('project'),after=url.searchParams.get('after')||'';
  if(!projectOK(project)||(after&&!prOK(after)))fail(422,'Invalid cleanup inventory scope');
  const rows=await stmt(db,'SELECT pr_key FROM reviews WHERE project_key=? AND pr_key>? UNION SELECT pr_key FROM cleanup_receipts WHERE project_key=? AND pr_key>? AND completed_at IS NULL UNION SELECT pr_key FROM upload_jobs WHERE project_key=? AND pr_key>? ORDER BY pr_key LIMIT 101',project,after,project,after,project,after).all();
  return reply({pr_keys:rows.results.slice(0,100).map(r=>r.pr_key),next:rows.results.length>100?rows.results[99].pr_key:null});
 }
 if(request.method!=='POST')fail(404,'Cleanup route not found');
 const b=await readJson(request);
 if(parts[1]==='merged') {
  if(!b||Object.keys(b).sort().join(',')!=='apply,checked_at,merged_at,pr_key'||!prOK(b.pr_key)||typeof b.apply!=='boolean'
   ||!Number.isFinite(Date.parse(b.merged_at))||Date.parse(b.merged_at)>Date.now()
   ||!Number.isFinite(Date.parse(b.checked_at))||Date.now()-Date.parse(b.checked_at)>120000||Date.parse(b.checked_at)>Date.now()+5000)
    fail(422,'Fresh verified merge identity required');
  const pr=b.pr_key,project=pr.split(':').slice(0,2).join(':');
  const rows=await stmt(db,'SELECT * FROM publications WHERE pr_key=? ORDER BY publication_key LIMIT 10',pr).all();
  if(!b.apply)return reply({status:'planned',pr_key:pr,publications_at_least:rows.results.length});
  await stmt(db,'INSERT OR IGNORE INTO cleanup_receipts(pr_key,project_key,merged_at,started_at,completed_at) VALUES(?,?,?,?,NULL)',pr,project,b.merged_at,now).run();
  for(const row of rows.results) {
   if(!await erasePrefix(env.BUCKET,publicationPrefix(row)))return reply({status:'pending',pr_key:pr});
   await stmt(db,'DELETE FROM publications WHERE publication_key=?',row.publication_key).run();
  }
  const jobs=await stmt(db,'SELECT * FROM upload_jobs WHERE pr_key=? LIMIT 10',pr).all();
  for(const job of jobs.results) {
   if(job.state==='uploading'&&job.expires_at>now)continue;
   await stmt(db,"UPDATE upload_jobs SET state='deleting' WHERE storage_prefix=?",job.storage_prefix).run();
   if(await erasePrefix(env.BUCKET,job.storage_prefix))
    await stmt(db,'DELETE FROM upload_jobs WHERE storage_prefix=?',job.storage_prefix).run();
  }
  const remaining=await stmt(db,'SELECT publication_key AS id FROM publications WHERE pr_key=? UNION ALL SELECT storage_prefix AS id FROM upload_jobs WHERE pr_key=? LIMIT 1',pr,pr).first();
  if(remaining)return reply({status:'pending',pr_key:pr,reason:jobs.results.some(j=>j.state==='uploading'&&j.expires_at>now)?'active upload':'more evidence'});
  await db.batch([
   stmt(db,'DELETE FROM reviews WHERE pr_key=?',pr),
   stmt(db,'UPDATE cleanup_receipts SET completed_at=COALESCE(completed_at,?) WHERE pr_key=?',now,pr)
  ]);
  const receipt=await stmt(db,'SELECT pr_key,merged_at,completed_at FROM cleanup_receipts WHERE pr_key=?',pr).first();
  return reply({status:'complete',...receipt});
 }
 if(parts[1]==='orphans') {
  if(!b||!projectOK(b.project_key)||typeof b.apply!=='boolean'||!Number.isInteger(b.grace_hours)||b.grace_hours<24||b.grace_hours>720
    ||!['legacy','uploads'].includes(b.phase)||typeof b.cursor!=='string'||b.cursor.length>2048
    ||Object.keys(b).sort().join(',')!=='apply,cursor,grace_hours,phase,project_key')fail(422,'Invalid orphan sweep scope');
  const cutoff=Date.now()-b.grace_hours*3600000,prefix=b.phase==='legacy'?'evidence/'+b.project_key+':':'uploads/'+b.project_key+'/';
  const page=await env.BUCKET.list({prefix,limit:100,...(b.cursor?{cursor:b.cursor}:{})});
  let eligible=0,deleted=0;
  for(const o of page.objects) {
   if(!Number.isFinite(new Date(o.uploaded).getTime())||new Date(o.uploaded).getTime()>cutoff)continue;
   if(b.phase==='legacy') {
    const key=o.key.split('/')[1];
    if(!new RegExp('^[a-z0-9.-]+:[1-9][0-9]*:[1-9][0-9]*:[a-f0-9]{40}:[a-f0-9]{64}$').test(key))continue;
    if(await stmt(db,'SELECT publication_key FROM publications WHERE publication_key=?',key).first())continue;
   } else {
    const parts=o.key.split('/');if(!/^[a-f0-9-]{36}$/.test(parts[2]||''))continue;
    const storage=parts.slice(0,3).join('/')+'/';
    if(await stmt(db,'SELECT publication_key FROM publications WHERE storage_prefix=?',storage).first())continue;
    const job=await stmt(db,'SELECT * FROM upload_jobs WHERE storage_prefix=?',storage).first();
    if(job && (Date.parse(job.created_at)>cutoff||job.expires_at>now))continue;
    if(b.apply&&job) {
     const claimed=await stmt(db,"UPDATE upload_jobs SET state='deleting' WHERE storage_prefix=? AND expires_at<=? AND NOT EXISTS(SELECT 1 FROM publications WHERE storage_prefix=?)",storage,now,storage).run();
     if(claimed.meta.changes!==1)continue;
    }
   }
   eligible++;
   if(b.apply){await env.BUCKET.delete(o.key);deleted++;}
  }
  // Empty abandoned jobs are also disposable, even if a failed upload wrote no object.
  if(b.apply) {
   const jobs=await stmt(db,'SELECT * FROM upload_jobs WHERE project_key=? AND created_at<=? AND expires_at<=? LIMIT 100',b.project_key,new Date(cutoff).toISOString(),now).all();
   for(const job of jobs.results) {
    if(await stmt(db,'SELECT publication_key FROM publications WHERE storage_prefix=?',job.storage_prefix).first())continue;
    await stmt(db,"UPDATE upload_jobs SET state='deleting' WHERE storage_prefix=? AND expires_at<=?",job.storage_prefix,now).run();
    if(!(await env.BUCKET.list({prefix:job.storage_prefix,limit:1})).objects.length)
     await stmt(db,'DELETE FROM upload_jobs WHERE storage_prefix=?',job.storage_prefix).run();
   }
  }
  return reply({status:b.apply?'swept':'planned',eligible,deleted,next:page.truncated?page.cursor:null,phase:b.phase});
 }
 fail(404,'Cleanup route not found');
}
