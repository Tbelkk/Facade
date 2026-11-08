// URL fit-check: is this a legacy system RESTore should explore?
//
// Live:  POST {CHECK_ENDPOINT}  body { url }  →  { verdict: 'good_fit' | 'probably_not' | 'blocked', reasons: [string] }
// Mock:  same answer shape, picked from the URL so every verdict can be tried (see mockVerdict below).
//
// Mode:  mock until the endpoint exists. Switch with VITE_CHECK_MODE=live in web/.env,
//        or add ?check=live / ?check=mock to the page address. The endpoint can be changed with VITE_CHECK_URL.

export const CHECK_ENDPOINT = import.meta.env?.VITE_CHECK_URL || 'http://localhost:8000/check';
const TIMEOUT_MS = 30000; // the check can take ~20s; give it some headroom

export function checkMode() {
  try {
    const q = new URLSearchParams(window.location.search).get('check');
    if (q === 'live' || q === 'mock') return q;
  } catch { /* no window */ }
  return import.meta.env?.VITE_CHECK_MODE === 'live' ? 'live' : 'mock';
}

/** Format check before calling anything. Returns { ok, url, error }. */
export function validateUrl(input) {
  const raw = String(input || '').trim();
  if (!raw) return { ok: false, error: 'Enter the address of the system, like https://old-clinic-2005.com' };
  if (/\s/.test(raw)) return { ok: false, error: 'A web address can’t contain spaces.' };
  const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(raw) ? raw : 'https://' + raw;
  let u;
  try { u = new URL(withScheme); } catch { return { ok: false, error: 'That isn’t a web address. Try something like https://old-clinic-2005.com' }; }
  if (!/^https?:$/.test(u.protocol)) return { ok: false, error: 'Use an http:// or https:// address.' };
  const host = u.hostname;
  const isIp = /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
  if (!(host === 'localhost' || isIp || /\.[a-z]{2,}$/i.test(host))) {
    return { ok: false, error: 'That address is missing a domain ending, like .com or .org.' };
  }
  return { ok: true, url: u.href };
}

export class CheckError extends Error {}

/** Calls the checker. Rejects with CheckError when the service can't be reached or answers badly. */
export async function checkUrl(url, { signal } = {}) {
  if (checkMode() === 'mock') return mockCheck(url, signal);

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort('timeout'), TIMEOUT_MS);
  const onAbort = () => ctrl.abort('cancelled');
  signal && signal.addEventListener('abort', onAbort);
  try {
    let res;
    try {
      res = await fetch(CHECK_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
        signal: ctrl.signal,
      });
    } catch (e) {
      if (signal && signal.aborted) throw e;
      if (ctrl.signal.reason === 'timeout') throw new CheckError('The URL check took longer than 30 seconds.');
      throw new CheckError(`Couldn’t reach the URL checker at ${CHECK_ENDPOINT}. Is it running?`);
    }
    if (!res.ok) throw new CheckError(`The URL checker answered with an error (${res.status}).`);
    let body;
    try { body = await res.json(); } catch { throw new CheckError('The URL checker sent back something that isn’t JSON.'); }
    return normalize(body);
  } finally {
    clearTimeout(timer);
    signal && signal.removeEventListener('abort', onAbort);
  }
}

function normalize(body) {
  const verdict = body && body.verdict;
  if (!['good_fit', 'probably_not', 'blocked'].includes(verdict)) throw new CheckError('The URL checker sent back an unknown verdict.');
  const reasons = Array.isArray(body.reasons) ? body.reasons.filter((r) => typeof r === 'string' && r.trim()) : [];
  return { verdict, reasons };
}

/* ---------------- mock ---------------- */

// Which verdict the mock gives, by URL:
//   blocked       address contains "blocked", is a bank, or a .gov / .mil site
//   probably_not  a well-known modern site (google, amazon, github, wikipedia, news.ycombinator.com, …)
//                 or the address contains "modern"
//   API down      address contains "down" (shows the error + Retry)
//   slow          address contains "slow" (takes ~20 s, to see the loading state)
//   good_fit      everything else, e.g. old-clinic-2005.com
const MODERN = ['google.', 'youtube.', 'amazon.', 'facebook.', 'instagram.', 'x.com', 'twitter.', 'reddit.', 'wikipedia.', 'github.', 'linkedin.', 'netflix.', 'apple.', 'microsoft.', 'openai.', 'news.ycombinator.com'];
const BANKS = ['chase.', 'bankofamerica.', 'wellsfargo.', 'paypal.', 'citi.'];

const MOCK = {
  good_fit: [
    'Pages are rendered on the server, with forms and tables',
    'No public API or data export found',
    'Looks like an internal or vendor system (login and admin pages)',
  ],
  probably_not: [
    'This looks like a modern public website',
    'It already offers a public API or data export',
    'RESTore works best on older systems your business runs or uses',
  ],
  blocked: [
    'This is a site you don’t run, with sensitive personal or financial data',
    'Its terms don’t allow automated access',
    'RESTore only explores systems you own or are authorized to automate',
  ],
};

export function mockVerdict(url) {
  const s = url.toLowerCase();
  let host = s;
  try { host = new URL(url).hostname.toLowerCase(); } catch { /* keep s */ }
  if (s.includes('blocked') || BANKS.some((b) => host.includes(b)) || /\.(gov|mil)$/.test(host)) return 'blocked';
  if (s.includes('modern') || MODERN.some((m) => host.includes(m))) return 'probably_not';
  return 'good_fit';
}

function mockCheck(url, signal) {
  const s = url.toLowerCase();
  const ms = s.includes('slow') ? 20000 : 1200 + Math.round(Math.random() * 600);
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => {
      if (s.includes('down')) reject(new CheckError(`Couldn’t reach the URL checker at ${CHECK_ENDPOINT}. Is it running? (mock: “down” in the address)`));
      else { const verdict = mockVerdict(url); resolve({ verdict, reasons: MOCK[verdict], mock: true }); }
    }, ms);
    signal && signal.addEventListener('abort', () => { clearTimeout(t); reject(new DOMException('cancelled', 'AbortError')); });
  });
}
