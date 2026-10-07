/**
 * brd.js – Phase 7 BRD generation frontend logic.
 *
 * Responsibilities:
 *  - Load BRD readiness status via GET /meetings/{id}/brd
 *  - Trigger POST /meetings/{id}/generate-brd
 *  - Show progress spinner and success/error states
 *  - Provide download button linked to GET /brd/{id}/download
 *  - Refresh BRD panel from meeting object
 */

let _currentBRDDocId = null;

// ── Refresh panel from meeting object ─────────────────────────────────────────

function refreshBRDPanel(meeting) {
  // Triggered on page load — load readiness in background
  loadBRDStatus();
}

// ── Load BRD readiness status ─────────────────────────────────────────────────

async function loadBRDStatus() {
  try {
    const data = await apiRequest(`/meetings/${MEETING_ID}/brd`, 'GET');

    const readinessDiv = document.getElementById('brd-readiness');
    const btn          = document.getElementById('btn-generate-brd');
    const hint         = document.getElementById('brd-hint');
    const badge        = document.getElementById('brd-ready-badge');
    const successDiv   = document.getElementById('brd-success');
    const errorDiv     = document.getElementById('brd-error');

    // Populate stats
    document.getElementById('brd-stat-reqs').textContent      = data.requirements_found;
    document.getElementById('brd-stat-open-q').textContent    = data.open_questions;
    document.getElementById('brd-stat-answered-q').textContent = data.answered_questions;
    document.getElementById('brd-readiness-msg').textContent  = data.message || '';
    readinessDiv.classList.remove('d-none');

    if (data.ready) {
      badge.textContent = 'Ready';
      badge.className   = 'badge bg-success';
      btn.disabled      = false;
      hint.textContent  = 'Click to generate the Business Requirement Document.';
    } else {
      badge.textContent = 'Not ready';
      badge.className   = 'badge bg-warning text-dark';
      btn.disabled      = true;
      hint.textContent  = data.message || 'Run NLP processing first.';
    }

    // Show last BRD if one exists
    if (data.last_brd) {
      const doc = data.last_brd;
      _currentBRDDocId = doc.id;
      if (doc.generation_status === 'COMPLETED') {
        successDiv.classList.remove('d-none');
        errorDiv.classList.add('d-none');
        const meta = document.getElementById('brd-meta');
        const ts   = doc.created_at ? new Date(doc.created_at).toLocaleString() : '';
        meta.textContent = `Model: ${doc.model_name || '—'} · Generated: ${ts} · File: ${doc.file_name || '—'}`;
      } else if (doc.generation_status === 'FAILED') {
        errorDiv.classList.remove('d-none');
        document.getElementById('brd-error-msg').textContent = doc.error_message || 'Unknown error.';
      }
    }

  } catch (err) {
    console.warn('BRD status load error:', err.message);
  }
}

// ── Trigger BRD generation ────────────────────────────────────────────────────

async function triggerGenerateBRD() {
  const spinner    = document.getElementById('brd-spinner');
  const successDiv = document.getElementById('brd-success');
  const errorDiv   = document.getElementById('brd-error');
  const btn        = document.getElementById('btn-generate-brd');

  spinner.classList.remove('d-none');
  successDiv.classList.add('d-none');
  errorDiv.classList.add('d-none');
  btn.disabled = true;

  try {
    const doc = await apiRequest(`/meetings/${MEETING_ID}/generate-brd`, 'POST');

    spinner.classList.add('d-none');

    if (doc.generation_status === 'COMPLETED') {
      _currentBRDDocId = doc.id;
      successDiv.classList.remove('d-none');
      btn.disabled = false;

      const meta = document.getElementById('brd-meta');
      const ts   = doc.created_at ? new Date(doc.created_at).toLocaleString() : '';
      meta.textContent = `Model: ${doc.model_name || '—'} · Generated: ${ts} · File: ${doc.file_name || '—'}`;

      showToast('BRD generated successfully!', 'success');
    } else {
      errorDiv.classList.remove('d-none');
      document.getElementById('brd-error-msg').textContent = doc.error_message || 'Generation failed.';
      btn.disabled = false;
      showToast('BRD generation failed.', 'error');
    }

  } catch (err) {
    spinner.classList.add('d-none');
    errorDiv.classList.remove('d-none');
    document.getElementById('brd-error-msg').textContent = err.message;
    btn.disabled = false;
    showToast(err.message, 'error');
  }
}

// ── Download BRD ──────────────────────────────────────────────────────────────

async function downloadBRD() {
  if (!_currentBRDDocId) { showToast('No BRD available to download.', 'warning'); return; }

  try {
    // Use getAccessToken() which reads from CONFIG.TOKEN_KEY = 'reqai_access_token'
    const token = getAccessToken();
    if (!token) { showToast('Session expired. Please login again.', 'error'); return; }

    const url = `${CONFIG.API_BASE_URL}/brd/${_currentBRDDocId}/download`;

    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Download failed.' }));
      throw new Error(err.detail || 'Download failed.');
    }

    const blob     = await response.blob();
    const fileName = `BRD_Meeting_${MEETING_ID}.docx`;
    const link     = document.createElement('a');
    link.href      = URL.createObjectURL(blob);
    link.download  = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);

    showToast('Download started!', 'success');

  } catch (err) {
    showToast(err.message, 'error');
  }
}
