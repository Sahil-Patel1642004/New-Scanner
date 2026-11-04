/**
 * Centralized API client for Scanora Admin Dashboard.
 * Interacts with the backend licensing server.
 */

export const API_BASE = typeof __SCANORA_API_BASE_URL__ !== 'undefined'
  ? __SCANORA_API_BASE_URL__
  : 'http://localhost:8000/api/v1';

export const TOKEN_KEY = 'scanora-admin-token';
export const DEFAULTS_KEY = 'scanora-admin-defaults';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function getPreferences() {
  try {
    const raw = localStorage.getItem(DEFAULTS_KEY);
    return raw ? JSON.parse(raw) : {
      defaultType: 'ONE_YEAR',
      defaultMaxDevices: 1,
      trialDays: 30,
      autoEmailOnCreate: true,
    };
  } catch {
    return {
      defaultType: 'ONE_YEAR',
      defaultMaxDevices: 1,
      trialDays: 30,
      autoEmailOnCreate: true,
    };
  }
}

export function savePreferences(prefs) {
  localStorage.setItem(DEFAULTS_KEY, JSON.stringify(prefs));
}

/**
 * Generic API request handler.
 */
export async function request(path, options = {}) {
  const token = options.token ?? getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = 'Request failed';
    try {
      const body = await response.json();
      message = body.detail || body.message || message;
    } catch {
      message = response.statusText || message;
    }

    if (
      response.status === 401 ||
      message.includes('Invalid or expired session') ||
      message.includes('Authentication required')
    ) {
      removeToken();
      window.dispatchEvent(new CustomEvent('scanora-auth-expired', { detail: message }));
    }

    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return response.status === 204 ? null : response.json();
}

/* ==================== Auth API ==================== */

export async function login({ email, password }) {
  const data = await request('/admin/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  if (data?.access_token) {
    setToken(data.access_token);
  }
  return data;
}

export async function logout() {
  try {
    await request('/admin/logout', { method: 'POST' });
  } catch {
    // Ignore network failure on logout
  } finally {
    removeToken();
  }
}

/* ==================== Dashboard API ==================== */

export async function getDashboard() {
  return request('/admin/dashboard');
}

/* ==================== Customers API ==================== */

export async function getCustomers() {
  return request('/customers');
}

export async function createCustomer(customerData) {
  return request('/customers', {
    method: 'POST',
    body: JSON.stringify(customerData),
  });
}

/* ==================== Products API ==================== */

export async function getProducts() {
  return request('/products');
}

export async function createProduct(productData) {
  return request('/products', {
    method: 'POST',
    body: JSON.stringify(productData),
  });
}

/* ==================== Licences API ==================== */

export async function getLicences() {
  return request('/licences');
}

export async function createLicence(licenceData) {
  return request('/licences', {
    method: 'POST',
    body: JSON.stringify(licenceData),
  });
}

export async function updateLicence(id, updates) {
  return request(`/licences/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

export async function revealProductKey(id) {
  return request(`/licences/${id}/product-key`);
}

export async function sendLicenceEmail(id) {
  return request(`/licences/${id}/send-email`, {
    method: 'POST',
  });
}

/* ==================== Email Logs API ==================== */

export async function getEmailLogs() {
  return request('/email-logs');
}

/* ==================== Date & Business Helpers ==================== */

export function formatDate(value, options = {}) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  
  if (options.includeTime) {
    return date.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
  
  return date.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function todayString() {
  return new Date().toISOString().slice(0, 10);
}

export function expiryForLicenceType(licenceType, issueDate) {
  if (!issueDate) return '';
  if (licenceType === 'LIFETIME') return '9999-12-31';

  const expiry = new Date(`${issueDate}T00:00:00`);
  if (licenceType === 'TRIAL') {
    expiry.setDate(expiry.getDate() + 30);
  } else {
    const monthsMap = {
      THREE_MONTHS: 3,
      SIX_MONTHS: 6,
      ONE_YEAR: 12,
    };
    const months = monthsMap[licenceType];
    if (!months) return '';
    const originalDay = expiry.getDate();
    expiry.setDate(1);
    expiry.setMonth(expiry.getMonth() + months);
    const lastDay = new Date(expiry.getFullYear(), expiry.getMonth() + 1, 0).getDate();
    expiry.setDate(Math.min(originalDay, lastDay));
  }

  const y = expiry.getFullYear();
  const m = String(expiry.getMonth() + 1).padStart(2, '0');
  const d = String(expiry.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}
