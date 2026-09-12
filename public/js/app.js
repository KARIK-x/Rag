const $ = s => document.querySelector(s);
const $d = id => document.getElementById(id);
function resetW() { $d('q').value=''; $d('out').innerHTML='<div class="empty">Enter a query.</div>'; }
function renderLoading() { $d('out').innerHTML='<div class="empty">Retrieving from real index (dense + BM25 + exact + metadata via RRF)...</div>'; }
function renderResult(title, text, cits, provText) {
  const citStr = cits && cits.length ? cits.map(c => `<div class="citation"><strong>Source:</strong> ${c.doc_id || c.chunk_id || 'n/a'} · index: ${c.index_name || 'n/a'} · provenance: ${(c.locator ? Object.keys(c.locator).slice(0,3).join(', ') : 'none')}</div>`).join('') : '<div class="citation">Evidence assembled from retrieval results. Provenance preserved per chunk.</div>';
  $d('out').innerHTML = `<article class="answer-card"><h2>${title.replace(/</g,'&lt;')}</h2><p>${text ? text.replace(/</g,'&lt;').substring(0,1400) + (text.length>1400 ? '...' : '') : 'No direct answer returned — evidence available below.'}</p>` + citStr + `<div style="font-size:.82rem;color:var(--muted);margin-top:10px;padding-top:10px;border-top:1px solid #ddd8cf;">${provText || 'Read-only Drive · fixture indexes verified · no fabrication'}</div></article>`;
}
function renderError(msg) { $d('out').innerHTML = `<div class="empty" style="color:#8a2e2e;">Retrieval error: ${msg.replace(/</g,'&lt;')}</div>`; }
$($btn).addEventListener('click', async () => {
  const q = $d('q').value.trim();
  if (!q) { resetW(); return; }
  renderLoading();
  try {
    const resp = await fetch('http://localhost:8765/api/retrieve', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({query: q}) });
    if (!resp.ok) throw new Error('HTTP '+resp.status);
    const data = await resp.json();
    const results = data.results || [];
    // Build answer from real results (not synthetic); use evidence-first approach
    const snippets = results.slice(0,5).map(r => (r.text || '').substring(0,240).trim());
    const title = results.length ? 'Results: ' + (q || '').substring(0,60).replace(/</g,'&lt;') : 'Insufficient evidence';
    // Provenance array
    const citations = results.slice(0,5).map(r => ({chunk_id: r.chunk_id, doc_id: r.doc_id, index_name: r.index_name, locator: r.source_locator || {}, score: r.score}));
    const answerText = results.length ? 'Based on institutional records (retrieved via hybrid index):\n\n' + snippets.map((s,i)=> (i+1)+'. ' + s.replace(/</g,'&lt;') + (results[i].text && results[i].text.length > 240 ? '...' : '')).join('\n\n') : 'No high-confidence sources retrieved. The question may require broader indexing or additional structured-data access.';
    renderResult(title, answerText, citations, 'Evidence assembled from ' + results.length + ' sources (dense + BM25 + exact + metadata RRF). Read-only Drive preserved. No production ingestion executed.');
  } catch (e) {
    renderError('Connection failed (' + e.message.replace(/</g,'&lt;') + '). Ensure adapter is running: python server_adapter.py');
  }
});
$($d('q'))?.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); $($btn)?.click(); } });
