import {pathToFileURL} from 'node:url';

export function isCliEntry(meta) {
  if (meta.main !== undefined) return meta.main;
  // Earlier Node 24 releases expose the ESM resolver but lack import.meta.main.
  const entry = process.argv[1];
  return Boolean(entry) && meta.resolve(pathToFileURL(entry).href) === meta.url;
}
