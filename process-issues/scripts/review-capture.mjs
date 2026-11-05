/** Run inside Codex's browser REPL with the already selected built-in tab.
 * No browser launch, model calls, navigation decisions or automatic visual approval.
 */
import {mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {setTimeout as delay} from 'node:timers/promises';

export async function createCapture({directory, sourceSha, fps=6, maxFrames=120,
  checkpointLimit=3, framesPerStep=12}) {
  if (!path.isAbsolute(directory) || !/^[a-f0-9]{40}$/.test(sourceSha))
    throw new Error('Absolute local output directory and full source SHA required');
  for (const [value,min,max] of [[fps,1,12],[maxFrames,2,180],[checkpointLimit,1,3],[framesPerStep,2,36]])
    if (!Number.isInteger(value) || value<min || value>max) throw new Error('Invalid capture budget');
  await mkdir(directory); // Exclusive run directory: never overwrite a previous capture.
  const manifest={schema_version:1,source:'codex-browser',source_sha:sourceSha,
    started_at:new Date().toISOString(),fps,frames:[],steps:[],checkpoints:[],
    status:'recording',timing:'Ordered browser frames at fixed fps; idle gaps omitted; no interpolation'};
  let active=false, closed=false;
  const persist=()=>writeFile(path.join(directory,'capture.json'),JSON.stringify(manifest,null,2)+'\n');
  const shot=async(tab,step)=>{
    const bytes=await tab.screenshot({fullPage:false});
    if (!(bytes instanceof Uint8Array) || bytes[0]!==255 || bytes[1]!==216)
      throw new Error('Expected a built-in browser JPEG screenshot');
    const file='frame-'+String(manifest.frames.length).padStart(5,'0')+'.jpg';
    await writeFile(path.join(directory,file),bytes,{flag:'wx'});
    const frame={file,step,at:new Date().toISOString(),
      sha256:createHash('sha256').update(bytes).digest('hex')};
    manifest.frames.push(frame);
    return frame;
  };
  await persist();
  return {
    async step({tab,name,action,checkpoint=false}) {
      if (closed || active) throw new Error('Capture is closed or a step is already running');
      if (!tab?.screenshot || typeof action!=='function' || !/^[a-z0-9][a-z0-9-]{0,63}$/.test(name))
        throw new Error('Pass the selected Codex tab, a short step name and an existing verification action');
      if (manifest.steps.some(s=>s.name===name)) throw new Error('Step names must be unique');
      if (checkpoint && manifest.checkpoints.length>=checkpointLimit)
        throw new Error('Checkpoint budget reached; reuse inspected checkpoints');
      if (maxFrames-manifest.frames.length<2) {
        manifest.status='budget-exhausted';closed=true;await persist();
        throw new Error('Capture frame budget reached; continue verification separately');
      }
      active=true;
      const step={name,status:'running',first_frame:manifest.frames.length,sampling_truncated:false};
      manifest.steps.push(step);
      let actionFailed=false, captureFailed=false, settled=false, count=0;
      const limit=Math.min(framesPerStep,maxFrames-manifest.frames.length);
      try {
        await shot(tab,name);count++;
        // Call action exactly once. Even when sampling fails, wait for it to settle.
        const work=Promise.resolve().then(action).catch(()=>{actionFailed=true;}).finally(()=>{settled=true;});
        const sample=(async()=>{
          while ((!settled || count<Math.min(fps,limit-1)) && count<limit-1) {
            await delay(1000/fps);
            if (settled && count>=Math.min(fps,limit-1)) break;
            await shot(tab,name);count++;
          }
          step.sampling_truncated=!settled && count>=limit-1;
        })().catch(()=>{captureFailed=true;});
        await Promise.all([work,sample]);
        if (captureFailed) throw new Error('Screenshot sampling failed');
        const last=await shot(tab,name);
        step.last_frame=manifest.frames.length-1;
        step.status=actionFailed?'failed':'captured';
        if (checkpoint || actionFailed)
          manifest.checkpoints.push({file:last.file,step:name,reason:actionFailed?'failure':'requested'});
        if (actionFailed) {manifest.status='failed';closed=true;}
        await persist();
        return {step:name,status:step.status,frames:step.last_frame-step.first_frame+1,
          sampling_truncated:step.sampling_truncated,
          checkpoint:checkpoint||actionFailed?path.join(directory,last.file):null};
      } catch {
        step.status='capture-failed';manifest.status='failed';closed=true;
        await persist();
        throw new Error('Capture failed; inspect the current browser state and retained capture.json');
      } finally {active=false;}
    },
    async finish() {
      if (active) throw new Error('Wait for the active step before finalizing');
      if (!closed) {manifest.status=manifest.frames.length>=2?'captured':'incomplete';closed=true;}
      manifest.finished_at ??= new Date().toISOString();
      await persist();
      return {status:manifest.status,manifest:path.join(directory,'capture.json'),
        frames:manifest.frames.length,checkpoints:manifest.checkpoints.map(c=>path.join(directory,c.file)),
        behavior_review:'not verified by capture helper'};
    }
  };
}
