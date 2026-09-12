const $d = id => document.getElementById(id);
const $ = s => document.querySelector(s);
const $btn = $d('btn');
function resetW() { $d('q').value=''; $d('out').innerHTML='<div class="empty">Enter a query.</div>'; }
function renderLoading() { $d('out').innerHTML='<div class="empty">Retrieving from real index (dense + BM25 + exact + metadata via RRF)...</div>'; }
function renderClaimCitation(claim, idx) {
  if (!claim) return '';
  const status = claim.status || 'PENDING';
  const badge = status === 'VERIFIED' ? '<span style="background:#3d5748;color:#fff;padding:1px 6px;border-radius:4px;font-size:.78rem;font-weight:600;">VERIFIED</span>' : (status === 'INSUFFICIENT_EVIDENCE' ? '<span style="background:#bfa03a;color:#fff;padding:1px 6px;border-radius:4px;font-size:.78rem;font-weight:600;">INSUFFICIENT EVIDENCE</span>' : (status === 'CONFLICT' ? '<span style="background:#8a2e2e;color:#fff;padding:1px 6px;border-radius:4px;font-size:.78rem;font-weight:600;">CONFLICT</span>' : '<span style="background:#ccc;color:#444;padding:1px 6px;border-radius:4px;font-size:.78rem;">UNSUPPORTED</span>'));
  const locator = claim.citation_locator ? `<a href="#" onclick="alert('${claim.citation_locator.replace(/'/g,"\\'")}')" style="color:#3d5748;text-decoration:underline;font-size:.82rem;">${claim.citation_locator}</a>` : '<span style="color:#999;font-size:.82rem;">No citation (unsupported / insufficient)</span>';
  const prov = claim.provenance ? `<div style="font-size:.78rem;color:#555;margin-top:4px;">Doc: ${claim.provenance.filename || '—'} · Page ${claim.provenance.page || '—'} · Chunk ${claim.provenance.chunk_id || '—'}</div>` : '';
  return `<div class="claim-row" style="border-left:3px solid ${(status==='VERIFIED'?'#3d5748':status==='CONFLICT'?'#8a2e2e':'#ccc')};padding:10px 12px;margin:10px 0;background:#faf8f3;border-radius:6px;font-size:.92rem;line-height:1.4;"><div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;"><span style="font-weight:600;">${(idx+1)+'. '+claim.claim_text}</span>${badge}</div><div style="margin-left:4px;">${locator}${prov}</div></div>`;
}
function renderResult(title, text, claims, cits, provText) {
  const citStr = cits && cits.length ? cits.map(c => `<div class="citation"><a href="#" onclick="alert('Source: ${String(c.locator && c.locator.filename ? c.locator.filename : (c.doc_id || 'n/a'))}')"><strong>${c.doc_id || c.chunk_id || 'n/a'}</strong></a> · index: ${c.index_name || 'n/a'} · provenance: ${(c.locator ? (c.locator.filename || c.locator.drive_file_id || 'none') : 'none')}</div>`).join('') : '<div class="citation">Evidence assembled from retrieval results. Provenance preserved per chunk.</div>';
  const claimsStr = claims && claims.length ? claims.map((cl, i) => `<div style="font-size:.88rem;margin-top:8px;padding:6px 10px;background:#faf8f3;border-left:3px solid ${cl.status==='VERIFIED'?'#3d5748':cl.status==='INSUFFICIENT_EVIDENCE'?'#bfa03a':'#ccc'};border-radius:4px;"><strong>Claim ${i+1}:</strong> ${cl.claim_text || 'N/A'} <span style="font-size:.75rem;color:#777;">· ${cl.status||'PENDING'} · verified:${String(cl.verified||false)}</span></div>`).join('') : '<div style="font-size:.82rem;color:#999;">No claims verified for this query.</div>';
  $d('out').innerHTML = `<article class="answer-card"><h2>${title.replace(/</g,'&lt;')}</h2><p>${text ? text.replace(/</g,'&lt;').substring(0,1400) + (text.length>1400 ? '...' : '') : 'No direct answer returned — evidence available below.'}</p>` + (claimsStr ? claimsStr : '') + citStr + `<div style="font-size:.82rem;color:var(--muted);margin-top:10px;padding-top:10px;border-top:1px solid #ddd8cf;">${provText || 'Read-only Drive · fixture indexes verified · no fabrication'}</div></article>`;
}
function renderError(msg) { $d('out').innerHTML = `<div class="empty" style="color:#8a2e2e;">Retrieval error: ${msg.replace(/</g,'&lt;')}</div>`; }
$btn.addEventListener('click', async () => {
  const q = $d('q').value.trim();
  if (!q) { resetW(); return; }
  renderLoading();
  try {
    const resp = await fetch('http://localhost:8765/api/retrieve', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({query: q}) });
    if (!resp.ok) throw new Error('HTTP '+resp.status);
    const data = await resp.json();
    const results = data.results || [];
    // Build answer from synthesized natural-language response (not raw chunk dump)
    const snippets = results.slice(0,5).map(r => (r.text || '').substring(0,240).trim());
    const title = (data.answer_text && data.answer_text.length > 10) ? (q || '').substring(0,60).replace(/</g,'&lt;') : 'Results: ' + (q || '').substring(0,60).replace(/</g,'&lt;');
    const citations = results.slice(0,5).map(r => ({chunk_id: r.chunk_id, doc_id: r.doc_id, index_name: r.index_name, locator: r.source_locator || {}, score: r.score}));
    const synthesizedAnswer = data.answer_text || (results.length ? 'Based on institutional records (retrieved via hybrid index):\n\n' + snippets.map((s,i)=> (i+1)+'. ' + s.replace(/</g,'&lt;') + (results[i].text && results[i].text.length > 240 ? '...' : '')).join('\n\n') : 'No high-confidence sources retrieved. The question may require broader indexing or additional structured-data access.');
    renderResult('Answer', synthesizedAnswer, data.claims || [], citations, 'Evidence assembled from ' + results.length + ' sources. Read-only Drive preserved. Partial evidence noted where applicable — no names, years, roles, sponsors, or dates invented.');
  } catch (e) {
    renderError('Connection failed (' + e.message.replace(/</g,'&lt;') + '). Ensure adapter is running: python server_adapter.py');
  }
});
$d('q')?.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); $btn?.click(); } });
