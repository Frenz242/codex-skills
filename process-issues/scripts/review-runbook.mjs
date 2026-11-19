export const RUNBOOK_ASSET_ID = 'owner-verification';
export const MAX_RUNBOOK_BYTES = 128 * 1024;

function fields(value, required, optional = []) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && required.every(key => Object.hasOwn(value, key))
    && Object.keys(value).every(key => required.includes(key) || optional.includes(key));
}

function text(value, limit) {
  return typeof value === 'string' && value.trim().length > 0 && value.length <= limit
    && !/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffd]/.test(value);
}

function safeLink(value) {
  if (!fields(value, ['label', 'url']) || !text(value.label, 150) || !text(value.url, 2000)) return false;
  try {
    const url = new URL(value.url);
    return value.url.startsWith('https://') && !url.username && !url.password;
  } catch {
    return false;
  }
}

function block(value) {
  return fields(value, ['label', 'kind', 'text'])
    && text(value.label, 150) && ['prompt', 'script'].includes(value.kind) && text(value.text, 16000);
}

function validList(values, max, validate) {
  return Array.isArray(values) && values.length <= max && values.every(validate);
}

export function parseRunbook(bytes) {
  if (bytes.byteLength > MAX_RUNBOOK_BYTES) throw Error('Owner runbook exceeds 128 KiB');
  const decoded = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  const runbook = JSON.parse(decoded);
  if (!fields(runbook, ['schema_version', 'steps']) || runbook.schema_version !== 1
    || !validList(runbook.steps, 24, step =>
      fields(step, ['title', 'instructions'], ['links', 'blocks', 'pass', 'fail', 'unverified'])
      && text(step.title, 150) && text(step.instructions, 6000)
      && (!Object.hasOwn(step, 'links') || validList(step.links, 10, safeLink))
      && (!Object.hasOwn(step, 'blocks') || validList(step.blocks, 8, block))
      && ['pass', 'fail', 'unverified'].every(key => !Object.hasOwn(step, key) || text(step[key], 3000)))
    || runbook.steps.length === 0) {
    throw Error('Invalid owner runbook format');
  }
  return runbook;
}
