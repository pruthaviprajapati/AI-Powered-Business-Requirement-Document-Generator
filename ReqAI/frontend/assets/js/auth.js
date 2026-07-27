/**
 * Authentication utilities – token storage, user session, logout.
 */

function saveSession(accessToken, refreshToken, user) {
  localStorage.setItem(CONFIG.TOKEN_KEY, accessToken);
  localStorage.setItem(CONFIG.REFRESH_KEY, refreshToken);
  localStorage.setItem(CONFIG.USER_KEY, JSON.stringify(user));
}

function getAccessToken() {
  return localStorage.getItem(CONFIG.TOKEN_KEY);
}

function getRefreshToken() {
  return localStorage.getItem(CONFIG.REFRESH_KEY);
}

function getUser() {
  const userJson = localStorage.getItem(CONFIG.USER_KEY);
  return userJson ? JSON.parse(userJson) : null;
}

function clearSession() {
  localStorage.removeItem(CONFIG.TOKEN_KEY);
  localStorage.removeItem(CONFIG.REFRESH_KEY);
  localStorage.removeItem(CONFIG.USER_KEY);
}

function isAuthenticated() {
  return !!getAccessToken();
}

function requireAuth() {
  if (!isAuthenticated()) {
    window.location.href = '/frontend/pages/login.html';
  }
}

function redirectIfAuthenticated() {
  if (isAuthenticated()) {
    window.location.href = '/frontend/pages/dashboard.html';
  }
}

async function logout() {
  try {
    await apiRequest('/auth/logout', 'POST');
  } catch (err) {
    console.error('Logout API error:', err);
  }
  clearSession();
  window.location.href = '/frontend/pages/login.html';
}

// Display current user name in topbar
function displayUserName() {
  const user = getUser();
  const element = document.getElementById('user-name-display');
  if (user && element) {
    element.textContent = user.full_name || user.username;
  }
}
