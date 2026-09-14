/* LOCUS RAG — Frontend script
 * Read-only interface over localhost:8765/api/retrieve
 * No ingestion, DB, or backend modification.
 */
const $d = id => document.getElementById(id);
const $ = s => document.querySelector(s);

const btn = $d('btn');
const input = $d('q');
const out = $d('out');

/* ------------------------------------------------------------------ */
/*  Theme                                                              */
/* ------------------------------------------------------------------ */
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme') || 'dark';
  html.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark');
  localStorage.setItem('locus-theme', html.getAttribute('data-theme'));
}
(function loadTheme(){
  const saved = localStorage.getItem('locus-theme');
  const prefersLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
  if (saved) document.documentElement.setAttribute('data-theme', saved);
  else if (prefersLight) document.documentElement.setAttribute('data-theme', 'light');
})();

/* ------------------------------------------------------------------ */
/*  History (localStorage only)                                        */
/* ------------------------------------------------------------------ */
const HISTORY_KEY = 'locus_history';
function getHistory() { try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); } catch { return []; } }
function saveHistory(h) { try { localStorage.setItem(HISTORY_KEY, JSON.stringify(h.slice(0, 20))); } catch {} }
function addToHistory(query) {
  const h = getHistory();
  const cleaned = query.trim();
  if (!cleaned) return;
  const filtered = h.filter(q => q !== cleaned);
  filtered.unshift(cleaned);
  saveHistory(filtered);
  renderHistory();
}
function clearHistory() { localStorage.removeItem(HISTORY_KEY); renderHistory(); }
function renderHistory() {
  const h = getHistory();
  const section = $d('history-section');
  const list = $d('history-list');
  if (!h.length) { section.hidden = true; return; }
  section.hidden = false;
  list.innerHTML = h.map(q => `<button class="history-item" onclick="runHistory('${q.replace(/'/g, "\\'")}')"><span class="history-q">${q.replace(/</g, '&lt;')}</span><span class="history-action">↩</span></button>`).join('');
}
function runHistory(q) { input.value = q; input.focus(); btn.click(); }

/* ------------------------------------------------------------------ */
/*  Examples                                                          */
/* ------------------------------------------------------------------ */
function runExample(el) {
  const q = el.getAttribute('data-q');
  input.value = q;
  input.focus();
  setTimeout(() => btn.click(), 120);
}

/* ------------------------------------------------------------------ */
/*  Reset / Home                                                       */
/* ------------------------------------------------------------------ */
function resetApp() { resetToHero(); }
function resetToHero() {
  input.value = '';
  input.focus();
  document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n') {
    e.preventDefault(); resetToHero();
  }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
    e.preventDefault(); input.focus();
  }
});
showHero();

  stopLoader();
  clearInterval(loaderTimer);
  $d('action-bar').style.display = 'none';
}

/* ------------------------------------------------------------------ */
/*  UI States                                                          */
/* ------------------------------------------------------------------ */
function hideAll() {
  $d('hero').hidden = true;
  $d('loading').hidden = true;
  $d('answer-area').hidden = true;
  $d('no-result').hidden = true;
  $d('error-state').hidden = true;
}
function showHistoryDock() { hideAll(); document.getElementById("history-section").hidden=false; renderHistory(); }
function showHero() {
  hideAll();
  $d('hero').hidden = false;
  renderHistory();
}
function showLoading() { hideAll(); $d('loading').hidden = false; startLoaderSteps(); }
function showAnswer() { hideAll(); $d('answer-area').hidden = false; $d('action-bar').style.display = 'flex'; }
function showNoResult() { hideAll(); $d('no-result').hidden = false; }
function showError() { hideAll(); $d('error-state').hidden = false; }

/* ------------------------------------------------------------------ */
/*  Loader                                                              */
/* ------------------------------------------------------------------ */
let loaderTimer = null;
function startLoaderSteps() {
  const steps = $d('loader-steps').querySelectorAll('li');
  let i = 0;
  steps.forEach(s => s.classList.remove('step-active'));
  clearInterval(loaderTimer);
  loaderTimer = setInterval(() => {
    steps.forEach(s => s.classList.remove('step-active'));
    if (i < steps.length) { steps[i].classList.add('step-active'); i++; } else { i = 0; steps[0].classList.add('step-active'); }
  }, 1100);
}
function stopLoader() { clearInterval(loaderTimer); }

/* ------------------------------------------------------------------ */
/*  Markdown rendering                                                  */
/* ------------------------------------------------------------------ */
function mdToHtml(text) {
  if (!text) return '';
  let html = String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  html = html.replace(/^(#{1,3})\s+(.+)$/gm, (m, hash, title) => {
    const sz = {1:'1.3rem',2:'1.05rem',3:'.95rem'}[hash.length] || '1rem';
    return `<h3 style="font-size:${sz};font-weight:600;margin-top:24px;margin-bottom:10px;letter-spacing:-0.025em;line-height:1.2;">${title}</h3>`;
  });
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em style="font-family:Instrument Serif,Georgia,serif;font-style:italic;">$1</em>');
  html = html.replace(/`(.+?)`/g, '<code>$1</code>');
  html = html.replace(/^([\s]*)([-*]\s+)(.+)$/gm, '<ul style="margin:8px 0 16px 20px;padding-left:6px;list-style:disc;"><li style="margin-bottom:6px;">$3</li></ul>');
  html = html.replace(/<\/ul>\s*<ul[^>]*>/g, '');
  const lines = html.split(/\n+/);
  let out = ''; let inList = false;
  for (const line of lines) {
    const t = line.trim();
    if (!t) continue;
    if (t.startsWith('<h3')) { out += t; continue; }
    if (t.startsWith('<ul')) { out += t; inList = true; continue; }
    if (t === '</ul>') { out += t; inList = false; continue; }
    if (t.startsWith('<')) { out += t; continue; }
    out += `<p style="margin-bottom:16px;line-height:1.75;">${t}</p>`;
  }
  return out;
}

/* ------------------------------------------------------------------ */
/*  Source builder                                                       */
/* ------------------------------------------------------------------ */
function buildSources(results) {
  if (!results || !results.length) return '';
  return results.map(r => {
    const loc = r.source_locator || {};
    const filename = (loc.filename || r.filename || r.doc_id || 'Unknown').replace(/</g, '&lt;');
    const page = (loc.page || r.page || '-');
    const sheet = (loc.sheet || r.sheet || '-');
    const link = r.source_link || loc.source_link || null;
    const title = filename.length > 50 ? filename.slice(0, 47) + '…' : filename;
    const meta = [page !== '-' ? `Page ${page}` : null, sheet !== '-' ? `Sheet ${sheet}` : null, r.index_name ? `Index: ${r.index_name}` : null].filter(Boolean).join(' · ');
    return `<div class="source-item"><div class="source-title">${title}</div>${meta ?`<div class="source-meta-row"><span>${meta}</span></div>`:''}${link ? `<a href="${link}" class="source-link" target="_blank" rel="noopener noreferrer">Open source</a>` : '<span style="font-size:.82rem;color:var(--ink-faint);">No external link</span>'}</div>`;
  }).join('');
}

/* ------------------------------------------------------------------ */
/*  Technical details                                                    */
/* ------------------------------------------------------------------ */
function buildTech(data) {
  const results = data.results || [];
  const claims = data.claims || [];
  const lines = [
    `<div><strong>Results:</strong> ${results.length} source${results.length !== 1 ? 's' : ''}</div>`,
    `<div><strong>Query:</strong> ${String(data.query || '').replace(/</g, '&lt;')}</div>`,
    `<div><strong>Read-only catalog:</strong> preserved · no fabrication</div>`,
  ];
  if (claims.length) lines.push(`<div><strong>Claims verified:</strong> ${claims.filter(c => c.status === 'VERIFIED').length} / ${claims.length}</div>`);
  if (results[0]) lines.push(`<div><strong>Top index:</strong> ${(results[0].index_name || '—').replace(/</g, '&lt;')}</div>`);
  return lines.join('');
}

/* ------------------------------------------------------------------ */
/*  Answer rendering                                                     */
/* ------------------------------------------------------------------ */
function renderAnswer(data) {
  const results = data.results || [];
  const answerText = data.answer_text || '';

  let body = '';
  if (answerText && answerText.length > 20) body = mdToHtml(answerText);
  else if (results.length) {
    const snippets = results.slice(0, 5).map((r, i) => {
      const s = (r.text || '').trim();
      const trimmed = s.length > 300 ? s.slice(0, 300) + '…' : s;
      return `<p><strong>Source ${i + 1}.</strong> ${trimmed.replace(/</g, '&lt;')}</p>`;
    }).join('');
    body = `<p>Based on institutional records (${results.length} source${results.length > 1 ? 's' : ''} retrieved):</p>` + snippets;
  } else {
    body = `<p>The records contain insufficient verified evidence to answer this query confidently. The institutional index preserved its read-only state; no fabrication was performed.</p>`;
  }

  $d('answer-body').innerHTML = body;
  $d('answer-heading').textContent = (answerText && answerText.length > 20) ? 'Answer' : 'Results';

  const metaText = results.length ? `${results.length} source${results.length > 1 ? 's' : ''} · Read-only Drive · Real provenance` : 'No verified sources retrieved';
  $d('answer-meta').textContent = metaText;

  // Evidence summary
  if (results.length) {
    $d('evidence-summary').hidden = false;
    $d('evidence-text').textContent = `Based on ${results.length} supporting source${results.length > 1 ? 's' : ''}`;
  } else {
    $d('evidence-summary').hidden = true;
  }

  // Sources
  const sourceHtml = buildSources(results);
  $d('sources-list').innerHTML = sourceHtml || '<p style="font-size:.85rem;color:var(--ink-faint);">No additional source details available.</p>';
  $d('source-count').textContent = String(results.length);
  $d('sources-toggle').setAttribute('aria-expanded', 'false');
  $d('sources-panel').hidden = true;

  // Technical details
  $d('tech-body').innerHTML = buildTech(data);
  $d('tech-panel').hidden = true;
  $d('tech-toggle-btn').setAttribute('aria-expanded', 'false');

  // Action bar
  $d('btn-copy').textContent = 'Copy';
  $d('btn-regen').disabled = false;

  showAnswer();
  stopLoader();
}

function renderNoResult() {
  $d('answer-body').innerHTML = '';
  $d('answer-heading').textContent = 'Insufficient evidence';
  $d('answer-meta').textContent = 'Read-only Drive preserved · no fabrication';
  $d('evidence-summary').hidden = true;
  $d('sources-list').innerHTML = '';
  $d('source-count').textContent = '0';
  $d('sources-panel').hidden = true;
  $d('sources-toggle').setAttribute('aria-expanded', 'false');
  $d('tech-body').innerHTML = '';
  $d('action-bar').style.display = 'none';
  showNoResult();
  stopLoader();
}

function renderError() {
  hideAll();
  $d('error-state').hidden = false;
  $d('action-bar').style.display = 'none';
  stopLoader();
}

/* ------------------------------------------------------------------ */
/*  Actions                                                             */
/* ------------------------------------------------------------------ */
function copyAnswer() {
  const text = $d('answer-body').textContent || '';
  navigator.clipboard.writeText(text).then(() => {
    const btn = $d('btn-copy');
    btn.textContent = 'Copied';
    setTimeout(() => btn.textContent = 'Copy', 1200);
    showToast('Copied to clipboard');
  }).catch(() => showToast('Copy failed'));
}

function regenerateAnswer() {
  const q = input.value.trim();
  if (!q) return;
  $d('btn-regen').disabled = true;
  $d('btn-regen').textContent = 'Regenerating…';
  btn.click();
  setTimeout(() => { $d('btn-regen').disabled = false; $d('btn-regen').textContent = 'Regenerate'; }, 3000);
}

function showToast(msg) {
  let toast = $d('toast');
  if (!toast) { toast = document.createElement('div'); toast.id = 'toast'; toast.className = 'toast'; document.body.appendChild(toast); }
  toast.textContent = msg; toast.classList.add('show'); clearTimeout(toast._t);
  toast._t = setTimeout(() => toast.classList.remove('show'), 1600);
}

function toggleSources() {
  const panel = $d('sources-panel');
  const btnToggle = $d('sources-toggle');
  const open = btnToggle.getAttribute('aria-expanded') === 'true';
  btnToggle.setAttribute('aria-expanded', String(!open));
  panel.hidden = open;
}

function toggleTech() {
  const panel = $d('tech-panel');
  const btnToggle = $d('tech-toggle-btn');
  const open = btnToggle.getAttribute('aria-expanded') === 'true';
  btnToggle.setAttribute('aria-expanded', String(!open));
  panel.hidden = open;
}

/* ------------------------------------------------------------------ */
/*  Search handler                                                      */
/* ------------------------------------------------------------------ */
btn.addEventListener('click', async () => {
  const q = input.value.trim();
  if (!q) { document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n') {
    e.preventDefault(); resetToHero();
  }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
    e.preventDefault(); input.focus();
  }
});
showHero();

document.addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openCommandPalette(); } }); return; }

  addToHistory(q);
  showLoading();

  const msgs = ['Searching institutional knowledge…', 'Finding relevant records…', 'Reading supporting evidence…', 'Preparing response…'];
  let msgIdx = 0;
  const msgTimer = setInterval(() => { $d('loader-text').textContent = msgs[msgIdx % msgs.length]; msgIdx++; }, 900);

  try {
    const resp = await fetch('http://localhost:8765/api/retrieve', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: q })
    });
    clearInterval(msgTimer);
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    const results = data.results || [];
    data.query = q; // attach for tech details
    if (!results.length && (!data.answer_text || data.answer_text.length < 10)) { renderNoResult(); return; }
    renderAnswer(data);
  } catch (e) {
    clearInterval(msgTimer);
    renderError();
    console.error('Fetch error:', e);
  }
});

/* ------------------------------------------------------------------ */
/*  Input events                                                        */
/* ------------------------------------------------------------------ */
input.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); btn.click(); }
  if (e.key === 'Escape') { input.blur(); if (!input.value.trim()) document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n') {
    e.preventDefault(); resetToHero();
  }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
    e.preventDefault(); input.focus();
  }
});
showHero();

document.addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openCommandPalette(); } }); }
});

/* ------------------------------------------------------------------ */
/*  Clear                                                               */
/* ------------------------------------------------------------------ */
$d('clear').addEventListener('click', () => {
  input.value = '';
  input.focus();
  document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n') {
    e.preventDefault(); resetToHero();
  }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
    e.preventDefault(); input.focus();
  }
});
showHero();

  stopLoader();
  clearInterval(loaderTimer);
  $d('action-bar').style.display = 'none';
});

/* ------------------------------------------------------------------ */
/*  Conversation Threads                                              */
/* ------------------------------------------------------------------ */
const THREAD_KEY = 'locus_threads';
function getThreads() { try { return JSON.parse(localStorage.getItem(THREAD_KEY) || '[]'); } catch { return []; } }
function saveThreads(t) { try { localStorage.setItem(THREAD_KEY, JSON.stringify(t.slice(0, 30))); } catch {} }
function addThread(query, answerData) {
  const threads = getThreads();
  const entry = { id: Date.now(), query: query.trim(), time: new Date().toISOString(), resultCount: (answerData.results || []).length, answerLength: (answerData.answer_text || '').length };
  threads.unshift(entry);
  saveThreads(threads);
  renderThreadNav();
}
function renderThreadNav() {
  const threads = getThreads();
  // Minimal: keep history section visible (it shows queries) — threads reuse that
  // For conversation continuity, answers stay visible below as the user searches new queries
}

/* ------------------------------------------------------------------ */
/*  Follow-up Suggestions                                               */
/* ------------------------------------------------------------------ */
function buildFollowUps(query, results) {
  const base = []; // No fabricated suggestions — only dynamic/contextual when backend supports
  if (results.length > 3) base.unshift({ label: 'Give me this as a table', q: `Present as a table: ${query}` });
  return base.slice(0, 5);
}
function renderFollowUps(query, results) {
  const suggestions = buildFollowUps(query, results);
  // Insert after answer-body
  const actionsRow = $d('action-bar');
  // Create follow-up row after actions if not present
  let followRow = document.getElementById('follow-up-row');
  if (!followRow) {
    followRow = document.createElement('div');
    followRow.id = 'follow-up-row';
    followRow.className = 'follow-up-row';
    actionsRow.insertAdjacentElement('afterend', followRow);
  }
  followRow.innerHTML = `<span class="follow-label">Follow up:</span>` + suggestions.map(s => `<button class="follow-btn" onclick="runExampleFromString('${s.q.replace(/'/g, "\\'")}')">${s.label}</button>`).join('');
}
function runExampleFromString(q) { input.value = q; input.focus(); btn.click(); }

/* ------------------------------------------------------------------ */
/*  Ask about this source                                               */
/* ------------------------------------------------------------------ */
function addSourceAskButton(sourceHtmlString, resultIndex, results) {
  return sourceHtmlString.replace('<div class="source-item">', `<div class="source-item"><button class="source-ask-btn" onclick="askAboutSource(${resultIndex}, ${results.length})">Ask about this source</button>`);
}
// Simpler approach: inject ask buttons after rendering sources
function injectSourceAskButtons(results) {
  const list = $d('sources-list');
  if (!list || !results || !results.length) return;
  const items = list.querySelectorAll('.source-item');
  items.forEach((item, idx) => {
    if (item.querySelector('.source-ask-btn')) return;
    const btn = document.createElement('button');
    btn.className = 'source-ask-btn';
    btn.textContent = 'Ask about this source';
    btn.onclick = () => askAboutSource(results[idx]);
    item.appendChild(btn);
  });
}
function askAboutSource(sourceObj) {
  const title = (sourceObj.source_locator || {}).filename || sourceObj.filename || sourceObj.doc_id || 'this document';
  input.value = `About "${title}": ${input.value.trim() || 'what is this about?'}`;
  input.focus();
  // Show small hint that source is being referenced
  showToast(`Referencing: ${title.slice(0, 50)}`);
}

/* ------------------------------------------------------------------ */
/*  Conversation Threads (integrated)                                   */
/* ------------------------------------------------------------------ */
function buildThreadDisplay(query, data, results) {
  // For conversation continuity: the answer remains visible; follow-ups are shown.
  // We store the conversation entry and keep answers stacked naturally by not clearing them between queries.
  // But our current design clears and shows one answer. To support threads, we add the previous answers to a thread container.
  const threadArea = $d('thread-area');
  const threadContent = $d('thread-content');
  // Create a new thread block with the current query and answer summary
  const queryStr = String(query || '').replace(/</g, '&lt;');
  const block = document.createElement('div');
  block.className = 'thread-block';
  const answerText = (data.answer_text || '').trim();
  const summary = answerText.length > 120 ? answerText.slice(0, 120) + '…' : answerText;
  block.innerHTML = `<div class="thread-query">${queryStr}</div><div class="thread-answer">${summary || '(No verified answer)'}</div>`;
  // Prepend so newest is at top; user can scroll
  threadContent.insertBefore(block, threadContent.firstChild);
  threadArea.hidden = false;
  addThread(query, data);
}

/* ------------------------------------------------------------------ */
/*  Modify renderAnswer to support threads + follow-ups + source ask     */
/* ------------------------------------------------------------------ */
const originalRenderAnswer = renderAnswer;
window.renderAnswer = function(data) {
  originalRenderAnswer(data);
  const q = input.value.trim();
  buildThreadDisplay(q, data, data.results || []);
  renderFollowUps(q, data.results || []);
  setTimeout(() => injectSourceAskButtons(data.results || []), 100);
};

/* ------------------------------------------------------------------ */
/*  Init                                                                */
/* ------------------------------------------------------------------ */
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n') {
    e.preventDefault(); resetToHero();
  }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
    e.preventDefault(); input.focus();
  }
});
showHero();

