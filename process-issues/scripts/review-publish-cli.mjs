#!/usr/bin/env node
import {readFile,mkdir,writeFile,rename,realpath,lstat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {loadConfig,inspectConfig,validateLocalBundle} from './review-bundle-cli.mjs';
import {OWNER_FILE} from './review-cleanup-local.mjs';
import {publishReview} from './review-publish.mjs';
function check(ok,message){if(!ok)throw Error(message);}
function gh(args){const r=spawnSync('gh',args,{encoding:'utf8',timeout:30000,maxBuffer:2*1024*1024,windowsHide:true});check(!r.error&&r.status===0,'GitHub read failed; inspect gh authentication/network separately');try{return JSON.parse(r.stdout);}catch{throw Error('Invalid GitHub response');}}
export async function secretInput(){
 if(process.stdin.isTTY){process.stdin.setRawMode(true);process.stderr.write('Ready for native Site metadata and publisher credentials (input hidden).\n');}
 process.stdin.setEncoding('utf8');
 return new Promise((resolve,reject)=>{let s='';const cleanup=()=>{process.stdin.removeListener('data',onData);process.stdin.removeListener('end',onEnd);if(process.stdin.isTTY)process.stdin.setRawMode(false);process.stdin.pause();};
 const finish=()=>{cleanup();try{resolve(JSON.parse(s.trim()));}catch{reject(Error('Invalid secure stdin JSON'));}};
 const onData=c=>{s+=c;if(s.length>128*1024||c.includes('\u0003')){cleanup();reject(Error('Input cancelled or too large'));}else if(/[\r\n]/.test(s))finish();};
 const onEnd=()=>finish();process.stdin.on('data',onData);process.stdin.once('end',onEnd);process.stdin.resume();});
}
async function main(){
 const [configFile,repoRoot,manifestFile,assetDir,...extra]=process.argv.slice(2);check(configFile&&repoRoot&&manifestFile&&assetDir&&!extra.length,'Usage: review-publish-cli.mjs CONFIG REPO_ROOT MANIFEST ASSET_DIR');
 const c=await loadConfig(configFile);if(!c.enabled)return {status:'disabled',site_mutations:0};
 await inspectConfig(configFile,repoRoot);
 const root=await realpath(repoRoot),output=path.join(root,c.output_directory),mf=await realpath(manifestFile),ad=await realpath(assetDir);
 check(mf.startsWith(output+path.sep)&&ad.startsWith(output+path.sep),'Evidence must be in configured ignored handoff storage');
 await validateLocalBundle(mf,ad,{ffmpeg:c.media.ffmpeg,ffprobe:c.media.ffprobe});
 const m=JSON.parse(await readFile(mf,'utf8')),assets=new Map();for(const a of m.assets)assets.set(a.id,new Uint8Array(await readFile(path.join(ad,a.filename))));
 if(c.cleanup?.merged_prs){
  const bundleDirectory=path.dirname(mf);
  check(bundleDirectory!==output&&ad.startsWith(bundleDirectory+path.sep),'Cleanup needs a dedicated PR bundle folder');
  const marker=path.join(bundleDirectory,OWNER_FILE);
  check(!(await lstat(marker)).isSymbolicLink(),'Linked evidence ownership marker');
  const owner=JSON.parse(await readFile(marker,'utf8'));
  check(owner.schema_version===1&&owner.pr_key===m.repository.host+':'+m.repository.id+':'+m.pull_request.number,'Register this bundle for exact PR cleanup before publishing');
 }
 const folder=path.join(output,'receipts');
 const target=path.join(folder,m.publication.key.split(':').at(-1)+'.json'),temp=target+'.'+crypto.randomUUID()+'.tmp';
 const evidencePaths=[mf,...m.assets.map(a=>path.join(ad,a.filename)),target,temp];
 await inspectConfig(configFile,root,evidencePaths);
 const observe=async()=>{
  const repo=m.repository.owner+'/'+m.repository.name;
  const r=gh(['api','--hostname',m.repository.host,'repos/'+repo]);
  check(r.id===m.repository.id&&r.html_url===m.repository.url,'GitHub repository identity changed');
  const p=gh(['api','--hostname',m.repository.host,'repos/'+repo+'/pulls/'+m.pull_request.number]);
  check(p.number===m.pull_request.number&&p.html_url===m.pull_request.url&&p.base.repo.id===m.pull_request.base.repository.id&&p.head.repo?.id===m.pull_request.head.repository.id&&p.base.ref===m.pull_request.base.ref&&p.head.ref===m.pull_request.head.ref,'PR scope/head/base identity changed');
  return {head_sha:p.head.sha,state:p.merged_at?'merged':p.state,draft:p.draft,observed_at:new Date().toISOString(),checks:'unknown (see GitHub)',reviews:'unknown (see GitHub)'};
 };
 const input=await secretInput();
 if(input.native_site && !input.native_site.siwc_bypass_bearer_token) input.native_site.siwc_bypass_bearer_token=process.env[c.auth.service_token_env];
 const receipt=await publishReview({config:c,manifest:m,assets,site:input.native_site,metadataReadAt:input.metadata_read_at,publisherKey:input.publisher_key||process.env[c.auth.publisher_key_env],observe});
 // Recheck before persisting: ignore rules may have changed during publication.
 await inspectConfig(configFile,root,evidencePaths);
 await mkdir(folder,{recursive:true});
 await writeFile(temp,JSON.stringify(receipt,null,2),{flag:'wx'});await rename(temp,target);
 return receipt;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
try{console.log(JSON.stringify(await main(),null,2));}catch(e){console.error(JSON.stringify({ok:false,error:e.code||e instanceof SyntaxError?'Local input unavailable or invalid':e.message}));process.exitCode=1;}
}
