/**
 * Audio Recorder – wraps the browser MediaRecorder API.
 * Handles: microphone permission, recording, timers, preview, and upload.
 */

let mediaRecorder = null;
let audioChunks = [];
let recordingTimerInterval = null;
let recordingSeconds = 0;
let recordedBlob = null;

// ── Start Recording ───────────────────────────────────────────────

async function startRecording() {
  // Request microphone permission
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    beginRecording(stream);
    document.getElementById('mic-permission-warning').classList.add('d-none');
  } catch (err) {
    console.error('Microphone error:', err);
    document.getElementById('mic-permission-warning').classList.remove('d-none');
    document.getElementById('recording-status').textContent =
      'Microphone access denied. Please allow microphone in browser settings.';
    showToast('Microphone permission denied.', 'error');
  }
}

function beginRecording(stream) {
  audioChunks = [];
  recordedBlob = null;

  // Prefer webm/opus; fall back to whatever the browser supports
  const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus'
    : MediaRecorder.isTypeSupported('audio/webm')
    ? 'audio/webm'
    : '';

  const options = mimeType ? { mimeType } : {};
  mediaRecorder = new MediaRecorder(stream, options);

  mediaRecorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) {
      audioChunks.push(event.data);
    }
  };

  mediaRecorder.onstop = () => {
    recordedBlob = new Blob(audioChunks, { type: mimeType || 'audio/webm' });
    const audioUrl = URL.createObjectURL(recordedBlob);
    document.getElementById('recorded-audio').src = audioUrl;
    document.getElementById('recorded-preview').classList.remove('d-none');
    document.getElementById('recording-status').textContent =
      'Recording complete. Preview below.';
    // Stop all tracks to release microphone
    stream.getTracks().forEach(t => t.stop());
  };

  mediaRecorder.start(1000); // collect data every 1 second

  // Update UI
  document.getElementById('btn-record').classList.add('d-none');
  document.getElementById('btn-stop').classList.remove('d-none');
  document.getElementById('recording-timer').classList.remove('d-none');
  document.getElementById('recorded-preview').classList.add('d-none');
  document.getElementById('recording-status').textContent = 'Recording in progress...';

  // Start timer
  recordingSeconds = 0;
  updateTimerDisplay();
  recordingTimerInterval = setInterval(() => {
    recordingSeconds++;
    updateTimerDisplay();
  }, 1000);
}

// ── Stop Recording ────────────────────────────────────────────────

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  clearInterval(recordingTimerInterval);

  document.getElementById('btn-stop').classList.add('d-none');
  document.getElementById('btn-record').classList.remove('d-none');
  document.getElementById('recording-timer').classList.add('d-none');
}

// ── Discard Recording ─────────────────────────────────────────────

function discardRecording() {
  recordedBlob = null;
  audioChunks = [];
  document.getElementById('recorded-preview').classList.add('d-none');
  document.getElementById('recorded-audio').src = '';
  document.getElementById('recording-status').textContent = 'Press the mic to start';
}

// ── Submit Recording to Backend ───────────────────────────────────

async function submitRecording() {
  if (!recordedBlob) {
    showToast('No recording found.', 'warning');
    return;
  }
  if (!MEETING_ID) {
    showToast('Meeting ID not found.', 'error');
    return;
  }

  showLoading();
  try {
    const formData = new FormData();
    formData.append('file', recordedBlob, 'recording.webm');

    const token = getAccessToken();
    const response = await fetch(
      `${CONFIG.API_BASE_URL}/meetings/${MEETING_ID}/recording`,
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      }
    );

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Upload failed');
    }

    const data = await response.json();
    showToast('Recording uploaded! Starting Auto Pipeline...', 'success');
    discardRecording();
    await loadMeeting(); // refresh the page state
    // Auto-trigger the full pipeline after recording upload
    setTimeout(() => {
      if (typeof runAutoPipeline === 'function') {
        runAutoPipeline();
      }
    }, 1500);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    hideLoading();
  }
}

// ── File Upload Handlers ──────────────────────────────────────────

let selectedFile = null;

function handleFileSelect(file) {
  if (!file) return;

  const allowedExts = ['.mp3', '.wav', '.m4a', '.webm', '.ogg', '.flac'];
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

  if (!allowedExts.includes(ext)) {
    showToast(`File type "${ext}" not supported.`, 'error');
    return;
  }

  const maxBytes = 100 * 1024 * 1024;
  if (file.size > maxBytes) {
    showToast('File exceeds 100 MB limit.', 'error');
    return;
  }

  selectedFile = file;
  document.getElementById('selected-file-name').textContent = file.name;
  document.getElementById('selected-file-size').textContent =
    '(' + formatFileSize(file.size) + ')';
  document.getElementById('selected-file-info').classList.remove('d-none');
}

function clearSelectedFile() {
  selectedFile = null;
  document.getElementById('selected-file-info').classList.add('d-none');
  document.getElementById('audio-file-input').value = '';
}

async function uploadSelectedFile() {
  if (!selectedFile) {
    showToast('No file selected.', 'warning');
    return;
  }

  showLoading();
  try {
    const formData = new FormData();
    formData.append('file', selectedFile);

    const token = getAccessToken();
    const response = await fetch(
      `${CONFIG.API_BASE_URL}/meetings/${MEETING_ID}/upload-audio`,
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      }
    );

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Upload failed');
    }

    showToast('Audio file uploaded! Starting Auto Pipeline...', 'success');
    clearSelectedFile();
    await loadMeeting();
    // Auto-trigger the full pipeline after file upload
    setTimeout(() => {
      if (typeof runAutoPipeline === 'function') {
        runAutoPipeline();
      }
    }, 1500);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    hideLoading();
  }
}

// ── Drag and Drop ─────────────────────────────────────────────────

function handleDragOver(event) {
  event.preventDefault();
  document.getElementById('upload-drop-zone').classList.add('dragover');
}

function handleDrop(event) {
  event.preventDefault();
  document.getElementById('upload-drop-zone').classList.remove('dragover');
  const file = event.dataTransfer.files[0];
  if (file) handleFileSelect(file);
}

// ── Timer helpers ─────────────────────────────────────────────────

function updateTimerDisplay() {
  const minutes = String(Math.floor(recordingSeconds / 60)).padStart(2, '0');
  const seconds = String(recordingSeconds % 60).padStart(2, '0');
  const el = document.getElementById('timer-display');
  if (el) el.textContent = `${minutes}:${seconds}`;
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
