import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {spawnSync} from 'node:child_process';
import {createCapture} from '../scripts/review-capture.mjs';
import {encodeCapture} from '../scripts/review-capture-encode.mjs';

const sha='a'.repeat(40),jpeg=Uint8Array.from([255,216,255,217]);
const root=await mkdtemp(path.join(tmpdir(),'review-capture-test-'));
let serial=0;
const folder=()=>path.join(root,String(serial++));
const tab={screenshot:async()=>jpeg};
test('actions run once; distinct steps preserve order and bounded checkpoints',async()=>{
  const dir=folder(),c=await createCapture({directory:dir,sourceSha:sha,fps:12,framesPerStep:2});
  let actions=0;
  await c.step({tab,name:'desktop',checkpoint:true,action:async()=>{actions++;}});
  await c.step({tab,name:'mobile',checkpoint:true,action:async()=>{actions++;}});
  const result=await c.finish(),m=JSON.parse(await readFile(result.manifest));
  assert.equal(actions,2);assert.equal(result.status,'captured');
  assert.deepEqual(m.frames.map(f=>f.step),['desktop','desktop','mobile','mobile']);
  assert.deepEqual(m.checkpoints.map(c=>c.step),['desktop','mobile']);
  assert.equal(result.behavior_review,'not verified by capture helper');
  await assert.rejects(c.step({tab,name:'again',action:async()=>{}}),/closed/);
  await assert.rejects(createCapture({directory:dir,sourceSha:sha}),/EEXIST/);
});
test('failed action retains a failure checkpoint and refuses further capture',async()=>{
  const c=await createCapture({directory:folder(),sourceSha:sha,framesPerStep:2});
  const result=await c.step({tab,name:'broken',action:async()=>{throw new Error('private failure detail');}});
  assert.equal(result.status,'failed');assert.ok(result.checkpoint);
  const end=await c.finish(),text=await readFile(end.manifest,'utf8');
  assert.equal(end.status,'failed');assert.ok(!text.includes('private failure detail'));
  await assert.rejects(c.step({tab,name:'later',action:async()=>{}}),/closed/);
  await assert.rejects(encodeCapture(end.manifest,folder(),sha),/incomplete or failed/);
});
test('frame and checkpoint limits prevent additional actions',async()=>{
  const c=await createCapture({directory:folder(),sourceSha:sha,maxFrames:2,checkpointLimit:1,framesPerStep:2});
  await c.step({tab,name:'one',checkpoint:true,action:async()=>{}});
  let invoked=false;
  await assert.rejects(c.step({tab,name:'two',checkpoint:true,action:async()=>{invoked=true;}}),/Checkpoint budget/);
  await assert.rejects(c.step({tab,name:'two',action:async()=>{invoked=true;}}),/frame budget/);
  assert.equal(invoked,false);assert.equal((await c.finish()).status,'budget-exhausted');
});
test('sampling is bounded, overlapping steps rejected, active action awaited',async()=>{
  const c=await createCapture({directory:folder(),sourceSha:sha,fps:12,framesPerStep:3});
  let done=false;
  const step=c.step({tab,name:'slow',action:async()=>{await delay(250);done=true;}});
  await assert.rejects(c.step({tab,name:'overlap',action:async()=>{}}),/already running/);
  await assert.rejects(c.finish(),/active step/);
  const result=await step;
  assert.equal(done,true);assert.equal(result.frames,3);assert.equal(result.sampling_truncated,true);
});
test('screenshot failure preserves failed state without retrying the action',async()=>{
  let shots=0,actions=0;
  const broken={screenshot:async()=>{if(shots++)throw new Error('screen failed');return jpeg;}};
  const c=await createCapture({directory:folder(),sourceSha:sha,fps:12,framesPerStep:3});
  await assert.rejects(c.step({tab:broken,name:'failure',action:async()=>{actions++;await delay(200);}}),/Capture failed/);
  assert.equal(actions,1);assert.equal((await c.finish()).status,'failed');
});
test('encode genuine-format synthetic frames, normalize changing widths, reject tampering and stale SHA',async()=>{
  const desktop=path.join(root,'synthetic-desktop.jpg'),mobile=path.join(root,'synthetic-mobile.jpg');
  for(const [file,size,color] of [[desktop,'640x360','blue'],[mobile,'390x844','red']]) {
    const r=spawnSync('ffmpeg',['-v','error','-f','lavfi','-i','color=c='+color+':s='+size,'-frames:v','1',file]);
    assert.equal(r.status,0,String(r.stderr));
  }
  const dir=folder(),c=await createCapture({directory:dir,sourceSha:sha,fps:2,framesPerStep:2});
  for(const [name,file] of [['desktop',desktop],['mobile',mobile]])
    await c.step({tab:{screenshot:async()=>new Uint8Array(await readFile(file))},name,checkpoint:true,action:async()=>{}});
  const result=await c.finish();
  await assert.rejects(encodeCapture(result.manifest,folder(),'b'.repeat(40)),/SHA mismatch/);
  const encoded=await encodeCapture(result.manifest,folder(),sha);
  assert.equal(encoded.assets.length,3);
  assert.equal(encoded.assets[0].codec,'h264');assert.equal(encoded.assets[0].width,1280);
  assert.equal(encoded.assets[2].width,390);
  assert.equal(encoded.behavior_review,'not verified by encoder');
  await writeFile(path.join(dir,'frame-00000.jpg'),jpeg);
  await assert.rejects(encodeCapture(result.manifest,folder(),sha),/hash mismatch/);
});

test('falsy promise rejections still fail capture',async()=>{
  const c=await createCapture({directory:folder(),sourceSha:sha,framesPerStep:2});
  const step=await c.step({tab,name:'rejected',action:()=>Promise.reject(undefined)});
  assert.equal(step.status,'failed');assert.equal((await c.finish()).status,'failed');
});
