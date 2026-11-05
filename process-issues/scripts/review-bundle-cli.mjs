#!/usr/bin/env node
/** Local-only evidence validation. No Site calls, credentials, or Git mutations. */
import {readFile, lstat, realpath, readdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {LIMITS, publicationKey, validateManifest, validateAssetBytes, validateConfig} from './review-bundle.mjs';

function check(ok, message) { if (!ok) throw new Error(message); }
async function jsonFile(file, max = LIMITS.manifest) {
  const stat = await lstat(file);
  check(stat.isFile() && !stat.isSymbolicLink() && stat.size <= max, 'Invalid or oversized JSON input');
  const raw = await readFile(file);
  check(raw.length <= max, 'JSON input changed size during read');
  return JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(raw));
}
export async function loadConfig(file) {
  try { return validateConfig(await jsonFile(file)); }
  catch (error) { if (error.code === 'ENOENT') return {enabled:false}; throw error; }
}
function run(executable, args, name) {
  const result = spawnSync(executable, args, {encoding:'utf8',timeout:60000,maxBuffer:1024*1024,windowsHide:true});
  check(!result.error && result.status === 0, `${name} failed or unavailable; evidence not verified`);
  return result.stdout;
}
export async function validateLocalBundle(manifestFile, assetDirectory, {decode = true, ffmpeg='ffmpeg', ffprobe='ffprobe'} = {}) {
  const m = await jsonFile(manifestFile);
  const result = await validateManifest(m);
  const dir = await realpath(assetDirectory);
  const entries = await readdir(dir);
  check(entries.length === m.assets.length && entries.every(f => m.assets.some(a => a.filename === f)), 'Asset directory must contain exactly the manifest assets');
  for (const asset of m.assets) {
    const file = path.join(dir, asset.filename), stat = await lstat(file);
    check(stat.isFile() && !stat.isSymbolicLink() && stat.size === asset.bytes, 'Asset must be a regular file of the declared size');
    check(path.dirname(await realpath(file)) === dir, 'Asset escapes evidence directory');
    await validateAssetBytes(asset, new Uint8Array(await readFile(file)));
    if (decode && ['image/png','video/mp4'].includes(asset.mime)) {
      const probe = JSON.parse(run(ffprobe, ['-v','error','-count_frames','-show_streams','-show_format','-of','json',file], 'Media probe'));
      const streams = probe.streams.filter(s => s.codec_type === 'video');
      check(streams.length === 1, 'Media must contain one visual stream');
      const s = streams[0];
      check(Number(s.nb_read_frames) >= (asset.mime === 'video/mp4' ? 2 : 1), 'Media contains no usable decoded frames');
      check(s.width === asset.width && s.height === asset.height, 'Decoded dimensions mismatch');
      if (asset.mime === 'video/mp4') {
        check(s.codec_name === 'h264' && s.pix_fmt === 'yuv420p', 'Video must use H.264/yuv420p');
        const duration = Number(probe.format.duration) * 1000;
        check(Number.isFinite(duration) && Math.abs(duration-asset.duration_ms) <= 100, 'Decoded duration mismatch');
      } else check(s.codec_name === 'png', 'Screenshot must decode as PNG');
      run(ffmpeg, ['-v','error','-xerror','-nostdin','-i',file,'-map','0:v:0','-f','null','-'], 'Full media decode');
    }
  }
  return {...result,integrity:'verified',media_decode:decode ? 'verified where applicable' : 'not verified',
    behavior_review:'not verified by this helper',source_provenance:'not verified by this helper'};
}
export async function inspectConfig(file, repositoryRoot) {
  const config = await loadConfig(file);
  if (!config.enabled) return {enabled:false,site_mutations:0};
  const root = await realpath(repositoryRoot);
  const skillRoot = await realpath(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'));
  check(root !== skillRoot && !root.startsWith(skillRoot+path.sep), 'Do not use an installed skill as evidence storage');
  const target = path.resolve(root,config.output_directory);
  check(target.startsWith(root+path.sep), 'Evidence directory escapes repository');
  let parent = target;
  for (;;) {
    try {
      const actual = await realpath(parent);
      check(actual === root || actual.startsWith(root+path.sep), 'Evidence path resolves outside repository');
      break;
    } catch (error) { if (error.code !== 'ENOENT') throw error; parent = path.dirname(parent); }
  }
  const gitRoot = run('git',['-C',root,'rev-parse','--show-toplevel'],'Git root check').trim();
  check(await realpath(gitRoot) === root, 'Configured root must be the Git worktree root');
  // Check a prospective file too: an existing directory is not required for dry-run.
  run('git',['-C',root,'check-ignore','--quiet','--',config.output_directory+'/receipt.json'],'Ignored evidence directory check');
  const tracked = run('git',['-C',root,'ls-files','--',config.output_directory],'Tracked evidence check').trim();
  check(!tracked, 'Evidence output contains tracked files');
  const configRelative = path.relative(root,path.resolve(file));
  if (!configRelative.startsWith('..') && !path.isAbsolute(configRelative)) {
    run('git',['-C',root,'check-ignore','--quiet','--',configRelative],'Ignored config check');
    check(!run('git',['-C',root,'ls-files','--',configRelative],'Tracked config check').trim(), 'Local config is tracked');
  }
  return {enabled:true,required:config.required,site_project_id:config.site.project_id,
    repository:config.repository,storage:'ignored local directory',site_mutations:0};
}
async function main(args) {
  const [command,...rest] = args;
  if (command === 'key' && rest.length === 1) return {publication_key:await publicationKey(await jsonFile(rest[0]))};
  if (command === 'config' && rest.length === 2) return inspectConfig(rest[0],rest[1]);
  if (command === 'validate' && (rest.length === 2 || rest.length === 3 && rest[2] === '--integrity-only'))
    return validateLocalBundle(rest[0],rest[1],{decode:rest[2] !== '--integrity-only'});
  throw new Error('Usage: review-bundle-cli.mjs key MANIFEST | config CONFIG REPO_ROOT | validate MANIFEST ASSET_DIR [--integrity-only]');
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { console.log(JSON.stringify(await main(process.argv.slice(2)),null,2)); }
  catch (error) {
    // Never echo filesystem errors, stderr from media tools, or supplied payloads.
    const message = error.code || error instanceof SyntaxError ? 'Input unavailable or invalid; check paths and JSON locally' : error.message;
    console.error(JSON.stringify({ok:false,error:message})); process.exitCode = 1;
  }
}
