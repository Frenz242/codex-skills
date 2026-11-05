/** Portable review-bundle v1 contract. No network or filesystem side effects. */
export const LIMITS = Object.freeze({manifest: 256 * 1024, file: 16 * 1024 * 1024,
  bundle: 32 * 1024 * 1024, assets: 8});
const SHA = /^[a-f0-9]{40}$/;
const HASH = /^[a-f0-9]{64}$/;
const SLUG = /^[A-Za-z0-9_.-]+$/;
const STATES = ['verified', 'not applicable', 'not verified'];
function requireThat(condition, message) { if (!condition) throw new Error(message); }
function object(value, name, required, optional = []) {
  requireThat(value && typeof value === 'object' && !Array.isArray(value), `${name}: object required`);
  requireThat(required.every(k => Object.hasOwn(value, k)), `${name}: missing field`);
  requireThat(Object.keys(value).every(k => [...required, ...optional].includes(k)), `${name}: unknown field`);
}
function text(value, name, max = 4000) {
  requireThat(typeof value === 'string' && value.trim().length > 0 && value.length <= max,
    `${name}: nonempty bounded text required`);
  requireThat(!/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(value), `${name}: control character`);
  requireThat(!/(?:\b[A-Za-z]:[\\/]|\\\\[^\s\\]+\\|\/(?:Users|home|tmp|workspace)\/)/.test(value), `${name}: local path forbidden`);
  requireThat(!/(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_|-----BEGIN .*PRIVATE KEY|Bearer\s+\S{16,})/.test(value), `${name}: possible credential`);
}
function integer(value, name, min = 1, max = Number.MAX_SAFE_INTEGER) {
  requireThat(Number.isSafeInteger(value) && value >= min && value <= max, `${name}: integer out of range`);
}
function timestamp(value, name) {
  requireThat(typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)
    && Number.isFinite(Date.parse(value)), `${name}: UTC timestamp required`);
  requireThat(new Date(value).toISOString().replace('.000Z', 'Z') === value.replace('.000Z', 'Z'), `${name}: invalid calendar timestamp`);
}
function host(value) {
  requireThat(typeof value === 'string' && value === value.toLowerCase() &&
    /^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$/.test(value), 'repository: canonical DNS host required');
}
function name(value) { requireThat(typeof value === 'string' && SLUG.test(value) && !['.', '..'].includes(value), 'repository: invalid owner/name'); }
function repo(value) {
  object(value, 'repository', ['host', 'id', 'owner', 'name', 'url']);
  host(value.host); integer(value.id, 'repository.id'); name(value.owner); name(value.name);
  requireThat(value.url === `https://${value.host}/${value.owner}/${value.name}`, 'repository: noncanonical URL');
}
function ref(value) {
  object(value, 'ref', ['repository', 'ref']); repo(value.repository); text(value.ref, 'ref', 255);
  requireThat(!/[\s~^:?*\[\\]|\.\.|@\{|\/\/|^\/|\/$|\.$/.test(value.ref), 'ref: invalid Git reference');
}
export function canonical(value) {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return JSON.stringify(value);
  if (typeof value === 'number') { requireThat(Number.isSafeInteger(value), 'canonical: safe integers only'); return String(value); }
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  requireThat(value && typeof value === 'object', 'canonical: JSON value required');
  return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
}
export async function digest(bytes) {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), x => x.toString(16).padStart(2, '0')).join('');
}
export function identities(m) {
  const project_key = `${m.repository.host}:${m.repository.id}`;
  const pr_key = `${project_key}:${m.pull_request.number}`;
  return {project_key, pr_key, revision_key: `${pr_key}:${m.revision.head_sha}`};
}
export async function publicationKey(m) {
  // Deliberate allowlist: transport/CAS/status/receipts never affect evidence identity.
  const stable = Object.fromEntries(['schema_version','repository','pull_request','revision',
    'summary','acceptance','demonstration','assets'].map(k => [k, m[k]]));
  stable.assets = [...m.assets].sort((a,b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
  return identities(m).revision_key + ':' + await digest(new TextEncoder().encode(canonical(stable)));
}
function evidence(e) {
  object(e, 'criterion', ['criterion','state','automated','runtime','output','delivery','limitation']);
  text(e.criterion, 'criterion'); requireThat(STATES.includes(e.state), 'criterion: invalid state');
  for (const field of ['automated','runtime','output','delivery']) {
    requireThat(Array.isArray(e[field]) && e[field].length <= 40, `criterion.${field}: bounded list required`);
    for (const item of e[field]) {
      object(item, 'evidence', ['result','description','reason']);
      requireThat(['passed','failed','skipped','not-run','not applicable'].includes(item.result), 'evidence: invalid result');
      text(item.description, 'evidence.description');
      requireThat(typeof item.reason === 'string' && item.reason.length <= 4000, 'evidence.reason: string required');
      if (!['passed'].includes(item.result)) text(item.reason, 'evidence.reason');
      if (e.state === 'verified') requireThat(!['failed','skipped','not-run'].includes(item.result), 'verified criterion contains incomplete evidence');
    }
  }
  requireThat(typeof e.limitation === 'string' && e.limitation.length <= 4000, 'criterion.limitation: string required');
  if (e.state !== 'verified') text(e.limitation, 'criterion.limitation');
  if (e.state === 'verified') requireThat(['automated','runtime','output','delivery'].some(k => e[k].some(x => x.result === 'passed')), 'verified criterion needs actual evidence');
}
export function validateObservation(o) {
  object(o, 'observed_github', ['head_sha','state','draft','observed_at','reviews','checks']);
  requireThat(o.head_sha === null || SHA.test(o.head_sha), 'observation: invalid SHA');
  requireThat(['open','closed','merged','unknown'].includes(o.state), 'observation: invalid PR state');
  requireThat(o.draft === null || typeof o.draft === 'boolean', 'observation: invalid draft state');
  timestamp(o.observed_at, 'observation time'); text(o.reviews, 'reviews'); text(o.checks, 'checks');
}
export async function validateManifest(m) {
  object(m, 'manifest', ['schema_version','repository','pull_request','revision','observed_github',
    'summary','acceptance','demonstration','assets','publication']);
  requireThat(m.schema_version === 1, 'unsupported manifest version');
  requireThat(new TextEncoder().encode(JSON.stringify(m)).length <= LIMITS.manifest, 'manifest too large');
  repo(m.repository);
  const p = m.pull_request;
  object(p, 'pull_request', ['number','title','url','issues','head','base']);
  integer(p.number, 'PR number'); text(p.title, 'PR title', 300); ref(p.head); ref(p.base);
  requireThat(p.url === `${m.repository.url}/pull/${p.number}`, 'PR: noncanonical URL');
  requireThat(p.base.repository.id === m.repository.id && p.base.repository.host === m.repository.host, 'PR base repository mismatch');
  requireThat(Array.isArray(p.issues) && p.issues.length <= 30, 'issues: bounded list required');
  for (const url of p.issues) {
    const prefix = `https://${m.repository.host}/`;
    requireThat(typeof url === 'string' && url.startsWith(prefix) && /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/issues\/[1-9][0-9]*$/.test(url.slice(prefix.length)), 'issue: noncanonical URL');
  }
  const r = m.revision;
  object(r, 'revision', ['head_sha','base_sha','captured_at','clean_source','build_sha']);
  requireThat(SHA.test(r.head_sha) && (r.base_sha === null || SHA.test(r.base_sha)), 'revision: full commit SHA required');
  requireThat(r.build_sha === null || SHA.test(r.build_sha), 'revision: invalid build SHA');
  requireThat(r.clean_source === true, 'revision: clean source verification required');
  timestamp(r.captured_at, 'capture time'); validateObservation(m.observed_github);
  object(m.summary, 'summary', ['changed','why','inspect']);
  for (const v of Object.values(m.summary)) text(v, 'summary');
  requireThat(Array.isArray(m.acceptance) && m.acceptance.length > 0 && m.acceptance.length <= 60, 'acceptance: nonempty bounded list required');
  m.acceptance.forEach(evidence);
  const d = m.demonstration;
  object(d, 'demonstration', ['kind','surface','capture_source','state','scenario','outcome','tool','source_sha','limitation']);
  requireThat(['ui','nonvisual'].includes(d.kind) && STATES.includes(d.state), 'demonstration: invalid kind/state');
  requireThat(['web','terminal','other','nonvisual'].includes(d.surface), 'demonstration: invalid surface');
  requireThat(['codex-browser','codex-terminal','authorized-computer-use','other-terminal','none'].includes(d.capture_source), 'demonstration: invalid capture source');
  requireThat(d.surface !== 'web' || d.kind === 'ui', 'web demonstration must be UI evidence');
  if (d.capture_source !== 'none') {
    const sources = {web:['codex-browser'],terminal:['codex-terminal','other-terminal'],other:['authorized-computer-use'],nonvisual:['codex-terminal','other-terminal']};
    requireThat(sources[d.surface].includes(d.capture_source), 'capture source does not match project surface');
    if (d.capture_source === 'other-terminal') text(d.limitation, 'built-in terminal fallback reason');
  }
  for (const k of ['scenario','outcome','tool']) text(d[k], `demonstration.${k}`);
  requireThat(d.source_sha === r.head_sha, 'demonstration source does not match tested SHA');
  requireThat(typeof d.limitation === 'string' && d.limitation.length <= 4000, 'demonstration: limitation required');
  if (d.state !== 'verified') text(d.limitation, 'demonstration.limitation');
  if (d.kind === 'ui') {
    requireThat(d.state !== 'not applicable', 'missing UI capture is not not-applicable');
    if (d.state === 'verified') requireThat(r.build_sha === r.head_sha, 'UI build does not match tested SHA');
  }
  requireThat(Array.isArray(m.assets) && m.assets.length <= LIMITS.assets, 'assets: too many files');
  const ids = new Set(), names = new Set(); let total = 0;
  for (const a of m.assets) {
    object(a, 'asset', ['id','role','filename','mime','bytes','sha256','caption','width','height','duration_ms','codec']);
    requireThat(typeof a.id === 'string' && /^[a-z][a-z0-9-]{0,63}$/.test(a.id) && a.id !== 'manifest' && !ids.has(a.id), 'asset: invalid/duplicate ID'); ids.add(a.id);
    requireThat(typeof a.filename === 'string' && /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}\.(png|mp4|txt|json)$/.test(a.filename)
      && !/^(con|prn|aux|nul|com[0-9]|lpt[0-9])\./i.test(a.filename) && !names.has(a.filename.toLowerCase()), 'asset: unsafe/duplicate filename'); names.add(a.filename.toLowerCase());
    requireThat(['before','after','screenshot','poster','demonstration','output'].includes(a.role), 'asset: invalid role');
    text(a.caption, 'caption'); integer(a.bytes, 'asset bytes', 1, LIMITS.file); total += a.bytes;
    requireThat(HASH.test(a.sha256), 'asset: SHA-256 required');
    const types = {png:'image/png',mp4:'video/mp4',txt:'text/plain',json:'application/json'};
    requireThat(types[a.filename.split('.').pop()] === a.mime, 'asset: MIME/extension mismatch');
    if (a.mime.startsWith('image/') || a.mime.startsWith('video/')) {
      integer(a.width, 'width', 1, 7680); integer(a.height, 'height', 1, 4320);
    } else requireThat(a.width === null && a.height === null && a.role === 'output', 'output: invalid metadata');
    if (a.mime === 'video/mp4') {
      integer(a.duration_ms, 'duration', 1000, 30000); requireThat(a.codec === 'h264' && a.role === 'demonstration', 'video: H.264 demonstration required');
    } else requireThat(a.duration_ms === null && a.codec === null, 'non-video: invalid codec/duration');
  }
  if (m.assets.some(a => a.mime === 'image/png' || a.mime === 'video/mp4'))
    requireThat(d.capture_source !== 'none', 'media requires capture provenance');
  requireThat(total <= LIMITS.bundle, 'bundle too large');
  if (d.kind === 'ui' && d.state === 'verified') requireThat(m.assets.some(a => a.mime === 'image/png' && a.role !== 'poster') &&
    m.assets.some(a => a.mime === 'video/mp4'), 'verified UI demonstration needs screenshots and video');
  object(m.publication, 'publication', ['key','expected_current_version','prepared_at']);
  integer(m.publication.expected_current_version, 'expected version', 0);
  timestamp(m.publication.prepared_at, 'prepared time');
  requireThat(m.publication.key === await publicationKey(m), 'publication key mismatch');
  // Validate every supplied string, including optional reasons, before rendering/storage.
  function walk(v) { if (typeof v === 'string' && v) text(v, 'manifest text', 8000); else if (v && typeof v === 'object') Object.values(v).forEach(walk); }
  walk(m);
  return {...identities(m), publication_key: m.publication.key,
    freshness: m.observed_github.head_sha === null ? 'unknown' : m.observed_github.head_sha === r.head_sha ? 'matches observed head' : 'stale', bytes: total};
}
/** Integrity validation is NOT a claim that media decodes or demonstrates the change. */
export async function validateAssetBytes(asset, bytes) {
  requireThat(bytes instanceof Uint8Array && bytes.byteLength === asset.bytes && bytes.length <= LIMITS.file, 'asset: byte count mismatch');
  requireThat(await digest(bytes) === asset.sha256, 'asset: hash mismatch');
  const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (asset.mime === 'image/png') {
    requireThat(bytes.length >= 45 && [137,80,78,71,13,10,26,10].every((b,i) => bytes[i] === b), 'asset: invalid PNG');
    requireThat(v.getUint32(8) === 13 && new TextDecoder().decode(bytes.slice(12,16)) === 'IHDR', 'asset: missing PNG header');
    requireThat(v.getUint32(16) === asset.width && v.getUint32(20) === asset.height, 'asset: PNG dimensions mismatch');
    let at = 8, ended = false, data = false;
    while (at + 12 <= bytes.length) {
      const n = v.getUint32(at), type = new TextDecoder().decode(bytes.slice(at+4,at+8));
      requireThat(n <= bytes.length - at - 12, 'asset: truncated PNG');
      if (type === 'IDAT') data = true;
      at += n + 12;
      if (type === 'IEND') { requireThat(n === 0 && at === bytes.length, 'asset: invalid PNG end'); ended = true; break; }
    }
    requireThat(ended && data, 'asset: incomplete PNG');
  } else if (asset.mime === 'video/mp4') {
    let at = 0; const boxes = [];
    while (at + 8 <= bytes.length) {
      const n = v.getUint32(at), type = new TextDecoder().decode(bytes.slice(at+4,at+8));
      requireThat(n >= 8 && n <= bytes.length-at, 'asset: truncated/unsupported MP4 box');
      boxes.push(type); at += n;
    }
    requireThat(at === bytes.length && boxes[0] === 'ftyp' && boxes.includes('moov') && boxes.includes('mdat') && boxes.indexOf('moov') < boxes.indexOf('mdat'), 'asset: fast-start MP4 required');
  } else {
    let content; try { content = new TextDecoder('utf-8',{fatal:true}).decode(bytes); } catch { throw new Error('asset: invalid UTF-8'); }
    text(content, 'output asset', LIMITS.file);
    if (asset.mime === 'application/json') { try { JSON.parse(content); } catch { throw new Error('asset: invalid JSON'); } }
  }
}
export function validateConfig(c) {
  object(c, 'config', ['schema_version','enabled'], ['required','site','repository','auth','output_directory','media']);
  requireThat(c.schema_version === 1 && typeof c.enabled === 'boolean', 'unsupported/invalid configuration');
  if (!c.enabled) return {enabled:false};
  object(c, 'enabled config', ['schema_version','enabled','required','site','repository','auth','output_directory','media']);
  requireThat(typeof c.required === 'boolean', 'config.required: boolean required');
  object(c.site, 'site', ['project_id','origin']); text(c.site.project_id, 'site ID', 200);
  let u; try {u = new URL(c.site.origin);} catch {throw new Error('site: invalid origin');}
  requireThat(u.protocol === 'https:' && u.origin === c.site.origin && !u.username && !u.password && !u.port && u.hostname.endsWith('.chatgpt.site'), 'site: canonical ChatGPT Site HTTPS origin required');
  object(c.repository, 'configured repository', ['host','id']); host(c.repository.host); integer(c.repository.id, 'configured repository ID');
  object(c.auth, 'auth', ['method','service_token_env','publisher_key_env']);
  requireThat(c.auth.method === 'sites-service-and-publisher-key', 'unsupported transport authentication');
  for (const k of ['service_token_env','publisher_key_env']) requireThat(/^[A-Z][A-Z0-9_]{2,100}$/.test(c.auth[k]), 'auth: environment variable NAME required');
  requireThat(c.auth.service_token_env !== c.auth.publisher_key_env, 'auth: separate credentials required');
  requireThat(typeof c.output_directory === 'string' && /^[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*$/.test(c.output_directory)
    && !c.output_directory.split('/').some(x => ['.','..','.git'].includes(x)), 'output: safe repository-relative directory required');
  object(c.media, 'media', ['target_seconds','max_file_bytes','max_bundle_bytes','ffmpeg','ffprobe']);
  integer(c.media.target_seconds,'target seconds',8,15); integer(c.media.max_file_bytes,'file limit',1,LIMITS.file);
  integer(c.media.max_bundle_bytes,'bundle limit',c.media.max_file_bytes,LIMITS.bundle);
  for (const k of ['ffmpeg','ffprobe']) requireThat(typeof c.media[k] === 'string' && /^[A-Za-z0-9_.-]+$/.test(c.media[k]), 'media: executable name on PATH required');
  return c;
}
