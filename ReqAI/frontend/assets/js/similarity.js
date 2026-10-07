/**
 * similarity.js – Phase 6 Semantic Similarity frontend logic.
 *
 * Responsibilities:
 *  - Refresh similarity panel state from meeting object
 *  - Trigger POST /meetings/{id}/similarity/analyze
 *  - Load and render similarity pairs with filters
 *  - Render pair cards with score, status badges, and review buttons
 *  - Submit PATCH /similarity/{id}/review for confirm / not-duplicate
 */

// ── Status display config ────────────────────────────────────────────────────
const SIM_STATUS_CONFIG = {
  POTENTIAL_DUPLICATE: { label: 'Potential Duplicate', color: '#ef4444', icon: 'fas fa-clone' },
  SIMILAR:             { label: 'Similar',             color: '#f97316', icon: 'fas fa-equals' },
  DUPLICATE_CONFIRMED: { label: 'Confirmed Duplicate', color: '#7c3aed', icon: 'fas fa-check-double' },
  NOT_DUPLICATE:       { label: 'Not Duplicate',       color: '#10b981', icon: 'fas fa-xmark-circle' },
  REVIEWED:            { label: 'Reviewed',            color: '#64748b', icon: 'fas fa-eye' },
};

// Cache of all loaded pairs (used for client-side filtering)
let _allSimPairs = [];
let _simCategories = new Set();

// ── Refresh panel state from meeting ─────────────────────────────────────────

function refreshSimilarityPanel(meeting) {
  const btn  = document.getElementById('btn-analyze-sim');
  const hint = document.getElementById('sim-hint');

  if (meeting.requirements_count && meeting.requirements_count > 1) {
    btn.disabled = false;
    hint.textContent = 'Requirements ready. Click to run semantic similarity analysis.';
  } else if (meeting.nlp_status === 'completed') {
    btn.disabled = false;
    hint.textContent = 'NLP complete. Click to analyze for semantic duplicates.';
  } else {
    btn.disabled = true;
    hint.textContent = 'Run NLP extraction first (Requirements tab), then analyze similarity.';
  }
}

// ── Trigger analysis ──────────────────────────────────────────────────────────

async function triggerSimilarityAnalysis() {
  const spinner  = document.getElementById('sim-processing');
  const action   = document.getElementById('sim-action');
  const errorDiv = document.getElementById('sim-error');
  const statsDiv = document.getElementById('sim-stats');
  const badge    = document.getElementById('sim-status-badge');

  spinner.classList.remove('d-none');
  action.classList.add('d-none');
  errorDiv.classList.add('d-none');
  statsDiv.classList.add('d-none');
  badge.textContent = 'analyzing';
  badge.className = 'badge-status badge-transcribing';

  try {
    const result = await apiRequest(`/meetings/${MEETING_ID}/similarity/analyze`, 'POST');

    // Populate stats
    document.getElementById('stat-analyzed').textContent  = result.requirements_analyzed;
    document.getElementById('stat-similar').textContent   = result.similar_count;
    document.getElementById('stat-duplicates').textContent = result.potential_duplicates;
    document.getElementById('stat-confirmed').textContent  = 0;
    document.getElementById('sim-dup-threshold').textContent = result.duplicate_threshold;
    document.getElementById('sim-rev-threshold').textContent = result.review_threshold;

    statsDiv.classList.remove('d-none');
    spinner.classList.add('d-none');
    action.classList.remove('d-none');
    badge.textContent = 'completed';
    badge.className   = 'badge-status badge-completed';

    // Update tab badge
    const countBadge = document.getElementById('sim-count-badge');
    const total = result.similar_count + result.potential_duplicates;
    if (total > 0) {
      countBadge.textContent = total;
      countBadge.classList.remove('d-none');
    }

    const msg = result.potential_duplicates > 0
      ? `Found ${result.potential_duplicates} potential duplicates!`
      : `Analysis complete. ${result.similar_count} similar pairs found.`;
    showToast(msg, result.potential_duplicates > 0 ? 'warning' : 'success');

    await loadSimilarityPairs();

  } catch (err) {
    spinner.classList.add('d-none');
    action.classList.remove('d-none');
    errorDiv.classList.remove('d-none');
    document.getElementById('sim-error-msg').textContent = err.message;
    badge.textContent = 'failed';
    badge.className   = 'badge-status badge-failed';
    showToast(err.message, 'error');
  }
}

// ── Load pairs ────────────────────────────────────────────────────────────────

async function loadSimilarityPairs() {
  try {
    const params = buildFilterParams();
    const url = `/meetings/${MEETING_ID}/similarity` + (params ? `?${params}` : '');
    const data = await apiRequest(url, 'GET');

    _allSimPairs = data.pairs || [];
    _simCategories = new Set();
    _allSimPairs.forEach(p => {
      if (p.requirement_1.category) _simCategories.add(p.requirement_1.category);
      if (p.requirement_2.category) _simCategories.add(p.requirement_2.category);
    });

    // Update summary stats
    document.getElementById('stat-similar').textContent    = data.similar_count;
    document.getElementById('stat-duplicates').textContent  = data.duplicate_count;
    document.getElementById('stat-confirmed').textContent   = data.confirmed_count;

    if (data.total > 0) {
      document.getElementById('sim-stats').classList.remove('d-none');
      document.getElementById('sim-filter-bar').classList.remove('d-none');
      populateCategoryFilter();

      const badge = document.getElementById('sim-status-badge');
      badge.textContent = 'completed';
      badge.className   = 'badge-status badge-completed';
    }

    // Update tab badge
    const countBadge = document.getElementById('sim-count-badge');
    const flagged = data.duplicate_count + data.similar_count;
    if (flagged > 0) {
      countBadge.textContent = flagged;
      countBadge.classList.remove('d-none');
    }

    renderSimilarityPairs(_allSimPairs);

  } catch (err) {
    if (err.message && err.message.includes('404')) return; // no pairs yet
    console.warn('Could not load similarity pairs:', err.message);
  }
}

// ── Filter helpers ────────────────────────────────────────────────────────────

function buildFilterParams() {
  const parts = [];
  const status   = document.getElementById('filter-sim-status')?.value;
  const category = document.getElementById('filter-sim-category')?.value;
  const score    = document.getElementById('filter-sim-score')?.value;
  const speaker  = document.getElementById('filter-sim-speaker')?.value?.trim();
  if (status)   parts.push(`similarity_status=${encodeURIComponent(status)}`);
  if (category) parts.push(`category=${encodeURIComponent(category)}`);
  if (score)    parts.push(`min_score=${encodeURIComponent(score)}`);
  if (speaker)  parts.push(`speaker=${encodeURIComponent(speaker)}`);
  return parts.join('&');
}

function populateCategoryFilter() {
  const sel = document.getElementById('filter-sim-category');
  if (!sel) return;
  const current = sel.value;
  // Keep first "All Categories" option
  while (sel.options.length > 1) sel.remove(1);
  [..._simCategories].sort().forEach(cat => {
    const opt = document.createElement('option');
    opt.value = cat;
    opt.textContent = cat;
    sel.appendChild(opt);
  });
  sel.value = current;
}

async function applySimFilters() {
  await loadSimilarityPairs();
}

// ── Render pairs ──────────────────────────────────────────────────────────────

function renderSimilarityPairs(pairs) {
  const container = document.getElementById('similarity-pairs-container');

  if (!pairs || pairs.length === 0) {
    container.innerHTML = `
      <div class="req-card">
        <div class="card-body text-center text-muted py-4">
          <i class="fas fa-code-compare fa-2x mb-2 d-block" style="opacity:.3;"></i>
          <p class="mb-0">No similarity pairs found.</p>
          <small>Click "Analyze Similarity" to start, or adjust filters above.</small>
        </div>
      </div>`;
    return;
  }

  container.innerHTML = pairs.map(pair => renderPairCard(pair)).join('');
}

function renderPairCard(pair) {
  const cfg     = SIM_STATUS_CONFIG[pair.similarity_status] || SIM_STATUS_CONFIG['SIMILAR'];
  const scorePct = Math.round(pair.similarity_score * 100);
  const scoreColor = scoreColor_(pair.similarity_score);
  const r1 = pair.requirement_1;
  const r2 = pair.requirement_2;

  // Score ring progress (CSS only)
  const dashOffset = Math.round((1 - pair.similarity_score) * 126); // circumference ≈ 126

  const isReviewable = ['POTENTIAL_DUPLICATE', 'SIMILAR', 'REVIEWED'].includes(pair.similarity_status);
  const isConfirmed  = pair.similarity_status === 'DUPLICATE_CONFIRMED';
  const isNotDup     = pair.similarity_status === 'NOT_DUPLICATE';

  return `
    <div class="req-card mb-3" id="sim-pair-${pair.id}">
      <div class="card-header" style="border-left:4px solid ${cfg.color};">
        <span style="font-size:.8rem;font-weight:600;color:${cfg.color};">
          <i class="${cfg.icon} me-1"></i>${cfg.label}
        </span>
        <div class="d-flex align-items-center gap-2">
          <!-- Score ring -->
          <div style="position:relative;width:44px;height:44px;">
            <svg width="44" height="44" viewBox="0 0 44 44" style="transform:rotate(-90deg)">
              <circle cx="22" cy="22" r="18" fill="none" stroke="#e2e8f0" stroke-width="4"/>
              <circle cx="22" cy="22" r="18" fill="none" stroke="${scoreColor}" stroke-width="4"
                stroke-dasharray="126" stroke-dashoffset="${dashOffset}"
                stroke-linecap="round"/>
            </svg>
            <span style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
              font-size:.6rem;font-weight:700;color:${scoreColor};">${scorePct}%</span>
          </div>
        </div>
      </div>
      <div class="card-body" style="padding:.75rem;">
        <!-- Req A -->
        <div class="mb-2">
          <div class="d-flex gap-2 align-items-center mb-1">
            <span class="badge" style="background:#f1f5f9;color:#475569;font-size:.65rem;">REQ-A</span>
            ${r1.category ? `<span class="badge" style="background:${getCategoryColor(r1.category)}22;color:${getCategoryColor(r1.category)};font-size:.65rem;">${r1.category}</span>` : ''}
            <span style="font-size:.72rem;color:var(--text-secondary);"><i class="fas fa-user me-1"></i>${escSim(r1.speaker)}</span>
          </div>
          <p class="mb-0" style="font-size:.85rem;line-height:1.5;background:#f8fafc;padding:.5rem .75rem;border-radius:6px;">
            ${escSim(r1.clean_sentence || r1.sentence)}
          </p>
        </div>
        <!-- Similarity indicator -->
        <div class="text-center my-1" style="font-size:.75rem;color:${cfg.color};">
          <i class="fas fa-arrows-up-down"></i>
          <span style="font-weight:600;">${scorePct}% similarity</span>
          <i class="fas fa-arrows-up-down"></i>
        </div>
        <!-- Req B -->
        <div class="mb-3">
          <div class="d-flex gap-2 align-items-center mb-1">
            <span class="badge" style="background:#f1f5f9;color:#475569;font-size:.65rem;">REQ-B</span>
            ${r2.category ? `<span class="badge" style="background:${getCategoryColor(r2.category)}22;color:${getCategoryColor(r2.category)};font-size:.65rem;">${r2.category}</span>` : ''}
            <span style="font-size:.72rem;color:var(--text-secondary);"><i class="fas fa-user me-1"></i>${escSim(r2.speaker)}</span>
          </div>
          <p class="mb-0" style="font-size:.85rem;line-height:1.5;background:#f8fafc;padding:.5rem .75rem;border-radius:6px;">
            ${escSim(r2.clean_sentence || r2.sentence)}
          </p>
        </div>
        <!-- Review buttons -->
        ${isReviewable ? `
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-danger" onclick="reviewSimilarity(${pair.id}, 'DUPLICATE_CONFIRMED')">
              <i class="fas fa-check-double me-1"></i> Confirm Duplicate
            </button>
            <button class="btn btn-sm btn-outline-success" onclick="reviewSimilarity(${pair.id}, 'NOT_DUPLICATE')">
              <i class="fas fa-xmark me-1"></i> Not Duplicate
            </button>
          </div>
        ` : ''}
        ${isConfirmed ? `
          <div class="alert alert-purple mb-0 py-1 px-2" style="background:#f5f3ff;color:#7c3aed;border:1px solid #ede9fe;font-size:.8rem;border-radius:6px;">
            <i class="fas fa-check-double me-1"></i> Confirmed as duplicate — will be flagged in BRD generation.
            <button class="btn btn-link btn-sm p-0 ms-2" style="font-size:.75rem;color:#7c3aed;" onclick="reviewSimilarity(${pair.id}, 'NOT_DUPLICATE')">Undo</button>
          </div>
        ` : ''}
        ${isNotDup ? `
          <div class="alert alert-success mb-0 py-1 px-2" style="font-size:.8rem;border-radius:6px;">
            <i class="fas fa-check me-1"></i> Marked as not duplicate.
            <button class="btn btn-link btn-sm p-0 ms-2" style="font-size:.75rem;" onclick="reviewSimilarity(${pair.id}, 'DUPLICATE_CONFIRMED')">Undo</button>
          </div>
        ` : ''}
      </div>
    </div>`;
}

// ── Review action ─────────────────────────────────────────────────────────────

async function reviewSimilarity(similarityId, newStatus) {
  try {
    const result = await apiRequest(
      `/similarity/${similarityId}/review?meeting_id=${MEETING_ID}`,
      'PATCH',
      { status: newStatus }
    );

    showToast(result.message, 'success');

    // Refresh the pairs to reflect new status
    await loadSimilarityPairs();

  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ── Colour helpers ────────────────────────────────────────────────────────────

function scoreColor_(score) {
  if (score >= 0.85) return '#ef4444';
  if (score >= 0.65) return '#f97316';
  return '#10b981';
}

function getCategoryColor(category) {
  const COLORS = {
    'Functional':      '#3b82f6', 'Security':        '#ef4444',
    'Performance':     '#f97316', 'Availability':    '#10b981',
    'Usability':       '#8b5cf6', 'Scalability':     '#06b6d4',
    'Reliability':     '#ec4899', 'Maintainability': '#84cc16',
    'Operational':     '#f59e0b', 'Portability':     '#64748b',
    'Legal':           '#a78bfa', 'Non-Functional':  '#94a3b8',
  };
  return COLORS[category] || '#94a3b8';
}

function escSim(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
