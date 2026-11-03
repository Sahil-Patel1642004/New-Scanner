import { useEffect, useState } from 'react';

const API_BASE = __SCANORA_API_BASE_URL__;
const TOKEN_KEY = 'scanora-admin-token';

async function request(path, token, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    let message = 'Request failed';
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  return response.status === 204 ? null : response.json();
}

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function todayString() {
  return new Date().toISOString().slice(0, 10);
}

function expiryForLicenceType(licenceType, issueDate) {
  if (!issueDate) return '';
  if (licenceType === 'LIFETIME') return '9999-12-31';

  const expiry = new Date(`${issueDate}T00:00:00`);
  if (licenceType === 'TRIAL') {
    expiry.setDate(expiry.getDate() + 30);
  } else {
    const months = { THREE_MONTHS: 3, SIX_MONTHS: 6, ONE_YEAR: 12 }[licenceType];
    if (!months) return '';
    const originalDay = expiry.getDate();
    expiry.setDate(1);
    expiry.setMonth(expiry.getMonth() + months);
    const lastDay = new Date(expiry.getFullYear(), expiry.getMonth() + 1, 0).getDate();
    expiry.setDate(Math.min(originalDay, lastDay));
  }

  return `${expiry.getFullYear()}-${String(expiry.getMonth() + 1).padStart(2, '0')}-${String(expiry.getDate()).padStart(2, '0')}`;
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || '');
  const [email, setEmail] = useState(import.meta.env.VITE_ADMIN_EMAIL || '');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [dashboard, setDashboard] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);
  const [licences, setLicences] = useState([]);
  const [emailLogs, setEmailLogs] = useState([]);
  const [openForm, setOpenForm] = useState('');
  const [createdKey, setCreatedKey] = useState('');
  const [sendingLicenceId, setSendingLicenceId] = useState(null);
  const [editingLicenceId, setEditingLicenceId] = useState(null);
  const [revealedKey, setRevealedKey] = useState(null);
  const [loadingKeyId, setLoadingKeyId] = useState(null);

  const loadData = async (authToken) => {
    const [dashboardData, customersData, productsData, licencesData, logsData] = await Promise.all([
      request('/admin/dashboard', authToken),
      request('/customers', authToken),
      request('/products', authToken),
      request('/licences', authToken),
      request('/email-logs', authToken),
    ]);

    setDashboard(dashboardData);
    setCustomers(customersData);
    setProducts(productsData);
    setLicences(licencesData);
    setEmailLogs(logsData);
  };

  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    (async () => {
      try {
        setLoading(true);
        setError('');
        await loadData(token);
      } catch (err) {
        if (cancelled) return;
        setError(err.message);
        if (err.message.includes('Invalid or expired session') || err.message.includes('Authentication required')) {
          localStorage.removeItem(TOKEN_KEY);
          setToken('');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [token]);

  const handleLogin = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const payload = await request('/admin/login', '', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      localStorage.setItem(TOKEN_KEY, payload.access_token);
      setToken(payload.access_token);
      setPassword('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await request('/admin/logout', token, { method: 'POST' });
    } catch {
      // Clear local state even if the session has already expired.
    }
    localStorage.removeItem(TOKEN_KEY);
    setToken('');
    setDashboard(null);
    setCustomers([]);
    setProducts([]);
    setLicences([]);
    setEmailLogs([]);
  };

  const createRecord = async (event, path, successMessage, onSuccess) => {
    event.preventDefault();
    setError('');
    setNotice('');
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form).entries());
    try {
      const result = await request(path, token, { method: 'POST', body: JSON.stringify(payload) });
      form.reset();
      await loadData(token);
      setNotice(successMessage);
      onSuccess?.(result);
    } catch (err) {
      setError(err.message);
    }
  };

  const createLicence = (event) => createRecord(
    event,
    '/licences',
    'Licence created.',
    (result) => {
      setCreatedKey(result.product_key || '');
      const delivery = result.email_delivery_status === 'mock'
        ? `Email to ${result.email_recipient} was simulated only; configure SMTP to deliver it.`
        : result.email_delivery_status === 'failed'
          ? `Email to ${result.email_recipient} failed. Check the email log and SMTP configuration.`
          : `SMTP accepted the message for ${result.email_recipient}; inbox delivery is not confirmed.`;
      setNotice(`Licence created. ${delivery} Copy the product key now.`);
    },
  );

  const sendLicenceEmail = async (licence) => {
    setSendingLicenceId(licence.id);
    setError('');
    setNotice('');
    try {
      const result = await request(`/licences/${licence.id}/send-email`, token, { method: 'POST' });
      await loadData(token);
      setNotice(result.delivery_status === 'mock'
        ? `Email to ${result.recipient} was simulated only; configure SMTP to deliver it.`
        : `SMTP accepted the message for ${result.recipient}; inbox delivery is not confirmed.`);
    } catch (err) {
      setError(err.message);
      await loadData(token).catch(() => {});
    } finally {
      setSendingLicenceId(null);
    }
  };

  const updateLicence = async (event, licence) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    values.max_devices = Number(values.max_devices);
    try {
      await request(`/licences/${licence.id}`, token, { method: 'PATCH', body: JSON.stringify(values) });
      setEditingLicenceId(null);
      await loadData(token);
      setNotice(`Licence #${licence.id} updated.`);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  const setLicenceEnabled = async (licence, enabled) => {
    try {
      await request(`/licences/${licence.id}`, token, {
        method: 'PATCH',
        body: JSON.stringify({ is_enabled: enabled }),
      });
      await loadData(token);
      setNotice(`Licence #${licence.id} ${enabled ? 'enabled' : 'disabled'}.`);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  const revokeLicence = async (licence) => {
    if (!window.confirm(`Permanently revoke licence #${licence.id}? This cannot be undone.`)) return;
    try {
      await request(`/licences/${licence.id}`, token, {
        method: 'PATCH',
        body: JSON.stringify({ is_revoked: true }),
      });
      await loadData(token);
      setNotice(`Licence #${licence.id} revoked.`);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  const viewProductKey = async (licence) => {
    if (revealedKey?.id === licence.id) {
      setRevealedKey(null);
      return;
    }
    setLoadingKeyId(licence.id);
    try {
      const result = await request(`/licences/${licence.id}/product-key`, token);
      setRevealedKey({ id: licence.id, value: result.product_key });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingKeyId(null);
    }
  };

  const copyProductKey = async (productKey = createdKey) => {
    try {
      await navigator.clipboard.writeText(productKey);
      setNotice('Product key copied. Store it securely.');
    } catch {
      setError('Clipboard access is unavailable. Select and copy the displayed key.');
    }
  };

  if (!token) {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <div className="brand-block">
            <span className="brand-badge">S</span>
            <h1>Scanora Admin</h1>
          </div>
          <form onSubmit={handleLogin} className="auth-form">
            <label>
              Email
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="username" />
            </label>
            <label>
              Password
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete="current-password" />
            </label>
            {error ? <div className="error-box" role="alert">{error}</div> : null}
            <button type="submit" disabled={loading}>
              {loading ? 'Signing in...' : 'Login'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  const summary = dashboard?.dashboard || {};

  return (
    <div className="dashboard-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Secure licensing portal</p>
          <h2>Admin Dashboard</h2>
        </div>
        <button className="ghost-button" onClick={handleLogout}>Logout</button>
      </header>

      {error ? <div className="error-box" role="alert">{error}</div> : null}
      {notice ? <div className="notice-box" role="status">{notice}</div> : null}
      {loading ? <div className="loading-box">Loading dashboard data...</div> : null}

      {createdKey ? (
        <section className="key-notice" aria-label="New product key">
          <div><strong>New product key</strong><code>{createdKey}</code></div>
          <button type="button" className="small-button" onClick={copyProductKey}>Copy key</button>
          <button type="button" className="icon-button" title="Dismiss key" aria-label="Dismiss key" onClick={() => setCreatedKey('')}>×</button>
        </section>
      ) : null}

      <section className="stats-grid">
        <StatCard label="Customers" value={summary.total_customers ?? customers.length} tone="blue" />
        <StatCard label="Licences" value={summary.total_licences ?? licences.length} tone="purple" />
        <StatCard label="Active" value={summary.active_licences ?? licences.filter((item) => item.status === 'ACTIVE').length} tone="green" />
        <StatCard label="Expired" value={summary.expired_licences ?? licences.filter((item) => item.expiry_date < todayString()).length} tone="red" />
      </section>

      <section className="workflow-grid" aria-label="Create records">
        <div className="panel">
          <div className="panel-header">
            <h3>Customers</h3>
            <span>{customers.length}</span>
          </div>
          <button className="small-button" onClick={() => setOpenForm(openForm === 'customer' ? '' : 'customer')}>Add customer</button>
          {openForm === 'customer' ? (
            <form className="workflow-form" onSubmit={(event) => createRecord(event, '/customers', 'Customer created.', () => setOpenForm(''))}>
              <label>Name<input name="name" required minLength="2" maxLength="255" /></label>
              <label>Email<input name="email" type="email" required maxLength="255" /></label>
              <label>Company<input name="company_name" maxLength="255" /></label>
              <label>Phone<input name="phone" maxLength="50" /></label>
              <label>Order reference<input name="order_reference" maxLength="255" /></label>
              <button type="submit" disabled={loading}>Create customer</button>
            </form>
          ) : null}
          <div className="list-box">
            {customers.length === 0 ? <p>No customers found.</p> : customers.map((customer) => (
              <div className="list-item" key={customer.id}>
                <div><strong>{customer.name}</strong><small>{customer.email}</small></div>
                <span>{customer.company_name || 'Independent'}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h3>Products</h3>
            <span>{products.length}</span>
          </div>
          <button className="small-button" onClick={() => setOpenForm(openForm === 'product' ? '' : 'product')}>Add product</button>
          {openForm === 'product' ? (
            <form className="workflow-form" onSubmit={(event) => createRecord(event, '/products', 'Product created.', () => setOpenForm(''))}>
              <label>Name<input name="name" required minLength="2" maxLength="255" /></label>
              <label>SKU<input name="sku" required minLength="2" maxLength="100" /></label>
              <label>Description<textarea name="description" maxLength="1000" rows="2" /></label>
              <button type="submit" disabled={loading}>Create product</button>
            </form>
          ) : null}
          <div className="list-box">
            {products.length === 0 ? <p>No products found.</p> : products.map((product) => (
              <div className="list-item" key={product.id}>
                <div><strong>{product.name}</strong><small>{product.sku}</small></div>
                <span>{product.is_active ? 'Active' : 'Inactive'}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="panel licence-panel">
        <div className="panel-header">
          <h3>Licences</h3>
          <span>{licences.length}</span>
        </div>
        <button className="small-button" onClick={() => setOpenForm(openForm === 'licence' ? '' : 'licence')} disabled={!customers.length || !products.length}>Create licence</button>
        {openForm === 'licence' ? (
          <form className="workflow-form licence-form" onSubmit={createLicence}>
            <label>Customer<select name="customer_id" required defaultValue=""><option value="" disabled>Select customer</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name} · {customer.email}</option>)}</select></label>
            <label>Product<select name="product_id" required defaultValue=""><option value="" disabled>Select product</option>{products.filter((product) => product.is_active).map((product) => <option key={product.id} value={product.id}>{product.name} · {product.sku}</option>)}</select></label>
            <label>Licence type<select name="licence_type" required defaultValue="ONE_YEAR" onChange={(event) => {
              const form = event.currentTarget.form;
              form.elements.expiry_date.value = expiryForLicenceType(event.target.value, form.elements.issue_date.value);
            }}>
              <option value="TRIAL">Trial (30 days)</option>
              <option value="THREE_MONTHS">3 months</option>
              <option value="SIX_MONTHS">6 months</option>
              <option value="ONE_YEAR">1 year</option>
              <option value="LIFETIME">Lifetime</option>
            </select></label>
            <label>Issue date<input name="issue_date" type="date" required defaultValue={todayString()} onChange={(event) => {
              const form = event.currentTarget.form;
              form.elements.expiry_date.value = expiryForLicenceType(form.elements.licence_type.value, event.target.value);
            }} /></label>
            <label>Start date<input name="start_date" type="date" defaultValue={todayString()} /></label>
            <label>Expiry date<input name="expiry_date" type="date" required defaultValue={expiryForLicenceType('ONE_YEAR', todayString())} /></label>
            <label>Device limit<input name="max_devices" type="number" min="1" max="100" defaultValue="1" required /></label>
            <label>Notes<textarea name="notes" maxLength="1000" rows="2" /></label>
            <button type="submit" disabled={loading}>Create licence</button>
          </form>
        ) : null}
        <div className="table-wrap">
          <table>
            <thead><tr><th>Customer</th><th>Email</th><th>Product</th><th>Key</th><th>Dates</th><th>Status</th><th>Devices</th><th>Action</th></tr></thead>
            <tbody>
              {licences.length === 0 ? <tr><td colSpan="8">No licences found.</td></tr> : licences.map((licence) => {
                const customer = customers.find((item) => item.id === licence.customer_id);
                const product = products.find((item) => item.id === licence.product_id);
                if (editingLicenceId === licence.id) {
                  return (
                    <tr key={licence.id}>
                      <td colSpan="8">
                        <form className="edit-licence-form" onSubmit={(event) => updateLicence(event, licence)}>
                          <label>Start date<input name="start_date" type="date" required defaultValue={licence.start_date || licence.issue_date} /></label>
                          <label>Expiry date<input name="expiry_date" type="date" required defaultValue={licence.expiry_date} /></label>
                          <label>Device limit<input name="max_devices" type="number" min="1" defaultValue={licence.max_devices} required /></label>
                          <label>Notes<input name="notes" maxLength="1000" defaultValue={licence.notes || ''} /></label>
                          <button className="small-button" type="submit">Save</button>
                          <button className="text-button" type="button" onClick={() => setEditingLicenceId(null)}>Cancel</button>
                        </form>
                      </td>
                    </tr>
                  );
                }
                return (
                  <tr key={licence.id}>
                    <td>{customer?.name || `Customer #${licence.customer_id}`}</td>
                    <td>{customer?.email || '—'}</td>
                    <td>{product?.name || `Product #${licence.product_id}`}</td>
                    <td>
                      <code>{revealedKey?.id === licence.id ? revealedKey.value : licence.masked_product_key}</code>
                      <div className="table-actions">
                        <button className="text-button" onClick={() => viewProductKey(licence)} disabled={loadingKeyId === licence.id}>
                          {loadingKeyId === licence.id ? 'Loading…' : revealedKey?.id === licence.id ? 'Hide key' : 'View key'}
                        </button>
                        {revealedKey?.id === licence.id ? <button className="text-button" onClick={() => copyProductKey(revealedKey.value)}>Copy</button> : null}
                      </div>
                    </td>
                    <td>{formatDate(licence.start_date || licence.issue_date)} – {formatDate(licence.expiry_date)}</td>
                    <td><span className={`pill ${licence.status === 'ACTIVE' ? 'pill-active' : ''}`}>{licence.is_revoked ? 'REVOKED' : licence.is_enabled ? licence.status : 'DISABLED'}</span></td>
                    <td>{licence.max_devices}</td>
                    <td>
                      <div className="table-actions">
                        <button className="small-button" onClick={() => setEditingLicenceId(licence.id)}>Edit</button>
                        {!licence.is_revoked ? <button className="small-button" onClick={() => setLicenceEnabled(licence, !licence.is_enabled)}>{licence.is_enabled ? 'Disable' : 'Enable'}</button> : null}
                        {!licence.is_revoked ? <button className="danger-button" onClick={() => revokeLicence(licence)}>Revoke</button> : null}
                        <button className="small-button" onClick={() => sendLicenceEmail(licence)} disabled={sendingLicenceId === licence.id || licence.is_revoked}>{sendingLicenceId === licence.id ? 'Sending…' : 'Email key'}</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header"><h3>Email log</h3><span>{emailLogs.length}</span></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Recipient</th><th>Subject</th><th>Status</th><th>Sent</th><th>Details</th></tr></thead>
            <tbody>
              {emailLogs.length === 0 ? <tr><td colSpan="5">No email activity yet.</td></tr> : emailLogs.map((log) => (
                <tr key={log.id}>
                  <td>{log.recipient}</td><td>{log.subject}</td><td>{log.status}</td>
                  <td>{formatDate(log.sent_at || log.failed_at)}</td><td>{log.last_error || log.provider_message_id || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function StatCard({ label, value, tone }) {
  return <div className={`stat-card ${tone}`}><span>{label}</span><strong>{value}</strong></div>;
}
