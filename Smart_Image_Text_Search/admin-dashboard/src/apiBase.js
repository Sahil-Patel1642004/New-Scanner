export function resolveApiBase(value, isProduction) {
  const configured = typeof value === 'string' ? value.trim() : '';
  if (!configured) {
    if (isProduction) {
      throw new Error('Set VITE_API_BASE_URL to the deployed HTTPS API before building the dashboard.');
    }
    return 'http://localhost:8000/api/v1';
  }

  const candidate = /^https?:\/\//i.test(configured) ? configured : `https://${configured}`;
  let url;
  try {
    url = new URL(candidate);
  } catch {
    throw new Error('VITE_API_BASE_URL must be a valid API host or URL.');
  }

  if (isProduction && url.protocol !== 'https:') {
    throw new Error('VITE_API_BASE_URL must use HTTPS in production.');
  }
  if (url.username || url.password || url.search || url.hash) {
    throw new Error('VITE_API_BASE_URL must not contain credentials, a query, or a fragment.');
  }

  const path = url.pathname.replace(/\/+$/, '');
  if (path && !path.endsWith('/api/v1')) {
    throw new Error('VITE_API_BASE_URL must point to the /api/v1 API prefix.');
  }
  return `${url.origin}${path || '/api/v1'}`;
}
