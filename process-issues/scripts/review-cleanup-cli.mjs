#!/usr/bin/env node
import {readFile,writeFile,mkdir,realpath,readdir,lstat,rename} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {loadConfig,inspectConfig} from './review-bundle-cli.mjs';
import {secretInput} from './review-publish-cli.mjs';
import {cleanupEvidence} from './review-cleanup.mjs';
import {discoverLocalEvidence,markEvidenceDirectory,removeLocalEvidence,assertEvidenceDirectory,findPublicationReceipts,removePublicationReceipt} from './review-cleanup-local.mjs';
const check=(ok,message)=>{if(!ok)throw Error(message);};
function gh(args,cwd) {
 const r=spawnSync('gh',args,{cwd,encoding:'utf8',timeout:30000,maxBuffer:4*1024*1024,windowsHide:true});
 check(!r.error&&r.status===0,'GitHub read failed; inspect authentication/network separately');return JSON.parse(r.stdout);
}
async function main() {
 const [mode,configFile,repoRoot,...rest]=process.argv.slice(2);
 check(['register','run'].includes(mode)&&configFile&&repoRoot,'Usage: review-cleanup-cli.mjs register CONFIG REPO PR DIRECTORY | run CONFIG REPO [--apply]');
 const c=await loadConfig(configFile);
 if(!c.enabled||!c.cleanup?.merged_prs)return {status:'disabled',site_mutations:0};
 await inspectConfig(configFile,repoRoot);
 const root=await realpath(repoRoot),output=await realpath(path.join(root,c.output_directory)),project=c.repository.host+':'+c.repository.id;
 if(mode==='register') {
  check(rest.length===2&&/^[1-9][0-9]*$/.test(rest[0]),'PR number and dedicated evidence directory required');
  const folder=await realpath(rest[1]);await assertEvidenceDirectory(output,folder);
  await inspectConfig(configFile,root,[path.join(folder,'.review-evidence-owner.json')]);
  await markEvidenceDirectory(folder,project+':'+rest[0]);
  await removeLocalEvidence(output,folder,project+':'+rest[0]); // read-only tree safety check
  return {status:'registered',pr_key:project+':'+rest[0]};
 }
 check(rest.length===0||rest.length===1&&rest[0]==='--apply','Only --apply is supported');
 const apply=rest[0]==='--apply',folders=await discoverLocalEvidence(output),pending=new Map();
 const publicationReceipts=await findPublicationReceipts(output);
 const receipts=path.join(output,'cleanup-receipts'),sweepFile=path.join(receipts,'sweep.json');
 try {
  check(!(await lstat(receipts)).isSymbolicLink(),'Cleanup receipt directory cannot be linked');
  for(const entry of await readdir(receipts)) {
   if(!/^[a-f0-9]{64}\.json$/.test(entry))continue;
   const f=path.join(receipts,entry);check(!(await lstat(f)).isSymbolicLink(),'Cleanup receipt cannot be linked');
   const r=JSON.parse(await readFile(f,'utf8'));
   if(r.status==='pending')pending.set(r.pr_key,r.directories);
  }
 } catch(e){if(e.code!=='ENOENT')throw e;}
 let sweepState={};
 try {check(!(await lstat(sweepFile)).isSymbolicLink(),'Sweep receipt cannot be linked');sweepState=JSON.parse(await readFile(sweepFile,'utf8'));}
 catch(e){if(e.code!=='ENOENT')throw e;}
 const repo=gh(['repo','view','--json','nameWithOwner,url'],root);
 const identity=gh(['api','--hostname',c.repository.host,'repos/'+repo.nameWithOwner],root);
 check(identity.id===c.repository.id&&identity.html_url===repo.url&&new URL(repo.url).hostname===c.repository.host,'Configured repository does not match checkout');
 const observe=async(pr)=>{
  const number=pr.split(':').at(-1),p=gh(['api','--hostname',c.repository.host,'repos/'+repo.nameWithOwner+'/pulls/'+number],root);
  check(p.number===Number(number)&&p.base.repo.id===c.repository.id,'GitHub PR repository mismatch');
  return {pr_key:pr,state:p.merged_at?'merged':p.state,merged_at:p.merged_at,checked_at:new Date().toISOString()};
 };
 const cleanLocal=async(pr,doApply)=>{
  const dirs=[...new Set([...folders.filter(f=>f.pr_key===pr).map(f=>path.relative(output,f.directory)),...(pending.get(pr)||[])])];
  const target=path.join(receipts,createHash('sha256').update(pr).digest('hex')+'.json');
  await inspectConfig(configFile,root,[target,...dirs.map(d=>path.resolve(output,d))]);
  const save=async(value)=>{
   await mkdir(receipts,{recursive:true});check(!(await lstat(receipts)).isSymbolicLink(),'Linked cleanup receipt directory');
   try{check(!(await lstat(target)).isSymbolicLink(),'Linked cleanup receipt');}catch(e){if(e.code!=='ENOENT')throw e;}
   const temp=target+'.'+crypto.randomUUID()+'.tmp';
   await writeFile(temp,JSON.stringify(value)+'\n',{flag:'wx'});await rename(temp,target);
  };
  if(doApply)await save({schema_version:1,pr_key:pr,status:'pending',directories:dirs});
  let files=0;
  for(const d of dirs) {
   const folder=path.resolve(output,d);
   try {await lstat(folder);}catch(e){if(e.code==='ENOENT')continue;throw e;}
   const result=await removeLocalEvidence(output,folder,pr,{apply:doApply,resumeEmpty:pending.has(pr)});
   files+=result.files;
  }
  for(const r of publicationReceipts.filter(r=>r.pr_key===pr)){
   await inspectConfig(configFile,root,[r.file]);
   if(doApply)await removePublicationReceipt(output,r.file,pr);
   files++;
  }
  if(doApply)await save({schema_version:1,pr_key:pr,status:'complete',completed_at:new Date().toISOString()});
  return {status:doApply?'complete':'planned',directories:dirs.length,files};
 };
 const input=await secretInput();
 if(input.native_site&&!input.native_site.siwc_bypass_bearer_token)input.native_site.siwc_bypass_bearer_token=process.env[c.auth.service_token_env];
 const result=await cleanupEvidence({config:c,site:input.native_site,metadataReadAt:input.metadata_read_at,
  publisherKey:input.publisher_key||process.env[c.auth.publisher_key_env],observe,apply,
  localPrKeys:[...folders.map(f=>f.pr_key),...publicationReceipts.map(r=>r.pr_key),...pending.keys()].filter(k=>k.startsWith(project+':')),cleanLocal,sweepState});
 if(apply){
  await inspectConfig(configFile,root,[sweepFile]);await mkdir(receipts,{recursive:true});
  check(!(await lstat(receipts)).isSymbolicLink(),'Linked cleanup receipt directory');
  try{check(!(await lstat(sweepFile)).isSymbolicLink(),'Linked sweep receipt');}catch(e){if(e.code!=='ENOENT')throw e;}
  const temp=sweepFile+'.'+crypto.randomUUID()+'.tmp';await writeFile(temp,JSON.stringify(result.sweep_state)+'\n',{flag:'wx'});await rename(temp,sweepFile);
 }
 return result;
}
try{console.log(JSON.stringify(await main(),null,2));}
catch(e){console.error(JSON.stringify({ok:false,error:e.code?'Cleanup input/storage operation failed; retained receipts support retry':e.message}));process.exitCode=1;}
