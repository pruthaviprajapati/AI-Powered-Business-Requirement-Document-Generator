/**
 * classifier.js – Phase 5 ML Classification frontend logic.
 *
 * Responsibilities:
 *  - Check DistilBERT model status
 *  - Trigger classification via POST /meetings/{id}/classify
 *  - Render classified requirements with category badges
 *  - Display category distribution bar chart
 *  - Refresh classify panel state
 */

// ── Category colour map ──────────────────────────────────────────────────────
const CATEGORY_COLORS = {
  'Functional':      '#3b82f6',
  'Security':        '#ef4444',
  'Performance':     '#f97316',
  'Availability':    '#10b981',
  'Usability':       '#8b5cf6',
  'Scalability':     '#06b6d4',
  'Reliability':     '#ec4899',
  'Maintainability': '#84cc16',
  'Operational':     '#f59e0b',
  'Portability':     '#64748b',
  'Legal':           '#a78bfa',
  'Non-Functional':  '#94a3b8',
  'Unknown':         '#cbd5e1',
};

function getCategoryColor(category) {
  return CATEGORY_COLORS[category] || '#94a3b8';
}

// ── Model status check ───────────────────────────────────────────────────────

async function checkModelStatus() {
  try {
    const data = await apiRequest('/models/status', 'GET');
    const badge = document.getElementById('ml-model-badge');
    const infoDiv = document.getElementById('ml-model-info');
    const untrainedDiv = document.getElementById('ml-model-untrained');

    if (data.status === 'untrained') {
      badge.textContent = 'Not Trained';
      badge.className = 'badge bg-danger';
      infoDiv.classList.add('d-none');
      untrainedDiv.classList.remove('d-none');
    } else {
      badge.textContent = data.status === 'loaded' ? 'Loaded' : 'Available';
      badge.className = data.status === 'loaded' ? 'badge bg-success' : 'badge bg-info';
      infoDiv.classList.remove('d-none');
      untrainedDiv.classList.add('d-none');

      const accEl = document.getElementById('ml-model-accuracy');
      if (data.test_accuracy !== null && data.test_accuracy !== undefined) {
        accEl.textContent = (data.test_accuracy * 100).toFixed(1) + '%';
      } else {
        accEl.textContent = '—';
      }
      document.getElementById('ml-model-labels').textContent = data.num_labels || '—';
      document.getElementById('ml-model-version').textContent = data.version || '—';
    }

    return data.status;
  } catch (err) {
    console.warn('Could not fetch model status:', err.message);
    return 'unknown';
  }
}

// ── Refresh classify panel from meeting object ───────────────────────────────

async function refreshClassifyPanel(meeting) {
  // Load model status in background
  checkModelStatus();

  const btnClassify = document.getElementById('btn-classify');
  const classifyHint = document.getElementById('classify-hint');

  // Enable classify button only if NLP has been run
  if (meeting.requirements_count && meeting.requirements_count > 0) {
    btnClassify.disabled = false;
    classifyHint.textContent = 'Requirements extracted. Click to classify with DistilBERT.';
  } else if (meeting.nlp_status === 'completed') {
    btnClassify.disabled = false;
    classifyHint.textContent = 'NLP complete. Click to classify with DistilBERT.';
  } else {
    btnClassify.disabled = true;
    classifyHint.textContent = 'Run NLP extraction first (Requirements tab), then classify.';
  }
}

// ── Trigger classification ───────────────────────────────────────────────────

async function triggerClassification() {
  const indicator = document.getElementById('classifying-indicator');
  const action    = document.getElementById('classify-action');
  const errorDiv  = document.getElementById('classify-error');
  const statsDiv  = document.getElementById('classify-stats');
  const badge     = document.getElementById('classify-status-badge');

  indicator.classList.remove('d-none');
  action.classList.add('d-none');
  errorDiv.classList.add('d-none');
  statsDiv.classList.add('d-none');
  badge.textContent = 'classifying';
  badge.className = 'badge-status badge-transcribing';

  try {
    const result = await apiRequest(`/meetings/${MEETING_ID}/classify`, 'POST');

    // Update stats
    document.getElementById('stat-classified').textContent = result.classified;
    const numCategories = Object.keys(result.category_breakdown || {}).length;
    document.getElementById('stat-categories').textContent = numCategories;

    statsDiv.classList.remove('d-none');
    indicator.classList.add('d-none');
    action.classList.remove('d-none');
    badge.textContent = 'classified';
    badge.className = 'badge-status badge-completed';

    // Update badge count
    const countBadge = document.getElementById('classify-count-badge');
    countBadge.textContent = result.classified;
    countBadge.classList.remove('d-none');

    showToast(`Classified ${result.classified} requirements!`, 'success');

    // Load results
    await loadClassifiedRequirements();

  } catch (err) {
    indicator.classList.add('d-none');
    action.classList.remove('d-none');
    errorDiv.classList.remove('d-none');
    document.getElementById('classify-error-msg').textContent = err.message;
    badge.textContent = 'failed';
    badge.className = 'badge-status badge-failed';
    showToast(err.message, 'error');
  }
}

// ── Load and render classified requirements ──────────────────────────────────

async function loadClassifiedRequirements() {
  try {
    const data = await apiRequest(`/meetings/${MEETING_ID}/classified-requirements`, 'GET');

    // Update badge
    const countBadge = document.getElementById('classify-count-badge');
    if (data.classified_count > 0) {
      countBadge.textContent = data.classified_count;
      countBadge.classList.remove('d-none');

      // Update status badge
      const badge = document.getElementById('classify-status-badge');
      badge.textContent = 'classified';
      badge.className = 'badge-status badge-completed';

      // Show stats
      document.getElementById('stat-classified').textContent = data.classified_count;
      const numCategories = Object.keys(data.category_breakdown || {}).length;
      document.getElementById('stat-categories').textContent = numCategories;
      document.getElementById('classify-stats').classList.remove('d-none');
    }

    // Render category chart
    if (data.classified_count > 0) {
      renderCategoryChart(data.category_breakdown, data.classified_count);
    }

    // Render requirement cards
    renderClassifiedRequirements(data.requirements);

  } catch (err) {
    console.warn('Could not load classified requirements:', err.message);
  }
}

// ── Category distribution chart (pure CSS bars) ─────────────────────────────

function renderCategoryChart(breakdown, total) {
  const card = document.getElementById('category-chart-card');
  const container = document.getElementById('category-chart-bars');

  if (!breakdown || Object.keys(breakdown).length === 0) {
    card.classList.add('d-none');
    return;
  }

  card.classList.remove('d-none');

  // Sort by count descending
  const sorted = Object.entries(breakdown).sort((a, b) => b[1] - a[1]);
  const max = sorted[0][1];

  container.innerHTML = sorted.map(([category, count]) => {
    const pct = Math.round((count / total) * 100);
    const barWidth = Math.round((count / max) * 100);
    const color = getCategoryColor(category);

    return `
      <div class="mb-2">
        <div class="d-flex justify-content-between align-items-center mb-1">
          <span style="font-size:.8rem;font-weight:600;color:${color}">
            <i class="fas fa-circle me-1" style="font-size:.5rem;"></i>${category}
          </span>
          <span style="font-size:.75rem;color:var(--text-secondary);">${count} (${pct}%)</span>
        </div>
        <div style="background:#f1f5f9;border-radius:4px;height:8px;overflow:hidden;">
          <div style="width:${barWidth}%;height:100%;background:${color};border-radius:4px;
                      transition:width .6s ease;"></div>
        </div>
      </div>
    `;
  }).join('');
}

// ── Render classified requirement cards ──────────────────────────────────────

function renderClassifiedRequirements(requirements) {
  const container = document.getElementById('classified-requirements-container');

  if (!requirements || requirements.length === 0) {
    container.innerHTML = `
      <div class="req-card">
        <div class="card-body text-center text-muted py-4">
          <i class="fas fa-robot fa-2x mb-2 d-block" style="opacity:.3;"></i>
          No classified requirements yet. Click "Classify Requirements" to begin.
        </div>
      </div>`;
    return;
  }

  // Group by category for organised display
  const grouped = {};
  requirements.forEach(req => {
    const cat = req.category || 'Unclassified';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(req);
  });

  // Sort groups: classified first, then unclassified
  const sortedGroups = Object.entries(grouped).sort((a, b) => {
    if (a[0] === 'Unclassified') return 1;
    if (b[0] === 'Unclassified') return -1;
    return b[1].length - a[1].length;
  });

  container.innerHTML = sortedGroups.map(([category, reqs]) => {
    const color = getCategoryColor(category);
    const icon  = getCategoryIcon(category);

    return `
      <div class="req-card mb-3">
        <div class="card-header">
          <h6 class="mb-0 fw-semibold" style="color:${color}">
            <i class="${icon} me-2"></i>${category}
          </h6>
          <span class="badge" style="background:${color};color:#fff;">${reqs.length}</span>
        </div>
        <div class="card-body" style="padding:.75rem;">
          ${reqs.map(req => renderClassifiedCard(req, color)).join('')}
        </div>
      </div>
    `;
  }).join('');
}

function renderClassifiedCard(req, color) {
  const confPct = req.ml_confidence !== null && req.ml_confidence !== undefined
    ? Math.round(req.ml_confidence * 100) + '%'
    : '—';

  const statusClass = req.processing_status === 'classified'
    ? 'badge bg-success'
    : 'badge bg-secondary';

  return `
    <div class="mb-2 p-2" style="background:#f8fafc;border-radius:8px;
         border-left:3px solid ${color};">
      <div class="d-flex justify-content-between align-items-start mb-1">
        <span style="font-size:.75rem;color:var(--text-secondary);">
          <i class="fas fa-user me-1"></i>${escapeHtml(req.speaker)}
        </span>
        <div class="d-flex gap-1 align-items-center">
          ${req.ml_confidence !== null && req.ml_confidence !== undefined ? `
            <span style="font-size:.7rem;color:${color};font-weight:600;">
              ${confPct} confidence
            </span>` : ''}
          <span class="${statusClass}" style="font-size:.65rem;">${req.processing_status}</span>
        </div>
      </div>
      <p class="mb-0" style="font-size:.85rem;line-height:1.5;">
        ${escapeHtml(req.clean_sentence || req.sentence)}
      </p>
    </div>
  `;
}

// ── Category icon helper ─────────────────────────────────────────────────────

function getCategoryIcon(category) {
  const icons = {
    'Functional':      'fas fa-cogs',
    'Security':        'fas fa-shield-halved',
    'Performance':     'fas fa-gauge-high',
    'Availability':    'fas fa-server',
    'Usability':       'fas fa-user-check',
    'Scalability':     'fas fa-expand-arrows-alt',
    'Reliability':     'fas fa-circle-check',
    'Maintainability': 'fas fa-wrench',
    'Operational':     'fas fa-sliders',
    'Portability':     'fas fa-laptop-mobile',
    'Legal':           'fas fa-scale-balanced',
    'Non-Functional':  'fas fa-list',
    'Unknown':         'fas fa-question-circle',
  };
  return icons[category] || 'fas fa-tag';
}

// ── Utility ──────────────────────────────────────────────────────────────────

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
