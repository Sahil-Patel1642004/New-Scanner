import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  getToken,
  setToken as saveToken,
  removeToken,
  getDashboard,
  getCustomers,
  getProducts,
  getLicences,
  getEmailLogs,
  createCustomer as apiCreateCustomer,
  createProduct as apiCreateProduct,
  createLicence as apiCreateLicence,
  updateLicence as apiUpdateLicence,
  revealProductKey as apiRevealProductKey,
} from '../api';
import { useToast } from './useToast';

const DataContext = createContext(null);

export function DataProvider({ children }) {
  const [authToken, setAuthTokenState] = useState(() => getToken());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);
  const [licences, setLicences] = useState([]);
  const [emailLogs, setEmailLogs] = useState([]);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState(null);
  const hasQueuedEmail = emailLogs.some((log) => (log.status || '').toUpperCase() === 'QUEUED');

  const { toast } = useToast();

  const setAuthToken = useCallback((token) => {
    saveToken(token);
    setAuthTokenState(token || '');
  }, []);

  const refreshData = useCallback(async () => {
    if (!getToken()) return;
    setLoading(true);
    setError(null);
    try {
      const [dash, custs, prods, lics, logs] = await Promise.all([
        getDashboard(),
        getCustomers(),
        getProducts(),
        getLicences(),
        getEmailLogs(),
      ]);
      setDashboard(dash);
      setCustomers(custs || []);
      setProducts(prods || []);
      setLicences(lics || []);
      setEmailLogs(logs || []);
    } catch (err) {
      setError(err.message);
      if (err.message.includes('Invalid or expired') || err.message.includes('Authentication required')) {
        removeToken();
        setAuthTokenState('');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load when token is present
  useEffect(() => {
    if (authToken) {
      refreshData();
    } else {
      setDashboard(null);
      setCustomers([]);
      setProducts([]);
      setLicences([]);
      setEmailLogs([]);
    }
  }, [authToken, refreshData]);

  useEffect(() => {
    if (!authToken || !hasQueuedEmail) return undefined;
    let cancelled = false;
    const refreshQueuedEmailLogs = async () => {
      try {
        const logs = await getEmailLogs();
        if (!cancelled) setEmailLogs(logs || []);
      } catch {
        // Keep the queued status visible; the user can retry from Email Logs.
      }
    };
    const intervalId = window.setInterval(refreshQueuedEmailLogs, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [authToken, hasQueuedEmail]);

  // Listen for auth expiration events
  useEffect(() => {
    const handleAuthExpired = (e) => {
      setAuthTokenState('');
      toast.error(e.detail || 'Session expired. Please sign in again.');
    };
    window.addEventListener('scanora-auth-expired', handleAuthExpired);
    return () => window.removeEventListener('scanora-auth-expired', handleAuthExpired);
  }, [toast]);

  const createCustomer = async (data) => {
    try {
      const result = await apiCreateCustomer(data);
      toast.success(`Customer "${data.name}" added successfully.`);
      await refreshData();
      return result;
    } catch (err) {
      toast.error(err.message || 'Failed to create customer');
      throw err;
    }
  };

  const createProduct = async (data) => {
    try {
      const result = await apiCreateProduct(data);
      toast.success(`Product "${data.name}" created.`);
      await refreshData();
      return result;
    } catch (err) {
      toast.error(err.message || 'Failed to create product');
      throw err;
    }
  };

  const createLicence = async (data) => {
    try {
      const result = await apiCreateLicence(data);
      const key = result.product_key || '';
      setNewlyCreatedKey({
        key,
        customerName: result.customer_name || 'Customer',
        emailRecipient: result.email_recipient,
        deliveryStatus: result.email_delivery_status,
      });
      toast.success(
        result.email_delivery_status === 'sent'
          ? `Licence generated and email sent to ${result.email_recipient}.`
          : 'Licence generated. The email is sending in the background; check Email Logs for its final status.',
      );
      await refreshData();
      return result;
    } catch (err) {
      toast.error(err.message || 'Failed to generate licence');
      throw err;
    }
  };

  const updateLicence = async (id, data) => {
    try {
      const result = await apiUpdateLicence(id, data);
      toast.success(`Licence #${id} updated.`);
      await refreshData();
      return result;
    } catch (err) {
      toast.error(err.message || 'Failed to update licence');
      throw err;
    }
  };

  const toggleLicenceStatus = async (licence) => {
    const newStatus = !licence.is_enabled;
    try {
      await apiUpdateLicence(licence.id, { is_enabled: newStatus });
      toast.success(`Licence #${licence.id} ${newStatus ? 'enabled' : 'disabled'}.`);
      await refreshData();
    } catch (err) {
      toast.error(err.message || 'Failed to toggle licence status');
      throw err;
    }
  };

  const revokeLicence = async (id) => {
    try {
      await apiUpdateLicence(id, { is_revoked: true });
      toast.success(`Licence #${id} permanently revoked.`);
      await refreshData();
    } catch (err) {
      toast.error(err.message || 'Failed to revoke licence');
      throw err;
    }
  };

  const revealProductKey = async (id) => {
    return apiRevealProductKey(id);
  };

  return (
    <DataContext.Provider
      value={{
        authToken,
        setAuthToken,
        loading,
        error,
        dashboard,
        customers,
        products,
        licences,
        emailLogs,
        newlyCreatedKey,
        setNewlyCreatedKey,
        refreshData,
        createCustomer,
        createProduct,
        createLicence,
        updateLicence,
        toggleLicenceStatus,
        revokeLicence,
        revealProductKey,
      }}
    >
      {children}
    </DataContext.Provider>
  );
}

export function useData() {
  const context = useContext(DataContext);
  if (!context) {
    throw new Error('useData must be used within a DataProvider');
  }
  return context;
}
