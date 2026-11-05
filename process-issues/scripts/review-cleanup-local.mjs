import {readdir,lstat,readFile,writeFile,realpath,unlink,rmdir} from 'node:fs/promises';
import path from 'node:path';
export const OWNER_FILE='.review-evidence-owner.json';
const valid=k=>typeof k==='string'&&/^[a-z0-9.-]+:[1-9][0-9]*:[1-9][0-9]*$/.test(k);
const check=(ok,message)=>{if(!ok)throw Error(message);};
async function owner(dir) {
 try {const f=path.join(dir,OWNER_FILE);check(!(await lstat(f)).isSymbolicLink(),'Ownership marker is a link');return JSON.parse(await readFile(f,'utf8'));}
 catch(e){if(e.code==='ENOENT')return null;throw e;}
}
export async function markEvidenceDirectory(directory,prKey) {
 check(valid(prKey),'Invalid evidence owner');
 const prior=await owner(directory);
 if(prior){check(prior.schema_version===1&&prior.pr_key===prKey,'Evidence folder belongs to another PR');return;}
 await writeFile(path.join(directory,OWNER_FILE),JSON.stringify({schema_version:1,pr_key:prKey})+'\n',{flag:'wx'});
}
export async function assertEvidenceDirectory(root,directory) {
 const base=await realpath(root),target=path.resolve(directory);
 check(target.startsWith(base+path.sep),'Evidence folder must be strictly inside configured storage');
 let at=base;
 for(const part of path.relative(base,target).split(path.sep)) {
  at=path.join(at,part);
  check(!(await lstat(at)).isSymbolicLink(),'Linked evidence paths cannot be deleted');
 }
 check(await realpath(target)===target,'Evidence path resolves elsewhere');
 return target;
}
export async function discoverLocalEvidence(root) {
 const base=await realpath(root),found=[];let entries=0;
 const walk=async(dir,depth)=>{
  check(depth<=12 && ++entries<=20000,'Evidence discovery limit reached');
  for(const e of await readdir(dir,{withFileTypes:true})) {
   const f=path.join(dir,e.name),s=await lstat(f);
   if(s.isSymbolicLink())continue;
   if(s.isDirectory()) {
    const o=await owner(f);
    if(o){check(o.schema_version===1&&valid(o.pr_key),'Invalid ownership marker');found.push({pr_key:o.pr_key,directory:f});}
    else await walk(f,depth+1);
   }
  }
 };
 await walk(base,0);return found;
}
export async function removeLocalEvidence(root,directory,prKey,{apply=false,resumeEmpty=false}={}) {
 check(valid(prKey),'Invalid PR identity');
 const dir=await assertEvidenceDirectory(root,directory),o=await owner(dir);
 if(!o&&resumeEmpty&&(await readdir(dir)).length===0) {
  if(apply)await rmdir(dir);
  return {status:apply?'complete':'planned',files:0};
 }
 check(o?.schema_version===1&&o.pr_key===prKey,'Exact PR ownership marker required');
 const files=[],dirs=[];
 const inspect=async(folder)=>{
  for(const e of await readdir(folder,{withFileTypes:true})) {
   const f=path.join(folder,e.name),s=await lstat(f);
   check(!s.isSymbolicLink(),'Linked evidence files cannot be deleted');
   if(s.isDirectory()){
    const nested=await owner(f);check(!nested||nested.pr_key===prKey,'Nested evidence belongs to another PR');
    await inspect(f);dirs.push(f);
   } else {check(s.isFile(),'Unsupported evidence entry');if(f!==path.join(dir,OWNER_FILE))files.push(f);}
  }
 };
 await inspect(dir);
 if(!apply)return {status:'planned',files:files.length+1};
 // The entire resolved tree was checked before deleting anything. Recheck each
 // parent/leaf; keep the root marker until last so a partial failure is resumable.
 for(const f of files) {
  if(path.dirname(f)!==dir)await assertEvidenceDirectory(root,path.dirname(f));
  check(!(await lstat(f)).isSymbolicLink(),'Evidence changed during cleanup');
  await unlink(f);
 }
 for(const d of dirs){await assertEvidenceDirectory(root,d);await rmdir(d);}
 await assertEvidenceDirectory(root,dir);await unlink(path.join(dir,OWNER_FILE));await rmdir(dir);
 return {status:'complete',files:files.length+1};
}

export async function findPublicationReceipts(root) {
 const directory=path.join(root,'receipts'),found=[];
 let entries;
 try{check(!(await lstat(directory)).isSymbolicLink(),'Linked publisher receipts');entries=await readdir(directory);}
 catch(e){if(e.code==='ENOENT')return found;throw e;}
 for(const name of entries) {
  if(!/^[a-f0-9]{64}\.json(?:\.[a-f0-9-]{36}\.tmp)?$/.test(name))continue;
  const file=path.join(directory,name),s=await lstat(file);
  check(s.isFile()&&!s.isSymbolicLink()&&s.size<=1024*1024,'Invalid publisher receipt');
  let r;try{r=JSON.parse(await readFile(file,'utf8'));}catch{continue;}
  const key=r.publication_key;
  if(typeof key!=='string'||!/^[a-z0-9.-]+:[1-9][0-9]*:[1-9][0-9]*:[a-f0-9]{40}:[a-f0-9]{64}$/.test(key)||!name.startsWith(key.split(':').at(-1)+'.json'))continue;
  found.push({file,pr_key:key.split(':').slice(0,3).join(':')});
 }
 return found;
}
export async function removePublicationReceipt(root,file,prKey) {
 const expected=(await findPublicationReceipts(root)).find(r=>r.file===file&&r.pr_key===prKey);
 check(expected,'Publisher receipt identity changed');
 await assertEvidenceDirectory(root,path.dirname(file));
 check(!(await lstat(file)).isSymbolicLink(),'Linked publisher receipt');
 await unlink(file);
}
