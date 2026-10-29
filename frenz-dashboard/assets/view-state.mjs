// Framework-neutral presentation state. No records, writes, or authorization live here.
const positiveInteger = value =>
  /^[1-9]\d*$/.test(String(value)) && Number.isSafeInteger(Number(value))
    ? Number(value) : null;
const single = (params, key) => params.getAll(key).length === 1 ? params.get(key) : null;
const choice = (value, allowed, fallback) => allowed.includes(value) ? value : fallback;
const safeCall = (fn, ...args) => { try { return fn?.(...args); } catch { return undefined; } };

export function decodeState(search, schema, savedPageSize) {
  const params = new URLSearchParams(search);
  const section = choice(single(params, 'section'), Object.keys(schema.sections), schema.defaultSection);
  const view = schema.sections[section];
  const filters = {};
  for (const [key, allowed] of Object.entries(view.filters)) {
    const value = single(params, `filter.${key}`);
    if (allowed.includes(value)) filters[key] = value;
  }
  const requestedSize = positiveInteger(single(params, 'pageSize'));
  // A malformed explicit URL uses the site default, never a device-specific preference.
  const size = params.has('pageSize') ? requestedSize : positiveInteger(savedPageSize);
  const entry = single(params, 'entry');
  return {
    section, filters,
    sort: choice(single(params, 'sort'), view.sorts, view.defaultSort),
    direction: choice(single(params, 'direction'), ['asc', 'desc'], view.defaultDirection),
    page: positiveInteger(single(params, 'page')) ?? 1,
    pageSize: schema.pageSizes.includes(size) ? size : schema.defaultPageSize,
    entry: entry && /^[A-Za-z0-9_-]{1,128}$/.test(entry) ? entry : null,
  };
}

export function encodeState(state, schema) {
  const candidate = new URLSearchParams();
  for (const key of ['section', 'sort', 'direction', 'page', 'pageSize', 'entry']) {
    if (state[key] != null) candidate.set(key, String(state[key]));
  }
  for (const [key, value] of Object.entries(state.filters ?? {})) {
    candidate.set(`filter.${key}`, String(value));
  }
  const valid = decodeState(candidate, schema);
  const params = new URLSearchParams();
  params.set('section', valid.section);
  for (const key of Object.keys(valid.filters).sort()) params.set(`filter.${key}`, valid.filters[key]);
  for (const key of ['sort', 'direction', 'page', 'pageSize']) params.set(key, String(valid[key]));
  if (valid.entry) params.set('entry', valid.entry);
  return params.toString();
}

// browser can be window or a router adapter implementing these browser APIs.
// onChange receives { state, notice }; wire it to rendering, not record mutations.
export function createNavigation(browser, schema, { readPageSize, savePageSize, onChange } = {}) {
  let state;
  let notice = null;
  const emit = () => onChange?.({ state: structuredClone(state), notice });
  const write = replace => {
    const url = browser.location.pathname + '?' + encodeState(state, schema) + browser.location.hash;
    browser.history[replace ? 'replaceState' : 'pushState'](browser.history.state, '', url);
  };
  const restore = () => {
    state = decodeState(browser.location.search, schema, safeCall(readPageSize));
    notice = null;
    write(true); // Canonicalize the current entry; never create a restoration loop.
    emit();
  };
  restore();
  browser.addEventListener('popstate', restore);
  return {
    get state() { return structuredClone(state); },
    navigate(patch, { replace = false } = {}) {
      state = decodeState(encodeState({ ...state, ...patch }, schema), schema);
      notice = null;
      write(replace);
      emit();
    },
    setPageSize(value) {
      const size = positiveInteger(value);
      if (!schema.pageSizes.includes(size)) return;
      safeCall(savePageSize, size); // Only explicit selection changes the remembered preference.
      this.navigate({ pageSize: size, page: 1 });
    },
    closeEntry() {
      this.navigate({ entry: null }, { replace: true }); // Never history.back().
    },
    entryUnavailable(id) {
      // Call only after the authorized lookup completes; ignore stale async responses.
      if (!id || state.entry !== id) return;
      state = { ...state, entry: null };
      notice = 'This entry is unavailable. It may have been removed or you may not have access.';
      write(true);
      emit();
    },
    dismissNotice() { notice = null; emit(); },
    dispose() { browser.removeEventListener('popstate', restore); },
  };
}
