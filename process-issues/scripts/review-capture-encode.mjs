#!/usr/bin/env node
/** Deterministic local encoding. Does not capture, launch a browser or call a model. */
import {markEvidenceDirectory,OWNER_FILE} from './review-cleanup-local.mjs';
import {readFile,writeFile,mkdir,lstat,realpath} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';

function check(ok,message) {if(!ok) throw new Error(message);}
function run(command,args) {
  const r=spawnSync(command,args,{encoding:'utf8',timeout:120000,maxBuffer:1024*1024,windowsHide:true});
  check(!r.error && r.status===0,command+' failed; retained capture is reusable');
  return r.stdout;
}
export async function encodeCapture(manifestFile,outputDirectory,sourceSha) {
  const capture=JSON.parse(await readFile(manifestFile,'utf8'));
  check(capture.schema_version===1 && capture.source==='codex-browser' && capture.status==='captured','Capture is incomplete or failed');
  check(/^[a-f0-9]{40}$/.test(sourceSha) && capture.source_sha===sourceSha,'Source SHA mismatch');
  check(Number.isInteger(capture.fps) && capture.fps>=1 && capture.fps<=12,'Invalid capture fps');
  check(Array.isArray(capture.frames) && capture.frames.length>=2 && capture.frames.length<=180,'Invalid frame count');
  check(capture.frames.length/capture.fps<=30,'Capture exceeds 30 seconds; shorten the scenario');
  check(Array.isArray(capture.checkpoints) && capture.checkpoints.length<=3,'Invalid checkpoints');
  const directory=await realpath(path.dirname(manifestFile));
  const seen=new Set();
  for (const frame of capture.frames) {
    check(/^frame-\d{5}\.jpg$/.test(frame.file) && !seen.has(frame.file),'Unsafe or duplicate frame');
    seen.add(frame.file);
    const file=path.join(directory,frame.file),stat=await lstat(file);
    check(stat.isFile() && !stat.isSymbolicLink() && stat.size<=8*1024*1024,'Invalid frame file');
    check(path.dirname(await realpath(file))===directory,'Frame escapes capture directory');
    check(createHash('sha256').update(await readFile(file)).digest('hex')===frame.sha256,'Frame hash mismatch');
  }
  for (const c of capture.checkpoints) check(seen.has(c.file),'Unknown checkpoint');
  await mkdir(outputDirectory); // Keep retries explicit and preserve existing output.
  const output=await realpath(outputDirectory);
  try {
    const marker=path.join(directory,OWNER_FILE);
    check(!(await lstat(marker)).isSymbolicLink(),'Linked ownership marker');
    const owner=JSON.parse(await readFile(marker,'utf8'));
    check(owner.schema_version===1,'Invalid ownership marker');
    await markEvidenceDirectory(output,owner.pr_key);
  } catch(e) {if(e.code!=='ENOENT')throw e;}
  const assets=path.join(output,'assets');await mkdir(assets);
  const quote=s=>"'"+s.replaceAll('\\','/').replaceAll("'","'\\''")+"'";
  const rows=['ffconcat version 1.0'];
  for(const frame of capture.frames) rows.push('file '+quote(path.join(directory,frame.file)),'duration '+(1/capture.fps));
  rows.push('file '+quote(path.join(directory,capture.frames.at(-1).file)));
  const listing=path.join(output,'frames.ffconcat');await writeFile(listing,rows.join('\n')+'\n');
  const video=path.join(assets,'navigation.mp4');
  run('ffmpeg',['-v','error','-nostdin','-f','concat','-safe','0','-i',listing,
    '-vf','scale=1280:900:force_original_aspect_ratio=decrease:in_range=full:out_range=limited,pad=1280:900:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p',
    '-r','30','-c:v','libx264','-preset','medium','-crf','20','-color_range','tv',
    '-an','-movflags','+faststart',video]);
  const descriptors=[];
  const describe=async(file,role)=>{
    const probe=JSON.parse(run('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',file]));
    const s=probe.streams[0],isVideo=role==='demonstration';
    check(probe.streams.length===1 && s.codec_type==='video','Unexpected media streams');
    check(s.codec_name===(isVideo?'h264':'png'),'Unexpected codec');
    if(isVideo) check(s.pix_fmt==='yuv420p' && Number(s.nb_read_frames)>=2 && Number(probe.format.duration)>=1 && Number(probe.format.duration)<=30,'Invalid video');
    run('ffmpeg',['-v','error','-xerror','-nostdin','-i',file,'-map','0:v:0','-f','null','-']);
    const bytes=await readFile(file);check(bytes.length<=8*1024*1024,'Encoded asset exceeds 8 MiB');
    descriptors.push({id:path.parse(file).name,filename:path.basename(file),role,
      mime:isVideo?'video/mp4':'image/png',bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex'),
      width:s.width,height:s.height,duration_ms:isVideo?Math.round(Number(probe.format.duration)*1000):null,
      codec:isVideo?'h264':null,caption:isVideo?'Real Codex browser frames in interaction order; idle gaps omitted.':'Codex browser checkpoint'});
  };
  await describe(video,'demonstration');
  for(const [i,c] of capture.checkpoints.entries()) {
    const file=path.join(assets,'checkpoint-'+(i+1)+'.png');
    run('ffmpeg',['-v','error','-nostdin','-i',path.join(directory,c.file),'-frames:v','1',file]);
    await describe(file,'screenshot');
  }
  const result={source_sha:sourceSha,source:'codex-browser',timing:capture.timing,
    assets:descriptors,behavior_review:'not verified by encoder'};
  await writeFile(path.join(output,'assets.json'),JSON.stringify(result,null,2)+'\n');
  return result;
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try {
    check(process.argv.length===5,'Usage: review-capture-encode.mjs CAPTURE_JSON NEW_OUTPUT_DIRECTORY SOURCE_SHA');
    console.log(JSON.stringify(await encodeCapture(...process.argv.slice(2)),null,2));
  } catch(e) {console.error(e.message);process.exitCode=1;}
}
