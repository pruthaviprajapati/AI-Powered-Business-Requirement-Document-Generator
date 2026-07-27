/**
 * Injects the shared sidebar and topbar into every authenticated page.
 * Call renderLayout('PageTitle', 'active-page-key') in each page.
 */
function renderLayout(pageTitle, activeKey) {
  const sidebarLinks = [
    { key: 'dashboard', icon: 'fa-gauge-high',     label: 'Dashboard',  href: 'dashboard.html' },
    { key: 'projects',  icon: 'fa-folder-open',    label: 'Projects',   href: 'projects.html' },
    { key: 'meetings',  icon: 'fa-calendar-check', label: 'Meetings',   href: 'meetings.html' },
    { key: 'profile',   icon: 'fa-user-circle',    label: 'Profile',    href: 'profile.html', section: 'Account' },
    { key: 'settings',  icon: 'fa-gear',            label: 'Settings',   href: 'settings.html' },
  ];

  let sidebarHTML = `
    <aside class="sidebar" id="sidebar">
      <div class="sidebar-brand">
        <div class="brand-icon"><i class="fas fa-robot"></i></div>
        <div>
          <span class="brand-name">ReqAI</span>
          <span class="brand-tagline">AI Requirement Generator</span>
        </div>
      </div>
      <nav class="sidebar-nav">
        <div class="nav-section-title">Main Menu</div>`;

  let lastSection = 'Main Menu';
  sidebarLinks.forEach(link => {
    if (link.section && link.section !== lastSection) {
      sidebarHTML += `<div class="nav-section-title">${link.section}</div>`;
      lastSection = link.section;
    }
    const activeClass = link.key === activeKey ? ' active' : '';
    sidebarHTML += `
        <a href="${link.href}" class="sidebar-link${activeClass}">
          <i class="fas ${link.icon}"></i>
          <span>${link.label}</span>
        </a>`;
  });

  sidebarHTML += `
      </nav>
      <div class="sidebar-footer">
        <a href="#" class="sidebar-link" onclick="logout()">
          <i class="fas fa-right-from-bracket"></i>
          <span>Logout</span>
        </a>
      </div>
    </aside>`;

  const topbarHTML = `
    <header class="topbar">
      <div class="topbar-left">
        <button class="topbar-toggle" id="sidebar-toggle">
          <i class="fas fa-bars"></i>
        </button>
        <span class="page-title">${pageTitle}</span>
      </div>
      <div class="topbar-right">
        <div class="d-flex align-items-center gap-2">
          <div style="width:34px;height:34px;border-radius:50%;background:var(--primary);
               color:#fff;display:flex;align-items:center;justify-content:center;font-size:.85rem;font-weight:700;">
            <span id="user-avatar-letter">U</span>
          </div>
          <span id="user-name-display" style="font-size:.875rem;font-weight:500;"></span>
        </div>
      </div>
    </header>`;

  document.body.insertAdjacentHTML('afterbegin', sidebarHTML + topbarHTML);

  // Set avatar letter
  const user = getUser();
  if (user) {
    const letter = document.getElementById('user-avatar-letter');
    if (letter) letter.textContent = (user.full_name || user.username || 'U')[0].toUpperCase();
    displayUserName();
  }
}
