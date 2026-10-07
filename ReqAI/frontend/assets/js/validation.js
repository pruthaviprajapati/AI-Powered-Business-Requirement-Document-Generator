/**
 * validation.js – Phase 7 Validation & Follow-up Questions frontend logic.
 *
 * Responsibilities:
 *  - Refresh validation panel state from meeting data
 *  - Trigger POST /meetings/{id}/validate
 *  - Render per-requirement validation cards
 *  - Trigger POST /meetings/{id}/follow-up-questions
 *  - Render follow-up questions with answer/skip controls
 *  - Submit PATCH /follow-up-questions/{id}
 */

// ── Validation status config ──────────────────────────────────────────────────
const VAL_STATUS = {
  valid:               { label: 'Valid',              color: '#10b981', icon: 'fas fa-check-circle' },
  needs_clarification: { label: 'Needs Clarification', color: '#f59e0b', icon: 'fas fa-question-circle' },
  ambiguous:           { label: 'Ambiguous',           color: '#f97316', icon: 'fas fa-triangle-exclamation' },
  incomplete:          { label: 'Incomplete',          color: '#ef4444', icon: 'fas fa-circle-xmark' },
};

let _validationDone = false;

// ── Refresh panel from meeting object ─────────────────────────────────────────

function refreshValidatePanel(meeting) {
  const btn  = document.getElementById('btn-validate');
  const hint = document.getElementById('validation-hint');

  if (meeting.requirements_count && meeting.requirements_count > 0) {
    btn.disabled = false;
    hint.textContent = 'Requirements ready. Click to validate with Groq AI.';
  } else if (meeting.nlp_status === 'completed') {
    btn.disabled = false;
    hint.textContent = 'NLP complete. Click to validate with Groq AI.';
  } else {
    btn.disabled = true;
    hint.textContent = 'Run NLP extraction first (Requirements tab).';
  }

  // Load existing follow-up questions silently
  loadFollowUpQuestions();
}

// ── Load validation tab (called on tab switch) ────────────────────────────────

async function loadValidationTab() {
  await loadFollowUpQuestions();
}

// ── Trigger validation ────────────────────────────────────────────────────────

async function triggerValidation() {
  const spinner = document.getElementById('validation-spinner');
  const action  = document.getElementById('validation-action');
  const errDiv  = document.getElementById('validation-error');
  const summary = document.getElementById('validation-summary');
  const badge   = document.getElementById('validation-status-badge');

  spinner.classList.remove('d-none');
  action.classList.add('d-none');
  errDiv.classList.add('d-none');
  summary.classList.add('d-none');
  badge.textContent = 'validating';
  badge.className = 'badge-status badge-transcribing';

  try {
    const result = await apiRequest(`/meetings/${MEETING_ID}/validate`, 'POST');

    // Stats
    document.getElementById('val-stat-valid').textContent     = result.valid_count;
    document.getElementById('val-stat-clarify').textContent   = result.needs_clarification_count;
    document.getElementById('val-stat-ambiguous').textContent = result.ambiguous_count;
    document.getElementById('val-stat-incomplete').textContent = result.incomplete_count;
    const qPct = Math.round((result.overall_quality || 0) * 100);
    document.getElementById('val-overall-quality').textContent = qPct + '%';
    document.getElementById('val-summary-text').textContent   = result.summary || '';

    summary.classList.remove('d-none');
    spinner.classList.add('d-none');
    action.classList.remove('d-none');
    badge.textContent = 'completed';
    badge.className   = 'badge-status badge-completed';

    const issueCount = (result.needs_clarification_count || 0) + (result.ambiguous_count || 0) + (result.incomplete_count || 0);
    const countBadge = document.getElementById('validate-count-badge');
    if (issueCount > 0) { countBadge.textContent = issueCount; countBadge.classList.remove('d-none'); }

    _validationDone = true;
    document.getElementById('btn-generate-questions').disabled = false;
    document.getElementById('fq-hint').textContent = 'Click to generate follow-up questions based on validation results.';

    renderValidationResults(result.requirements || []);
    showToast(`Validation complete. ${issueCount} issues found.`, issueCount > 0 ? 'warning' : 'success');

  } catch (err) {
    spinner.classList.add('d-none');
    action.classList.remove('d-none');
    errDiv.classList.remove('d-none');
    document.getElementById('validation-error-msg').textContent = err.message;
    badge.textContent = 'failed';
    badge.className   = 'badge-status badge-failed';
    showToast(err.message, 'error');
  }
}

// ── Render validation result cards ────────────────────────────────────────────

function renderValidationResults(requirements) {
  const container = document.getElementById('validation-results-container');
  if (!requirements.length) { container.innerHTML = ''; return; }

  container.innerHTML = requirements.map(r => {
    const cfg    = VAL_STATUS[r.validation_status] || VAL_STATUS['needs_clarification'];
    const clarPct = Math.round((r.clarity_score || 0) * 100);
    const compPct = Math.round((r.completeness_score || 0) * 100);

    return `
      <div class="req-card mb-2" style="border-left:3px solid ${cfg.color};">
        <div class="card-body py-2 px-3">
          <div class="d-flex justify-content-between align-items-start mb-1">
            <span style="font-size:.72rem;font-weight:600;color:${cfg.color};">
              <i class="${cfg.icon} me-1"></i>${cfg.label}
            </span>
            <div class="d-flex gap-2" style="font-size:.72rem;color:var(--text-secondary);">
              <span>Clarity: <strong>${clarPct}%</strong></span>
              <span>Complete: <strong>${compPct}%</strong></span>
            </div>
          </div>
          <p class="mb-1" style="font-size:.84rem;line-height:1.5;">${escVal(r.sentence || '—')}</p>
          ${r.issues && r.issues.length ? `
            <div style="font-size:.75rem;color:#b45309;">
              <i class="fas fa-exclamation-triangle me-1"></i>
              ${r.issues.map(i => escVal(i)).join(' · ')}
            </div>` : ''}
          ${r.missing_information && r.missing_information.length ? `
            <div style="font-size:.75rem;color:#9a3412;">
              <i class="fas fa-circle-dot me-1"></i>
              Missing: ${r.missing_information.map(m => escVal(m)).join(', ')}
            </div>` : ''}
          ${r.suggestion ? `
            <div style="font-size:.75rem;color:#1e40af;margin-top:.25rem;">
              <i class="fas fa-lightbulb me-1"></i>${escVal(r.suggestion)}
            </div>` : ''}
        </div>
      </div>`;
  }).join('');
}

// ── Generate follow-up questions ──────────────────────────────────────────────

async function triggerGenerateQuestions() {
  const spinner = document.getElementById('fq-spinner');
  const action  = document.getElementById('fq-action');
  const errDiv  = document.getElementById('fq-error');

  spinner.classList.remove('d-none');
  action.classList.add('d-none');
  errDiv.classList.add('d-none');

  try {
    const result = await apiRequest(`/meetings/${MEETING_ID}/follow-up-questions`, 'POST');
    spinner.classList.add('d-none');
    action.classList.remove('d-none');

    const badge = document.getElementById('fq-count-badge');
    badge.textContent = result.total;
    badge.classList.remove('d-none');

    showToast(`Generated ${result.total} follow-up questions.`, 'success');
    renderFollowUpQuestions(result.questions || []);

  } catch (err) {
    spinner.classList.add('d-none');
    action.classList.remove('d-none');
    errDiv.classList.remove('d-none');
    document.getElementById('fq-error-msg').textContent = err.message;
    showToast(err.message, 'error');
  }
}

// ── Load existing follow-up questions ─────────────────────────────────────────

async function loadFollowUpQuestions() {
  try {
    const result = await apiRequest(`/meetings/${MEETING_ID}/follow-up-questions`, 'GET');
    if (result.total > 0) {
      const badge = document.getElementById('fq-count-badge');
      badge.textContent = result.total;
      badge.classList.remove('d-none');
      document.getElementById('btn-generate-questions').disabled = false;
      document.getElementById('fq-hint').textContent = `${result.open_count} open, ${result.answered_count} answered.`;
    }
    renderFollowUpQuestions(result.questions || []);
  } catch (err) {
    // No questions yet — silent
  }
}

// ── Render follow-up question cards ──────────────────────────────────────────

function renderFollowUpQuestions(questions) {
  const container = document.getElementById('fq-list-container');
  if (!questions.length) { container.innerHTML = ''; return; }

  const PRIORITY_COLOR = { HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#10b981' };

  container.innerHTML = questions.map(q => {
    const pColor = PRIORITY_COLOR[q.priority] || '#94a3b8';
    const isAnswered = q.status === 'ANSWERED';
    const isSkipped  = q.status === 'SKIPPED';

    return `
      <div class="req-card mb-2" id="fq-card-${q.id}">
        <div class="card-body py-2 px-3">
          <div class="d-flex justify-content-between align-items-start mb-1">
            <span class="badge" style="background:${pColor}22;color:${pColor};font-size:.65rem;">${q.priority}</span>
            <span class="badge ${isAnswered ? 'bg-success' : isSkipped ? 'bg-secondary' : 'bg-warning text-dark'}" style="font-size:.65rem;">
              ${q.status}
            </span>
          </div>
          <p class="fw-semibold mb-1" style="font-size:.85rem;">${escVal(q.question)}</p>
          ${q.reason ? `<p class="mb-2" style="font-size:.75rem;color:var(--text-secondary);">${escVal(q.reason)}</p>` : ''}

          ${isAnswered && q.answer ? `
            <div class="p-2 rounded mb-2" style="background:#f0fdf4;font-size:.82rem;color:#166534;">
              <i class="fas fa-check me-1"></i><strong>Answer:</strong> ${escVal(q.answer)}
            </div>` : ''}

          ${!isAnswered && !isSkipped ? `
            <div class="d-flex gap-2 mt-2">
              <input type="text" id="fq-input-${q.id}" class="form-control-custom" style="font-size:.8rem;" placeholder="Type your answer...">
              <button class="btn btn-sm btn-success" onclick="submitAnswer(${q.id})">
                <i class="fas fa-check me-1"></i>Answer
              </button>
              <button class="btn btn-sm btn-outline-secondary" onclick="skipQuestion(${q.id})">Skip</button>
            </div>` : ''}

          ${isAnswered ? `
            <button class="btn btn-link btn-sm p-0 mt-1" style="font-size:.75rem;" onclick="reopenQuestion(${q.id})">
              <i class="fas fa-pencil me-1"></i>Edit answer
            </button>` : ''}
        </div>
      </div>`;
  }).join('');
}

// ── Question actions ──────────────────────────────────────────────────────────

async function submitAnswer(questionId) {
  const input = document.getElementById(`fq-input-${questionId}`);
  const answer = input?.value?.trim();
  if (!answer) { showToast('Please type an answer first.', 'warning'); return; }

  try {
    await apiRequest(`/follow-up-questions/${questionId}`, 'PATCH', { answer, status: 'ANSWERED' });
    showToast('Answer saved.', 'success');
    await loadFollowUpQuestions();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function skipQuestion(questionId) {
  try {
    await apiRequest(`/follow-up-questions/${questionId}`, 'PATCH', { status: 'SKIPPED' });
    showToast('Question skipped.', 'info');
    await loadFollowUpQuestions();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function reopenQuestion(questionId) {
  try {
    await apiRequest(`/follow-up-questions/${questionId}`, 'PATCH', { status: 'OPEN', answer: '' });
    await loadFollowUpQuestions();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ── Utility ───────────────────────────────────────────────────────────────────

function escVal(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
