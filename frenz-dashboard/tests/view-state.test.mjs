import test from 'node:test';
import assert from 'node:assert/strict';
import { decodeState, encodeState, createNavigation } from '../assets/view-state.mjs';

const schema = {
  defaultSection: 'overview', pageSizes: [10, 25, 50, 100], defaultPageSize: 25,
  sections: {
    overview: { sorts: ['name'], defaultSort: 'name', defaultDirection: 'asc', filters: {} },
    entries: { sorts: ['name', 'updated'], defaultSort: 'updated', defaultDirection: 'desc',
      filters: { status: ['open', 'closed'], tag: ['needs review', 'ready'] } },
  },
};
const selected = {
  section: 'entries', filters: { status: 'open', tag: 'needs review' },
  sort: 'name', direction: 'asc', page: 3, pageSize: 50, entry: 'entry_42',
};
// A deterministic browser-history adapter; this is not visual/browser acceptance evidence.
function browserAt(search = '') {
  const browser = new EventTarget();
  let stack = [new URL('https://example.test/dashboard' + search)];
  let index = 0;
  Object.defineProperty(browser, 'location', { get: () => stack[index] });
  browser.history = {
    state: null,
    get length() { return stack.length; },
    replaceState(_state, _title, url) { stack[index] = new URL(url, stack[index]); },
    pushState(_state, _title, url) {
      stack = stack.slice(0, index + 1);
      stack.push(new URL(url, stack[index]));
      index++;
    },
    back() { if (index > 0) { index--; browser.dispatchEvent(new Event('popstate')); } },
    forward() { if (index + 1 < stack.length) { index++; browser.dispatchEvent(new Event('popstate')); } },
  };
  return browser;
}

test('1. shared query round-trips all view fields independently of local preferences', () => {
  const query = encodeState(selected, schema);
  assert.deepEqual(decodeState(query, schema, 10), selected);
  assert.equal(encodeState(decodeState(query, schema), schema), query);
  assert.match(query, /filter.tag=needs\+review/);
  const browser = browserAt('?' + query);
  const nav = createNavigation(browser, schema, { readPageSize: () => 100 });
  assert.deepEqual(nav.state, selected);
  assert.equal(browser.history.length, 1);
  nav.dispose();
});

test('2. malformed, duplicate, unknown and section-incompatible query values are rejected', () => {
  const state = decodeState('?section=entries&sort=secret&direction=sideways&page=1e3'
    + '&pageSize=999&entry=%3Cscript%3E&filter.status=open&filter.status=closed'
    + '&filter.tag=private&token=secret', schema, 100);
  assert.deepEqual(state, {
    section: 'entries', filters: {}, sort: 'updated', direction: 'desc',
    page: 1, pageSize: 25, entry: null,
  });
  const canonical = encodeState(state, schema);
  assert.ok(!canonical.includes('secret') && !canonical.includes('token'));
  for (const page of ['-1', '0', '1.5', 'Infinity', '9007199254740992']) {
    assert.equal(decodeState('?page=' + page, schema).page, 1);
  }
  assert.equal(decodeState('?section=entries&section=overview', schema).section, 'overview');
  assert.deepEqual(decodeState('?section=overview&filter.status=open&sort=updated', schema).filters, {});
  assert.equal(decodeState('?entry=a&entry=b', schema).entry, null);
});

test('3. Back/Forward and reload restore presentation state without replaying saved-data changes', () => {
  const browser = browserAt('?' + encodeState(selected, schema));
  let savedData = { reviewed: false };
  const nav = createNavigation(browser, schema);
  nav.navigate({ filters: { status: 'closed' }, page: 1, entry: null });
  const next = nav.state;
  savedData.reviewed = true; // A record write belongs outside navigation.
  browser.history.back();
  assert.deepEqual(nav.state, selected);
  browser.history.forward();
  assert.deepEqual(nav.state, next);
  nav.dispose();
  const reloaded = createNavigation(browser, schema);
  assert.deepEqual(reloaded.state, next);
  assert.deepEqual(savedData, { reviewed: true });
  reloaded.dispose();
});

test('4. explicit page-size selection persists; URLs win and storage failures remain usable', () => {
  let remembered = 10;
  const preferences = { readPageSize: () => remembered, savePageSize: size => { remembered = size; } };
  const nav = createNavigation(browserAt(), schema, preferences);
  assert.equal(nav.state.pageSize, 10);
  nav.navigate({ page: 5 });
  nav.setPageSize('50');
  assert.equal(remembered, 50);
  assert.equal(nav.state.page, 1);
  assert.equal(createNavigation(browserAt(), schema, preferences).state.pageSize, 50);
  const linked = createNavigation(browserAt('?pageSize=25'), schema, preferences);
  assert.equal(linked.state.pageSize, 25);
  assert.equal(remembered, 50);
  linked.setPageSize(999);
  assert.equal(linked.state.pageSize, 25);
  const unavailable = createNavigation(browserAt(), schema, {
    readPageSize: () => { throw Error('blocked'); },
    savePageSize: () => { throw Error('blocked'); },
  });
  unavailable.setPageSize(100);
  assert.equal(unavailable.state.pageSize, 100);
  assert.equal(decodeState('?pageSize=bad', schema, 50).pageSize, 25);
});

test('5. direct-entry close and missing-entry notice preserve the view without leaving the page', () => {
  const browser = browserAt('?' + encodeState(selected, schema));
  let rendered;
  const nav = createNavigation(browser, schema, { onChange: value => { rendered = value; } });
  nav.closeEntry();
  assert.deepEqual(nav.state, { ...selected, entry: null });
  assert.ok(!browser.location.search.includes('entry='));
  assert.equal(browser.history.length, 1);
  nav.navigate({ entry: 'missing' });
  nav.entryUnavailable('old-request');
  assert.equal(nav.state.entry, 'missing');
  nav.entryUnavailable('missing');
  assert.deepEqual(nav.state, { ...selected, entry: null });
  assert.match(rendered.notice, /unavailable/);
  assert.ok(!browser.location.search.includes('entry='));
  const url = browser.location.href;
  nav.dismissNotice();
  assert.equal(rendered.notice, null);
  assert.equal(browser.location.href, url);
  nav.dispose();
});
