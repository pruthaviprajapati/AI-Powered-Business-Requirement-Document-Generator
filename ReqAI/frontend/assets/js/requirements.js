/**
 * Requirements NLP UI module – Phase 4.
 * Handles: NLP trigger, requirement card rendering,
 *          token/lemma/entity expandable views, status management.
 */

// ── Refresh requirements panel from meeting object ────────────────

function refreshRequirementsPanel(m) {
  const btn        = document.getElementById('btn-process-nlp');
  const hint       = document.getElementById('nlp-hint');
  const statusBadge = document.getElementById('nlp-status-badge');
  const reqBadge   = document.getElementById('req-count-badge');

  // Enable button only when transcript exists
  const hasTranscript = !!(m.transcript || m.speaker_transcript);
  if (btn)  btn.disabled = !hasTranscript;
  if (hint) hint.textContent = hasTranscript
    ? 'Click to run NLP and extract requirement candidates.'
    : 'Complete transcription first, then extract requirements.';

  // Status badge
  const nlpStatus = m.nlp_status || 'pending';
  if (statusBadge) {
    statusBadge.textContent  = nlpStatus;
    statusBadge.className    = 'badge-status badge-' + nlpStatus;
  }

  // Hide sub-panels
  _hide('nlp-processing');
  _hide('nlp-error');

  if (nlpStatus === 'processing') {
    _hide('nlp-action');
    _show('nlp-processing');
    pollNLPStatus();
  } else if (nlpStatus === 'completed') {
    _show('nlp-action');
    if (m.requirements_count > 0) {
      if (reqBadge) {
        reqBadge.textContent = m.requirements_count;
        reqBadge.classList.remove('d-none');
      }
      loadRequirements();
    }
  } else if (nlpStatus === 'failed') {
    _show('nlp-action');
    _show('nlp-error');
    const errEl = document.getElementById('nlp-error-msg');
    if (errEl) errEl.textContent = m.processing_error || 'Unknown error.';
  } else {
    _show('nlp-action');
  }
}

// ── Trigger NLP ───────────────────────────────────────────────────

async function triggerNLP() {
  _show('nlp-processing');
  _hide('nlp-action');
  _hide('nlp-error');

  try {
    const result = await apiRequest(`/meetings/${MEETING_ID}/process-nlp`, 'POST');
    handleNLPResult(result);
    showToast(`Extracted ${result.candidate_count} requirement candidates!`, 'success');
  } catch (err) {
    _hide('nlp-processing');
    _show('nlp-action');
    _show('nlp-error');
    const errEl = document.getElementById('nlp-error-msg');
    if (errEl) errEl.textContent = err.message;
    showToast(err.message, 'error');
  }
}

// ── Handle NLP result ─────────────────────────────────────────────

function handleNLPResult(result) {
  _hide('nlp-processing');
  _show('nlp-action');

  // Update status badge
  const statusBadge = document.getElementById('nlp-status-badge');
  if (statusBadge) {
    statusBadge.textContent = result.nlp_status;
    statusBadge.className   = 'badge-status badge-' + result.nlp_status;
  }

  // Stats
  _show('nlp-stats');
  const statSentences = document.getElementById('stat-total-sentences');
  const statCandidates = document.getElementById('stat-candidates');
  if (statSentences)  statSentences.textContent  = result.total_sentences;
  if (statCandidates) statCandidates.textContent = result.candidate_count;

  // Tab badge
  const reqBadge = document.getElementById('req-count-badge');
  if (reqBadge) {
    reqBadge.textContent = result.candidate_count;
    reqBadge.classList.remove('d-none');
  }

  if (result.candidate_count > 0) {
    loadRequirements();
  } else {
    const container = document.getElementById('requirements-container');
    if (container) {
      container.innerHTML = `
        <div class="empty-state">
          <i class="fas fa-list-check"></i>
          <h5>No Requirement Candidates Found</h5>
          <p>The transcript did not contain recognisable requirement statements.</p>
        </div>`;
    }
  }
}

// ── Load requirements from API ────────────────────────────────────

async function loadRequirements() {
  try {
    const data = await apiRequest(`/meetings/${MEETING_ID}/requirements`, 'GET');

    // Update stats
    _show('nlp-stats');
    const statCandidates = document.getElementById('stat-candidates');
    if (statCandidates) statCandidates.textContent = data.total;

    renderRequirementCards(data.requirements);
  } catch (err) {
    console.error('Failed to load requirements:', err);
  }
}

// ── Render requirement candidate cards ───────────────────────────

function renderRequirementCards(requirements) {
  const container = document.getElementById('requirements-container');
  if (!container) return;

  if (!requirements || requirements.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <i class="fas fa-list-check"></i>
        <h5>No Requirements Found</h5>
        <p>Run NLP processing to extract requirement candidates.</p>
      </div>`;
    return;
  }

  container.innerHTML = requirements.map((req, idx) => {
    const scoreColor = req.confidence_score >= 0.75 ? '#22c55e'
                     : req.confidence_score >= 0.5  ? '#f59e0b'
                     : '#94a3b8';
    const scoreLabel = req.confidence_score >= 0.75 ? 'High'
                     : req.confidence_score >= 0.5  ? 'Medium' : 'Low';

    const entitiesHtml = (req.entities || []).length > 0
      ? `<div class="mt-2">
           <span style="font-size:.7rem;font-weight:600;color:var(--text-muted);
                  text-transform:uppercase;letter-spacing:.05em;">Entities</span>
           <div class="d-flex flex-wrap gap-1 mt-1">
             ${(req.entities || []).map(e =>
               `<span class="nlp-tag entity-tag">${escapeHtml(e.text)}
                 <span class="nlp-label">${e.label}</span></span>`
             ).join('')}
           </div>
         </div>`
      : '';

    const lemmasHtml = (req.lemmas || []).length > 0
      ? `<div class="mt-2" id="lemmas-${req.id}" style="display:none;">
           <span style="font-size:.7rem;font-weight:600;color:var(--text-muted);
                  text-transform:uppercase;letter-spacing:.05em;">Key Lemmas</span>
           <div class="d-flex flex-wrap gap-1 mt-1">
             ${(req.lemmas || []).slice(0, 15).map(l =>
               `<span class="nlp-tag lemma-tag">${escapeHtml(l)}</span>`
             ).join('')}
           </div>
         </div>`
      : '';

    const tokensHtml = (req.tokens || []).length > 0
      ? `<div class="mt-2" id="tokens-${req.id}" style="display:none;">
           <span style="font-size:.7rem;font-weight:600;color:var(--text-muted);
                  text-transform:uppercase;letter-spacing:.05em;">POS Tags</span>
           <div class="d-flex flex-wrap gap-1 mt-1">
             ${(req.tokens || []).slice(0, 12).map(t =>
               `<span class="nlp-tag pos-tag">
                  ${escapeHtml(t.text)}
                  <span class="nlp-label">${t.pos}</span>
                </span>`
             ).join('')}
           </div>
         </div>`
      : '';

    return `
      <div class="req-card mb-2 requirement-card" id="req-card-${req.id}">
        <div class="card-body" style="padding:1rem;">
          <!-- Header row -->
          <div class="d-flex align-items-start justify-content-between mb-2">
            <div class="d-flex align-items-center gap-2 flex-wrap">
              <span class="badge-status badge-active" style="font-size:.65rem;">
                #${idx + 1}
              </span>
              <span style="
                font-size:.72rem;padding:.2rem .55rem;border-radius:999px;
                background:#f1f5f9;color:var(--text-secondary);font-weight:500;">
                <i class="fas fa-user me-1"></i>${escapeHtml(req.speaker)}
              </span>
              ${req.category
                ? `<span class="badge-status badge-processing" style="font-size:.65rem;">
                     ${escapeHtml(req.category)}
                   </span>`
                : `<span style="font-size:.65rem;color:var(--text-muted);">
                     Unclassified — Phase 5
                   </span>`
              }
            </div>
            <div class="d-flex align-items-center gap-1" style="flex-shrink:0;">
              <span style="
                font-size:.7rem;font-weight:700;
                color:${scoreColor};white-space:nowrap;">
                ${scoreLabel} (${req.confidence_score})
              </span>
            </div>
          </div>

          <!-- Sentence -->
          <p class="mb-2" style="font-size:.9rem;line-height:1.6;font-weight:500;">
            "${escapeHtml(req.sentence)}"
          </p>

          <!-- Entities always visible -->
          ${entitiesHtml}

          <!-- Expandable: lemmas + POS -->
          ${lemmasHtml}${tokensHtml}

          <!-- Expand / collapse controls -->
          <div class="mt-2 d-flex gap-2">
            ${(req.lemmas || []).length > 0
              ? `<button class="btn btn-sm btn-outline-secondary nlp-expand-btn"
                   onclick="toggleNLPView('lemmas-${req.id}', this)"
                   style="font-size:.72rem;padding:.2rem .5rem;">
                   <i class="fas fa-font me-1"></i>Lemmas
                 </button>`
              : ''}
            ${(req.tokens || []).length > 0
              ? `<button class="btn btn-sm btn-outline-secondary nlp-expand-btn"
                   onclick="toggleNLPView('tokens-${req.id}', this)"
                   style="font-size:.72rem;padding:.2rem .5rem;">
                   <i class="fas fa-tags me-1"></i>POS Tags
                 </button>`
              : ''}
          </div>
        </div>
      </div>`;
  }).join('');
}

// ── Toggle expandable NLP sections ───────────────────────────────

function toggleNLPView(elementId, btn) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const isHidden = el.style.display === 'none' || el.style.display === '';
  el.style.display = isHidden ? 'block' : 'none';
  btn.classList.toggle('active', isHidden);
}

// ── Poll NLP status ───────────────────────────────────────────────

function pollNLPStatus() {
  const interval = setInterval(async () => {
    try {
      const data = await getMeetingByIdAPI(MEETING_ID);
      if (data.nlp_status !== 'processing') {
        clearInterval(interval);
        refreshRequirementsPanel(data);
      }
    } catch (err) { clearInterval(interval); }
  }, 3000);
}

// ── Helpers ───────────────────────────────────────────────────────

function _show(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('d-none');
}

function _hide(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('d-none');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(text || ''));
  return div.innerHTML;
}
