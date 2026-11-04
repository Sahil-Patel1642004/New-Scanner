import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import ToastContainer from '../ui/Toast';
import Modal from '../ui/Modal';
import { useData } from '../../hooks/useApi';
import { useToast } from '../../hooks/useToast';
import { expiryForLicenceType, todayString } from '../../api';
import { Copy, Check, KeyRound, AlertCircle, Info } from 'lucide-react';

export default function AppShell({ adminEmail, onLogout }) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    return localStorage.getItem('scanora-sidebar-collapsed') === 'true';
  });

  const [createLicenceOpen, setCreateLicenceOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  const {
    customers,
    products,
    createLicence,
    newlyCreatedKey,
    setNewlyCreatedKey,
  } = useData();

  const { toast } = useToast();

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem('scanora-sidebar-collapsed', String(next));
      return next;
    });
  };

  const handleCreateLicenceSubmit = async (e) => {
    e.preventDefault();
    setCreating(true);
    const form = e.currentTarget;
    const formData = new FormData(form);

    const payload = {
      customer_id: Number(formData.get('customer_id')),
      product_id: Number(formData.get('product_id')),
      licence_type: formData.get('licence_type'),
      issue_date: formData.get('issue_date'),
      start_date: formData.get('start_date') || formData.get('issue_date'),
      expiry_date: formData.get('expiry_date'),
      max_devices: Number(formData.get('max_devices')),
      notes: formData.get('notes') || '',
    };

    try {
      await createLicence(payload);
      setCreateLicenceOpen(false);
      form.reset();
    } catch {
      // error handled in useData hook with toast
    } finally {
      setCreating(false);
    }
  };

  const handleCopyNewKey = async () => {
    if (!newlyCreatedKey?.key) return;
    try {
      await navigator.clipboard.writeText(newlyCreatedKey.key);
      setCopiedKey(true);
      toast.success('Product key copied to clipboard.');
      setTimeout(() => setCopiedKey(false), 2500);
    } catch {
      toast.error('Could not access clipboard. Please copy manually.');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50/60 dark:bg-gray-950 text-gray-900 dark:text-gray-100 flex flex-col font-sans transition-colors duration-200">
      {/* Sidebar */}
      <Sidebar
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={toggleSidebar}
        adminEmail={adminEmail}
      />

      {/* Main Layout Area */}
      <div
        className={`flex-1 flex flex-col transition-all duration-300 ease-in-out ${
          isSidebarCollapsed ? 'pl-16' : 'pl-60'
        }`}
      >
        <Topbar
          onOpenCreateLicence={() => setCreateLicenceOpen(true)}
          adminEmail={adminEmail}
          onLogout={onLogout}
        />

        <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>

      {/* Toast Notifications */}
      <ToastContainer />

      {/* Global "Create Licence" Modal */}
      <Modal
        isOpen={createLicenceOpen}
        onClose={() => setCreateLicenceOpen(false)}
        title="Generate New Licence"
        subtitle="Issue an encrypted product key and send it via email."
        maxWidth="max-w-xl"
      >
        {customers.length === 0 || products.length === 0 ? (
          <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-sm text-amber-800 dark:text-amber-200 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 shrink-0 text-amber-600 mt-0.5" />
            <div>
              <p className="font-semibold">Setup Required</p>
              <p className="mt-1">
                You must have at least one active customer and one active product before you can generate a licence.
              </p>
            </div>
          </div>
        ) : (
          <form id="globalCreateLicenceForm" onSubmit={handleCreateLicenceSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                  Customer *
                </label>
                <select
                  name="customer_id"
                  required
                  defaultValue=""
                  className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value="" disabled>Select customer…</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.email})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                  Product *
                </label>
                <select
                  name="product_id"
                  required
                  defaultValue=""
                  className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value="" disabled>Select product…</option>
                  {products.filter((p) => p.is_active).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                  Licence Type *
                </label>
                <select
                  name="licence_type"
                  required
                  defaultValue="ONE_YEAR"
                  onChange={(e) => {
                    const form = e.currentTarget.form;
                    if (form && form.elements.expiry_date) {
                      form.elements.expiry_date.value = expiryForLicenceType(
                        e.target.value,
                        form.elements.issue_date.value
                      );
                    }
                  }}
                  className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value="TRIAL">Trial (30 days)</option>
                  <option value="THREE_MONTHS">3 Months</option>
                  <option value="SIX_MONTHS">6 Months</option>
                  <option value="ONE_YEAR">1 Year (Standard)</option>
                  <option value="LIFETIME">Lifetime</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                  Device Limit *
                </label>
                <input
                  name="max_devices"
                  type="number"
                  min="1"
                  max="100"
                  defaultValue="1"
                  required
                  className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                  Issue Date *
                </label>
                <input
                  name="issue_date"
                  type="date"
                  required
                  defaultValue={todayString()}
                  onChange={(e) => {
                    const form = e.currentTarget.form;
                    if (form && form.elements.expiry_date) {
                      form.elements.expiry_date.value = expiryForLicenceType(
                        form.elements.licence_type.value,
                        e.target.value
                      );
                    }
                  }}
                  className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                  Start Date *
                </label>
                <input
                  name="start_date"
                  type="date"
                  required
                  defaultValue={todayString()}
                  className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                  Expiry Date *
                </label>
                <input
                  name="expiry_date"
                  type="date"
                  required
                  defaultValue={expiryForLicenceType('ONE_YEAR', todayString())}
                  className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                Internal Notes
              </label>
              <textarea
                name="notes"
                maxLength={1000}
                rows={2}
                placeholder="Optional billing or license notes…"
                className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-gray-100 dark:border-gray-700">
              <button
                type="button"
                onClick={() => setCreateLicenceOpen(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creating}
                className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition-colors disabled:opacity-50"
              >
                {creating ? 'Generating…' : 'Generate & Send Key'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* Prominent Modal for Newly Created Product Key */}
      <Modal
        isOpen={Boolean(newlyCreatedKey)}
        onClose={() => setNewlyCreatedKey(null)}
        title="Licence Key Generated Successfully"
        subtitle="This unmasked key is shown only once upon creation. Copy and store it securely."
        maxWidth="max-w-lg"
        footer={
          <button
            type="button"
            onClick={() => setNewlyCreatedKey(null)}
            className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition-colors"
          >
            Done
          </button>
        }
      >
        <div className="space-y-4">
          <div className="p-4 bg-emerald-50/70 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-emerald-800 dark:text-emerald-300 uppercase tracking-wider flex items-center gap-1.5">
                <KeyRound className="w-4 h-4" />
                Product Activation Key
              </span>
              <button
                type="button"
                onClick={handleCopyNewKey}
                className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 dark:text-emerald-300 hover:text-emerald-900 bg-white dark:bg-gray-800 border border-emerald-300 dark:border-emerald-700 px-2.5 py-1 rounded-md shadow-xs transition-colors"
              >
                {copiedKey ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    Copy Key
                  </>
                )}
              </button>
            </div>
            <div className="font-mono text-sm sm:text-base font-bold text-gray-900 dark:text-white bg-white dark:bg-gray-900 p-3 rounded-lg border border-emerald-200/80 dark:border-emerald-800/80 break-all select-all">
              {newlyCreatedKey?.key}
            </div>
          </div>

          <div className="text-xs text-gray-600 dark:text-gray-300 space-y-1.5 p-3 rounded-lg bg-gray-50 dark:bg-gray-800/60 border border-gray-200/60 dark:border-gray-700/60">
            <div className="flex items-center gap-2">
              <Info className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>
                Recipient:{' '}
                <strong className="text-gray-900 dark:text-white">
                  {newlyCreatedKey?.emailRecipient || 'N/A'}
                </strong>
              </span>
            </div>
            <div>
              Status:{' '}
              <span className="font-medium text-emerald-600 dark:text-emerald-400 capitalize">
                {newlyCreatedKey?.deliveryStatus === 'mock'
                  ? 'Simulated (configure backend SMTP for live sending)'
                  : newlyCreatedKey?.deliveryStatus || 'Sent'}
              </span>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
