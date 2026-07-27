/**
 * UI utilities – toast notifications, loading overlays, modals.
 */

// ── Toast notifications ───────────────────────────────────────────

function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast-msg ${type}`;

  const icon = type === 'success' ? '✓' :
               type === 'error'   ? '✕' :
               type === 'warning' ? '⚠' : 'ℹ';

  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ── Loading overlay ───────────────────────────────────────────────

function showLoading() {
  let overlay = document.getElementById('loading-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'loading-overlay';
    overlay.className = 'loading-overlay';
    overlay.innerHTML = '<div class="spinner-ring"></div>';
    document.body.appendChild(overlay);
  }
  overlay.style.display = 'flex';
}

function hideLoading() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) {
    overlay.style.display = 'none';
  }
}

// ── Sidebar toggle (mobile) ───────────────────────────────────────

function initSidebarToggle() {
  const sidebar = document.querySelector('.sidebar');
  const toggleBtn = document.getElementById('sidebar-toggle');
  let overlay = document.getElementById('sidebar-overlay');

  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'sidebar-overlay';
    overlay.className = 'sidebar-overlay';
    document.body.appendChild(overlay);
  }

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      overlay.classList.toggle('visible');
    });
  }

  overlay.addEventListener('click', () => {
    sidebar.classList.remove('open');
    overlay.classList.remove('visible');
  });
}

// ── Set active nav link ───────────────────────────────────────────

function setActiveNavLink(pageName) {
  document.querySelectorAll('.sidebar-link').forEach(link => {
    link.classList.remove('active');
    if (link.getAttribute('href').includes(pageName)) {
      link.classList.add('active');
    }
  });
}

// ── Format date ───────────────────────────────────────────────────

function formatDate(isoString) {
  if (!isoString) return '—';
  const date = new Date(isoString);
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatDateTime(isoString) {
  if (!isoString) return '—';
  const date = new Date(isoString);
  return date.toLocaleString('en-US', { 
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

// ── Status badge helper ───────────────────────────────────────────

function getStatusBadge(status) {
  const cls = `badge-${status.toLowerCase()}`;
  return `<span class="badge-status ${cls}">${status}</span>`;
}

// ── Confirm action ────────────────────────────────────────────────

function confirmAction(message) {
  return confirm(message);
}

// ── Initialize common behaviors ───────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initSidebarToggle();
  displayUserName();
});
