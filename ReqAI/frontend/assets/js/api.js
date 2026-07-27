/**
 * Centralized API request utility with automatic JWT injection.
 */

async function apiRequest(endpoint, method = 'GET', body = null, requiresAuth = true) {
  const url = `${CONFIG.API_BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
  };

  if (requiresAuth) {
    const token = getAccessToken();
    if (!token) {
      throw new Error('No access token found. Please login again.');
    }
    headers['Authorization'] = `Bearer ${token}`;
  }

  const options = {
    method,
    headers,
  };

  if (body) {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(url, options);

  // Handle 401 Unauthorized
  if (response.status === 401 && requiresAuth) {
    clearSession();
    window.location.href = '/frontend/pages/login.html';
    throw new Error('Session expired. Redirecting to login...');
  }

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || data.message || 'Request failed');
  }

  return data;
}

// ── API Helpers ───────────────────────────────────────────────────

// Auth
async function loginAPI(username_or_email, password) {
  return apiRequest('/auth/login', 'POST', { username_or_email, password }, false);
}

async function registerAPI(full_name, email, username, password) {
  return apiRequest('/auth/register', 'POST', { full_name, email, username, password }, false);
}

// Projects
async function getProjectsAPI() {
  return apiRequest('/projects', 'GET');
}

async function getProjectByIdAPI(id) {
  return apiRequest(`/projects/${id}`, 'GET');
}

async function createProjectAPI(data) {
  return apiRequest('/projects/', 'POST', data);
}

async function updateProjectAPI(id, data) {
  return apiRequest(`/projects/${id}`, 'PUT', data);
}

async function deleteProjectAPI(id) {
  return apiRequest(`/projects/${id}`, 'DELETE');
}

// Meetings
async function getMeetingsAPI(projectId = null) {
  const query = projectId ? `?project_id=${projectId}` : '';
  return apiRequest(`/meetings${query}`, 'GET');
}

async function getMeetingByIdAPI(id) {
  return apiRequest(`/meetings/${id}`, 'GET');
}

async function createMeetingAPI(data) {
  return apiRequest('/meetings/', 'POST', data);
}

async function updateMeetingAPI(id, data) {
  return apiRequest(`/meetings/${id}`, 'PUT', data);
}

async function deleteMeetingAPI(id) {
  return apiRequest(`/meetings/${id}`, 'DELETE');
}

// User
async function getUserProfileAPI() {
  return apiRequest('/users/profile', 'GET');
}

async function updateUserProfileAPI(data) {
  return apiRequest('/users/profile', 'PUT', data);
}

async function changePasswordAPI(current_password, new_password) {
  return apiRequest('/users/password', 'PUT', { current_password, new_password });
}
