import test from 'node:test';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,mkdir,rm,lstat} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {publicationKey,validateManifest,validateAssetBytes,validateConfig,digest,identities,canonical} from '../scripts/review-bundle.mjs';
import {loadConfig,validateLocalBundle,inspectConfig} from '../scripts/review-bundle-cli.mjs';

import {fixture} from './fixtures/review-bundles.mjs';
async function seal(m) {m.publication.key=await publicationKey(m);return m;}
test('valid nonvisual manifest, immutable identities and explicit freshness',async()=>{
  const m=await fixture();assert.equal((await validateManifest(m)).freshness,'matches observed head');
  const original=m.publication.key;m.observed_github.head_sha='c'.repeat(40);
  assert.equal((await validateManifest(m)).freshness,'stale');assert.equal(await publicationKey(m),original);
  m.observed_github.head_sha=null;assert.equal((await validateManifest(m)).freshness,'unknown');
});
test('retry key excludes mutable observation, CAS and preparation time',async()=>{
  const m=await fixture(),key=m.publication.key;
  m.publication.expected_current_version=9;m.publication.prepared_at='2026-02-01T00:00:00Z';
  m.observed_github.checks='failed';m.observed_github.draft=false;
  assert.equal(await publicationKey(m),key);await validateManifest(m);
  m.revision.captured_at='2026-01-02T00:00:00Z';assert.notEqual(await publicationKey(m),key);
});
test('stable numeric repository identity survives rename and scopes PR numbers',async()=>{
  const m=await fixture(),before=identities(m);m.repository.name='renamed';
  assert.deepEqual(identities(m),before);m.repository.id=102;assert.notEqual(identities(m).pr_key,before.pr_key);
});
test('canonical encoding is deterministic and rejects non-JSON numeric values',()=>{
  assert.equal(canonical({z:1,a:{z:2,a:'é'}}),canonical({a:{a:'é',z:2},z:1}));
  for(const bad of [NaN,Infinity,1.5,undefined]) assert.throws(()=>canonical(bad));
});
for(const [label,change] of [
  ['version',m=>m.schema_version=2],['missing field',m=>delete m.summary],
  ['secret field',m=>m.publication.token='unexpected'],['short SHA',m=>m.revision.head_sha='abc'],
  ['dirty source',m=>m.revision.clean_source=false],['wrong PR URL',m=>m.pull_request.url='https://evil.example/pull/7'],
  ['invalid date',m=>m.revision.captured_at='2026-02-30T00:00:00Z'],
  ['path exposure',m=>m.summary.changed='Read C:\\Users\\person\\private.txt'],
  ['failed verified evidence',m=>m.acceptance[0].automated[0].result='failed'],
  ['false UI exemption',m=>m.demonstration.kind='ui'],
  ['stale build',m=>{m.demonstration.kind='ui';m.demonstration.state='verified';m.revision.build_sha='d'.repeat(40);}],
  ['cross-repo base',m=>m.pull_request.base.repository={...m.repository,id:999}],
  ['observation draft type',m=>m.observed_github.draft='false']]) {
  test('rejects '+label,async()=>{const m=await fixture();change(m);await assert.rejects(async()=>{await seal(m);await validateManifest(m);});});
}
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aC9sAAAAASUVORK5CYII=','base64');
async function imageAsset(){return {id:'after',role:'after',filename:'after.png',mime:'image/png',bytes:png.length,sha256:await digest(png),caption:'Synthetic one-pixel PNG, not implementation proof',width:1,height:1,duration_ms:null,codec:null};}
test('byte/hash/type/dimension and truncated image checks',async()=>{
  const a=await imageAsset();await validateAssetBytes(a,png);
  await assert.rejects(validateAssetBytes(a,png.subarray(0,40)));
  await assert.rejects(validateAssetBytes({...a,width:2},png));
  const bad=Buffer.from(png);bad[20]^=1;await assert.rejects(validateAssetBytes(a,bad));
  const truncated=png.subarray(0,png.length-12);
  await assert.rejects(validateAssetBytes({...a,bytes:truncated.length,sha256:await digest(truncated)},truncated));
});
test('asset order does not change publication key; duplicate IDs do not validate',async()=>{
  const m=await fixture(),a=await imageAsset();m.assets=[a,{...a,id:'before',role:'before',filename:'before.png'}];
  const key=await publicationKey(m);m.assets.reverse();assert.equal(await publicationKey(m),key);
  m.assets[0].id=m.assets[1].id;await seal(m);await assert.rejects(validateManifest(m));
});
for(const filename of ['../secret.png','a/b.png','C:\\x.png','CON.png','after.html','file.png:stream']) {
  test('rejects unsafe filename '+filename,async()=>{const m=await fixture();m.assets=[{...await imageAsset(),filename}];await seal(m);await assert.rejects(validateManifest(m));});
}
test('missing/disabled config is read-only and needs no destination',async()=>{
  assert.deepEqual(validateConfig({schema_version:1,enabled:false}),{enabled:false});
  assert.deepEqual(await loadConfig(path.join(tmpdir(),'missing-review-config-'+crypto.randomUUID())),{enabled:false});
  assert.throws(()=>validateConfig({schema_version:2,enabled:false}));
});
test('config rejects credential values, foreign origins, unsafe storage and unknown methods',()=>{
  const c={schema_version:1,enabled:true,required:false,site:{project_id:'synthetic-project',origin:'https://review.example.chatgpt.site'},repository:{host:'github.example',id:101},auth:{method:'sites-service-and-publisher-key',service_token_env:'SITES_SERVICE_TOKEN',publisher_key_env:'REVIEW_PUBLISHER_KEY'},output_directory:'.codex/review-evidence',media:{target_seconds:10,max_file_bytes:1048576,max_bundle_bytes:2097152,ffmpeg:'ffmpeg',ffprobe:'ffprobe'}};
  assert.equal(validateConfig(c).enabled,true);
  for(const change of [x=>x.site.origin='http://review.example.chatgpt.site',x=>x.site.origin='https://review.example.chatgpt.site.evil.example',x=>x.auth.service_token_env='actual-secret-value',x=>x.output_directory='../elsewhere',x=>x.auth.method='invented',x=>x.media.ffmpeg='ffmpeg --extra']) {const bad=structuredClone(c);change(bad);assert.throws(()=>validateConfig(bad));}
});
test('public CLI validates finalized output and refuses unlisted files',async()=>{
  const dir=await mkdtemp(path.join(tmpdir(),'review-bundle-'));
  try {
    const assets=path.join(dir,'assets');await mkdir(assets);
    const m=await fixture(),bytes=Buffer.from('synthetic result: passed\n');
    m.assets=[{id:'output',role:'output',filename:'result.txt',mime:'text/plain',bytes:bytes.length,sha256:await digest(bytes),caption:'Synthetic semantic result',width:null,height:null,duration_ms:null,codec:null}];await seal(m);
    const file=path.join(dir,'manifest.json');await writeFile(file,JSON.stringify(m));await writeFile(path.join(assets,'result.txt'),bytes);
    const cli=new URL('../scripts/review-bundle-cli.mjs',import.meta.url);
    const r=spawnSync(process.execPath,[fileURLToPath(cli), 'validate',file,assets],{encoding:'utf8'});
    assert.equal(r.status,0,r.stderr);const output=JSON.parse(r.stdout);assert.equal(output.integrity,'verified');assert.equal(output.behavior_review,'not verified by this helper');
    await writeFile(path.join(assets,'unlisted.txt'),'unlisted');await assert.rejects(validateLocalBundle(file,assets));
  } finally {await rm(dir,{recursive:true,force:true});}
});

test('full decoder validates real synthetic PNG/MP4 and rejects damaged frames',async()=>{
  const dir=await mkdtemp(path.join(tmpdir(),'review-media-'));
  const generate=(args)=>{const r=spawnSync('ffmpeg',['-v','error','-nostdin',...args],{encoding:'utf8',timeout:60000});assert.equal(r.status,0,'ffmpeg must be installed for required media validation');};
  try {
    const assets=path.join(dir,'assets');await mkdir(assets);
    const image=path.join(assets,'after.png'),video=path.join(assets,'demo.mp4');
    generate(['-f','lavfi','-i','color=c=blue:s=64x64','-frames:v','1',image]);
    generate(['-f','lavfi','-i','testsrc2=s=64x64:r=5','-t','2','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',video]);
    const m=await fixture();m.revision.build_sha=m.revision.head_sha;m.demonstration.kind='ui';m.demonstration.state='verified';m.demonstration.limitation='Synthetic media fixture only';
    m.assets=[];
    for(const [file,id,role,mime,duration_ms,codec] of [[image,'after','after','image/png',null,null],[video,'demo','demonstration','video/mp4',2000,'h264']]){
      const bytes=await readFile(file);m.assets.push({id,role,filename:path.basename(file),mime,bytes:bytes.length,sha256:await digest(bytes),caption:'Synthetic decoder fixture',width:64,height:64,duration_ms,codec});
    }
    await seal(m);const manifest=path.join(dir,'manifest.json');await writeFile(manifest,JSON.stringify(m));
    const validated=await validateLocalBundle(manifest,assets);assert.equal(validated.media_decode,'verified where applicable');
    const integrity=await validateLocalBundle(manifest,assets,{decode:false});assert.equal(integrity.media_decode,'not verified');
    await assert.rejects(validateLocalBundle(manifest,assets,{ffprobe:'nonexistent-review-media-probe'}));
    const damaged=await readFile(image);let at=8;
    while(damaged.toString('ascii',at+4,at+8)!=='IDAT')at+=damaged.readUInt32BE(at)+12;
    damaged[at+8]^=255;await writeFile(image,damaged);m.assets[0].sha256=await digest(damaged);await seal(m);await writeFile(manifest,JSON.stringify(m));
    await assert.rejects(validateLocalBundle(manifest,assets));
  } finally {await rm(dir,{recursive:true,force:true});}
});

test('config inspection enforces ignored, untracked output with no writes',async()=>{
  const root=await mkdtemp(path.join(tmpdir(),'review-config-'));
  const git=(args)=>{const r=spawnSync('git',['-C',root,...args],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);return r.stdout;};
  try {
    git(['init','-b','main']);await mkdir(path.join(root,'.codex'));
    const c=JSON.parse(await readFile(new URL('../assets/review-site.config.example.json',import.meta.url),'utf8'));c.enabled=true;
    const file=path.join(root,'.codex','review-site.local.json');await writeFile(file,JSON.stringify(c));
    await assert.rejects(inspectConfig(file,root));
    await writeFile(path.join(root,'.git','info','exclude'),'.codex/review-site.local.json\n.codex/review-evidence/\n');
    const result=await inspectConfig(file,root);assert.equal(result.enabled,true);assert.equal(result.site_mutations,0);
    await assert.rejects(lstat(path.join(root,'.codex','review-evidence')),{code:'ENOENT'});
    git(['add','-f','.codex/review-site.local.json']);await assert.rejects(inspectConfig(file,root));
  } finally {await rm(root,{recursive:true,force:true});}
});
