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
  sendLicenceEmail as apiSendLicenceEmail,
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

      let emailMsg = '';
      if (result.email_delivery_status === 'mock') {
        emailMsg = ' (Email simulated — configure SMTP for live delivery)';
      } else if (result.email_delivery_status === 'failed') {
        emailMsg = ' (Email delivery failed. Check email logs)';
      } else {
        emailMsg = ' (Email key queued for delivery)';
      }

      toast.success(`Licence generated successfully!${emailMsg}`);
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

  const sendLicenceEmail = async (id) => {
    try {
      const result = await apiSendLicenceEmail(id);
      const delivery = result.delivery_status === 'mock'
        ? `Delivery simulated to ${result.recipient} (SMTP not configured)`
        : `Key email sent to ${result.recipient}`;
      toast.success(delivery);
      await refreshData();
      return result;
    } catch (err) {
      toast.error(err.message || 'Failed to send licence email');
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
        sendLicenceEmail,
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
