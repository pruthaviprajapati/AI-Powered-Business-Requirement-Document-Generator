/**
 * autopipeline.js – Automatic full pipeline: Audio → BRD
 *
 * When user clicks "Auto BRD" button, this runs:
 * 1. Transcription (faster-whisper)
 * 2. NLP Extraction (spaCy)
 * 3. ML Classification (DistilBERT)
 * 4. Similarity Analysis (Sentence Transformers)
 * 5. AI Validation (Groq)
 * 6. Follow-up Questions (Groq)
 * 7. BRD Generation (Groq + python-docx)
 */

// ── Step status helpers ───────────────────────────────────────────────────────

function _stepRunning(stepId) {
  const el = document.getElementById(stepId);
  if (!el) return;
  el.innerHTML = '<i class="fas fa-spinner fa-spin text-primary"></i> ' + el.textContent.trim();
}

function _stepDone(stepId) {
  const el = document.getElementById(stepId);
  if (!el) return;
  const text = el.textContent.replace(/^[\s\S]*? /, '').trim();
  el.innerHTML = '<i class="fas fa-check-circle text-success"></i> ' + text;
}

function _stepFailed(stepId, reason) {
  const el = document.getElementById(stepId);
  if (!el) return;
  const text = el.textContent.replace(/^[\s\S]*? /, '').trim();
  el.innerHTML = `<i class="fas fa-times-circle text-danger"></i> ${text} <small class="text-muted">(${reason})</small>`;
}

function _stepSkipped(stepId) {
  const el = document.getElementById(stepId);
  if (!el) return;
  const text = el.textContent.replace(/^[\s\S]*? /, '').trim();
  el.innerHTML = '<i class="fas fa-forward text-warning"></i> ' + text + ' (skipped)';
}

// ── Main auto pipeline ────────────────────────────────────────────────────────

async function runAutoPipeline() {
  const card   = document.getElementById('auto-pipeline-card');
  const result = document.getElementById('auto-pipeline-result');
  const errDiv = document.getElementById('auto-pipeline-error');
  const errMsg = document.getElementById('auto-pipeline-error-msg');
  const status = document.getElementById('auto-pipeline-status');
  const btn    = document.getElementById('btn-auto-pipeline');

  // Show the progress card
  card.classList.remove('d-none');
  result.classList.add('d-none');
  errDiv.classList.add('d-none');
  btn.disabled = true;
  status.textContent = 'running...';
  status.className = 'badge bg-info';

  // Scroll to card
  card.scrollIntoView({ behavior: 'smooth', block: 'start' });

  let failed = false;

  // ── STEP 1: Transcription ─────────────────────────────────────
  _stepRunning('step-transcribe');
  try {
    const t = await apiRequest(`/meetings/${MEETING_ID}/transcribe`, 'POST');
    if (t.processing_status === 'completed') {
      _stepDone('step-transcribe');
    } else {
      _stepFailed('step-transcribe', t.processing_error || 'failed');
      failed = true;
    }
  } catch (err) {
    _stepFailed('step-transcribe', err.message.substring(0, 50));
    failed = true;
  }
  if (failed) { _showPipelineError(errDiv, errMsg, status, btn, 'Transcription failed.'); return; }

  // ── STEP 2: NLP ───────────────────────────────────────────────
  _stepRunning('step-nlp');
  try {
    const n = await apiRequest(`/meetings/${MEETING_ID}/process-nlp`, 'POST');
    if (n.nlp_status === 'completed') {
      _stepDone('step-nlp');
    } else {
      _stepFailed('step-nlp', 'failed');
      failed = true;
    }
  } catch (err) {
    _stepFailed('step-nlp', err.message.substring(0, 50));
    failed = true;
  }
  if (failed) { _showPipelineError(errDiv, errMsg, status, btn, 'NLP extraction failed.'); return; }

  // ── STEP 3: ML Classification ─────────────────────────────────
  _stepRunning('step-classify');
  try {
    const c = await apiRequest(`/meetings/${MEETING_ID}/classify`, 'POST');
    if (c.classified > 0) {
      _stepDone('step-classify');
    } else {
      _stepSkipped('step-classify');
    }
  } catch (err) {
    _stepSkipped('step-classify');  // non-blocking
  }

  // ── STEP 4: Similarity ────────────────────────────────────────
  _stepRunning('step-similarity');
  try {
    await apiRequest(`/meetings/${MEETING_ID}/similarity/analyze`, 'POST');
    _stepDone('step-similarity');
  } catch (err) {
    _stepSkipped('step-similarity');  // non-blocking
  }

  // ── STEP 5: Validation ────────────────────────────────────────
  _stepRunning('step-validate');
  try {
    await apiRequest(`/meetings/${MEETING_ID}/validate`, 'POST');
    _stepDone('step-validate');
  } catch (err) {
    _stepSkipped('step-validate');  // non-blocking — Groq may hit rate limit
  }

  // ── STEP 6: Follow-up Questions ───────────────────────────────
  _stepRunning('step-questions');
  try {
    await apiRequest(`/meetings/${MEETING_ID}/follow-up-questions`, 'POST');
    _stepDone('step-questions');
  } catch (err) {
    _stepSkipped('step-questions');  // non-blocking
  }

  // ── STEP 7: BRD Generation ────────────────────────────────────
  _stepRunning('step-brd');
  try {
    const b = await apiRequest(`/meetings/${MEETING_ID}/generate-brd`, 'POST');
    if (b.generation_status === 'COMPLETED') {
      _stepDone('step-brd');
      // Show success
      result.classList.remove('d-none');
      status.textContent = 'complete';
      status.className = 'badge bg-success';
      btn.disabled = false;
      showToast('BRD generated successfully! Switch to BRD tab to download.', 'success');
      // Reload meeting to update all panels
      setTimeout(() => loadMeeting(), 1000);
    } else {
      _stepFailed('step-brd', b.error_message || 'generation failed');
      _showPipelineError(errDiv, errMsg, status, btn, 'BRD generation failed. Check BRD tab.');
    }
  } catch (err) {
    _stepFailed('step-brd', err.message.substring(0, 60));
    _showPipelineError(errDiv, errMsg, status, btn, 'BRD generation failed: ' + err.message.substring(0, 80));
  }
}

function _showPipelineError(errDiv, errMsg, status, btn, message) {
  errDiv.classList.remove('d-none');
  errMsg.textContent = message;
  status.textContent = 'partial';
  status.className = 'badge bg-warning text-dark';
  btn.disabled = false;
}
