/**
 * Speaker Diarization UI module.
 * Handles: diarize button, speaker cards, timeline, summary stats.
 */

// Colour palette — one colour per speaker (cycles if > 8 speakers)
const SPEAKER_COLORS = [
  { bg: '#eef2ff', border: '#4f46e5', text: '#3730a3', badge: '#4f46e5' }, // indigo
  { bg: '#fef3c7', border: '#f59e0b', text: '#92400e', badge: '#f59e0b' }, // amber
  { bg: '#dcfce7', border: '#22c55e', text: '#15803d', badge: '#22c55e' }, // green
  { bg: '#fce7f3', border: '#ec4899', text: '#9d174d', badge: '#ec4899' }, // pink
  { bg: '#e0f2fe', border: '#0ea5e9', text: '#0369a1', badge: '#0ea5e9' }, // sky
  { bg: '#f3e8ff', border: '#a855f7', text: '#6b21a8', badge: '#a855f7' }, // purple
  { bg: '#fff7ed', border: '#f97316', text: '#9a3412', badge: '#f97316' }, // orange
  { bg: '#f0fdf4', border: '#4ade80', text: '#166534', badge: '#4ade80' }, // lime
];

function getSpeakerColor(speakerIndex) {
  return SPEAKER_COLORS[speakerIndex % SPEAKER_COLORS.length];
}

// ── Refresh speaker panel from meeting object ─────────────────────

function refreshSpeakerPanel(m) {
  const diarizeBtn = document.getElementById('btn-diarize');
  const diarizeHint = document.getElementById('diarize-hint');
  const statusBadge = document.getElementById('diarization-status-badge');
  const diarizeAction = document.getElementById('diarize-action');
  const diarizingIndicator = document.getElementById('diarizing-indicator');
  const diarizeError = document.getElementById('diarize-error');
  const speakerCountBadge = document.getElementById('speaker-count-badge');

  // Update status badge
  if (statusBadge) {
    statusBadge.textContent = m.diarization_status || 'pending';
    statusBadge.className = 'badge-status badge-' + (m.diarization_status || 'pending');
  }

  // Enable diarize button only when transcription is complete
  if (diarizeBtn) {
    const canDiarize = m.processing_status === 'completed' && !!m.transcript;
    diarizeBtn.disabled = !canDiarize;
    if (diarizeHint) {
      diarizeHint.textContent = canDiarize
        ? 'Transcript ready. Click to identify speakers.'
        : 'Complete transcription first, then identify speakers.';
    }
  }

  // Hide all sub-panels
  if (diarizingIndicator) diarizingIndicator.classList.add('d-none');
  if (diarizeError) diarizeError.classList.add('d-none');

  const status = m.diarization_status || 'pending';

  if (status === 'diarizing') {
    if (diarizeAction) diarizeAction.classList.add('d-none');
    if (diarizingIndicator) diarizingIndicator.classList.remove('d-none');
    pollDiarizationStatus();
  } else if (status === 'completed' || status === 'skipped') {
    if (diarizeAction) diarizeAction.classList.remove('d-none');
    if (m.speaker_count > 0) {
      if (speakerCountBadge) {
        speakerCountBadge.textContent = m.speaker_count + ' speakers';
        speakerCountBadge.classList.remove('d-none');
      }
      loadSpeakerTranscript();
    }
  } else if (status === 'failed') {
    if (diarizeAction) diarizeAction.classList.remove('d-none');
    if (diarizeError) {
      diarizeError.classList.remove('d-none');
      const errMsg = document.getElementById('diarize-error-msg');
      if (errMsg) errMsg.textContent = m.processing_error || 'Unknown error.';
    }
  } else {
    // pending state
    if (diarizeAction) diarizeAction.classList.remove('d-none');
  }
}

// ── Trigger diarization ───────────────────────────────────────────

async function triggerDiarization() {
  document.getElementById('diarizing-indicator').classList.remove('d-none');
  document.getElementById('diarize-action').classList.add('d-none');
  document.getElementById('diarize-error').classList.add('d-none');

  try {
    const result = await apiRequest(`/meetings/${MEETING_ID}/diarize`, 'POST');
    handleDiarizationResult(result);
    showToast('Speaker identification complete!', 'success');
  } catch (err) {
    document.getElementById('diarizing-indicator').classList.add('d-none');
    document.getElementById('diarize-action').classList.remove('d-none');
    document.getElementById('diarize-error').classList.remove('d-none');
    document.getElementById('diarize-error-msg').textContent = err.message;
    showToast(err.message, 'error');
  }
}

// ── Handle result from diarize endpoint ──────────────────────────

function handleDiarizationResult(result) {
  document.getElementById('diarizing-indicator').classList.add('d-none');
  document.getElementById('diarize-action').classList.remove('d-none');

  const statusBadge = document.getElementById('diarization-status-badge');
  if (statusBadge) {
    statusBadge.textContent = result.diarization_status;
    statusBadge.className = 'badge-status badge-' + result.diarization_status;
  }

  const speakerCountBadge = document.getElementById('speaker-count-badge');
  if (speakerCountBadge && result.speaker_count > 0) {
    speakerCountBadge.textContent = result.speaker_count + ' speakers';
    speakerCountBadge.classList.remove('d-none');
  }

  if (result.segments && result.segments.length > 0) {
    renderSpeakerSegments(result.segments);
    loadSpeakerSummary();
  }
}

// ── Load speaker transcript from API ─────────────────────────────

async function loadSpeakerTranscript() {
  try {
    const data = await apiRequest(`/meetings/${MEETING_ID}/speaker-transcript`, 'GET');
    if (data.segments && data.segments.length > 0) {
      renderSpeakerSegments(data.segments);
      loadSpeakerSummary();
    }
  } catch (err) {
    console.error('Failed to load speaker transcript:', err);
  }
}

// ── Load speaker summary ──────────────────────────────────────────

async function loadSpeakerSummary() {
  try {
    const data = await apiRequest(`/meetings/${MEETING_ID}/speaker-summary`, 'GET');
    renderSpeakerSummary(data);
  } catch (err) {
    console.error('Failed to load speaker summary:', err);
  }
}

// ── Render speaker segment cards ──────────────────────────────────

function renderSpeakerSegments(segments) {
  const container = document.getElementById('speaker-segments-container');
  if (!container) return;

  container.innerHTML = '';
  segments.forEach((seg, index) => {
    const color = getSpeakerColor(seg.speaker_index);
    const card = document.createElement('div');
    card.className = 'speaker-card mb-2';
    card.style.cssText = `
      background: ${color.bg};
      border-left: 4px solid ${color.border};
      border-radius: var(--border-radius-sm);
      padding: 0.875rem 1rem;
    `;
    card.innerHTML = `
      <div class="d-flex align-items-center justify-content-between mb-1">
        <div class="d-flex align-items-center gap-2">
          <span style="
            background:${color.badge};color:#fff;
            font-size:.7rem;font-weight:700;
            padding:.2rem .6rem;border-radius:999px;
          ">${seg.speaker}</span>
          <span style="font-size:.75rem;color:${color.text};font-weight:600;">
            ${seg.start_fmt} – ${seg.end_fmt}
          </span>
        </div>
        <span style="font-size:.72rem;color:var(--text-muted);">
          ${Math.round(seg.end - seg.start)}s
        </span>
      </div>
      <p class="mb-0" style="font-size:.875rem;line-height:1.6;color:var(--text-primary);">
        ${escapeHtml(seg.text)}
      </p>`;
    container.appendChild(card);
  });
}

// ── Render speaker summary stats + timeline ───────────────────────

function renderSpeakerSummary(data) {
  const summaryCard = document.getElementById('speaker-summary-card');
  if (summaryCard) summaryCard.classList.remove('d-none');

  // Stat cards per speaker
  const statsGrid = document.getElementById('speaker-stats-grid');
  if (statsGrid) {
    statsGrid.innerHTML = data.speakers.map(sp => {
      const color = getSpeakerColor(sp.speaker_index);
      return `
        <div class="col-sm-6">
          <div style="background:${color.bg};border:1px solid ${color.border};
               border-radius:var(--border-radius-sm);padding:.75rem;">
            <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem;">
              <span style="width:10px;height:10px;border-radius:50%;background:${color.badge};flex-shrink:0;"></span>
              <strong style="font-size:.8rem;">${sp.speaker}</strong>
            </div>
            <div style="font-size:.75rem;color:var(--text-secondary);">
              ${sp.segment_count} segment${sp.segment_count !== 1 ? 's' : ''} •
              ${sp.total_duration.toFixed(1)}s •
              <strong>${sp.percentage}%</strong>
            </div>
          </div>
        </div>`;
    }).join('');
  }

  // Timeline bar
  const timeline = document.getElementById('speaker-timeline');
  if (timeline && data.total_duration > 0) {
    timeline.innerHTML = data.speakers.map(sp => {
      const color = getSpeakerColor(sp.speaker_index);
      return `<div style="
        flex: ${sp.percentage};
        background: ${color.badge};
        height: 100%;
        title: '${sp.speaker}: ${sp.percentage}%';
      " title="${sp.speaker}: ${sp.percentage}%"></div>`;
    }).join('');
  }

  // Legend
  const legend = document.getElementById('speaker-timeline-legend');
  if (legend) {
    legend.innerHTML = data.speakers.map(sp => {
      const color = getSpeakerColor(sp.speaker_index);
      return `<span style="font-size:.75rem;display:flex;align-items:center;gap:.3rem;">
        <span style="width:10px;height:10px;border-radius:2px;background:${color.badge};flex-shrink:0;"></span>
        ${sp.speaker} (${sp.percentage}%)
      </span>`;
    }).join('');
  }
}

// ── Poll diarization status ───────────────────────────────────────

function pollDiarizationStatus() {
  const interval = setInterval(async () => {
    try {
      const data = await getMeetingByIdAPI(MEETING_ID);
      if (data.diarization_status !== 'diarizing') {
        clearInterval(interval);
        refreshSpeakerPanel(data);
      }
    } catch (err) { clearInterval(interval); }
  }, 4000);
}

// ── Copy speaker transcript ───────────────────────────────────────

async function copySpeakerTranscript() {
  try {
    const data = await apiRequest(`/meetings/${MEETING_ID}/speaker-transcript`, 'GET');
    if (data.speaker_transcript) {
      navigator.clipboard.writeText(data.speaker_transcript)
        .then(() => showToast('Speaker transcript copied!', 'success'));
    } else {
      showToast('No speaker transcript available.', 'warning');
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ── Helper ────────────────────────────────────────────────────────

function escapeHtml(text) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(text || ''));
  return div.innerHTML;
}
