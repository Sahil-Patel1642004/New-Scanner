import { useState, useMemo, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useData } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { LicenceStatusBadge } from '../components/ui/Badge';
import SearchInput from '../components/ui/SearchInput';
import Pagination from '../components/ui/Pagination';
import Modal from '../components/ui/Modal';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import EmptyState from '../components/ui/EmptyState';
import { formatDate, todayString, expiryForLicenceType } from '../api';
import {
  Key,
  Plus,
  Eye,
  EyeOff,
  Copy,
  Mail,
  Edit2,
  Power,
  Trash2,
  Filter,
  Check,
} from 'lucide-react';

export default function LicencesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || '';

  const {
    loading,
    licences,
    customers,
    products,
    createLicence,
    updateLicence,
    toggleLicenceStatus,
    revokeLicence,
    sendLicenceEmail,
    revealProductKey,
  } = useData();

  const { toast } = useToast();

  // Search & Filters
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // Reveal / Copy keys
  const [revealedKeys, setRevealedKeys] = useState({});
  const [loadingKeyId, setLoadingKeyId] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  // Modals state
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editingLicence, setEditingLicence] = useState(null);
  const [revokingLicence, setRevokingLicence] = useState(null);
  const [revoking, setRevoking] = useState(false);
  const [sendingEmailId, setSendingEmailId] = useState(null);

  // Sync searchQuery with query param if it changes
  useEffect(() => {
    const q = searchParams.get('q');
    if (q !== null && q !== searchQuery) {
      setSearchQuery(q);
    }
  }, [searchParams]);

  // Filtered licences
  const filteredLicences = useMemo(() => {
    return licences.filter((lic) => {
      const customer = customers.find((c) => c.id === lic.customer_id);
      const product = products.find((p) => p.id === lic.product_id);

      // Search match
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const customerMatch = customer?.name?.toLowerCase().includes(query) || customer?.email?.toLowerCase().includes(query);
        const productMatch = product?.name?.toLowerCase().includes(query) || product?.sku?.toLowerCase().includes(query);
        const keyMatch = lic.masked_product_key?.toLowerCase().includes(query) || String(lic.id).includes(query);
        if (!customerMatch && !productMatch && !keyMatch) return false;
      }

      // Status filter
      if (statusFilter !== 'ALL') {
        if (statusFilter === 'REVOKED' && !lic.is_revoked) return false;
        if (statusFilter === 'DISABLED' && (lic.is_enabled || lic.is_revoked)) return false;
        if (statusFilter === 'EXPIRED') {
          const isExpired = lic.status === 'EXPIRED' || lic.expiry_date < todayString();
          if (!isExpired || lic.is_revoked) return false;
        }
        if (statusFilter === 'ACTIVE') {
          if (lic.is_revoked || !lic.is_enabled || lic.expiry_date < todayString()) return false;
        }
      }

      // Type filter
      if (typeFilter !== 'ALL') {
        const licType = lic.licence_type || (lic.notes?.includes('Type:') ? 'OTHER' : 'ONE_YEAR');
        if (licType !== typeFilter) return false;
      }

      return true;
    });
  }, [licences, customers, products, searchQuery, statusFilter, typeFilter]);

  // Paginated licences
  const totalItems = filteredLicences.length;
  const paginatedLicences = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredLicences.slice(start, start + pageSize);
  }, [filteredLicences, currentPage, pageSize]);

  // Reset page when filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter, typeFilter]);

  const handleToggleKey = async (lic) => {
    if (revealedKeys[lic.id]) {
      setRevealedKeys((prev) => {
        const copy = { ...prev };
        delete copy[lic.id];
        return copy;
      });
      return;
    }

    setLoadingKeyId(lic.id);
    try {
      const res = await revealProductKey(lic.id);
      setRevealedKeys((prev) => ({ ...prev, [lic.id]: res.product_key }));
    } catch (err) {
      toast.error(err.message || 'Failed to reveal product key');
    } finally {
      setLoadingKeyId(null);
    }
  };

  const handleCopyKey = async (licId, keyStr) => {
    try {
      await navigator.clipboard.writeText(keyStr);
      setCopiedId(licId);
      toast.success('Key copied to clipboard');
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      toast.error('Failed to copy key');
    }
  };

  const handleSendEmail = async (lic) => {
    setSendingEmailId(lic.id);
    try {
      await sendLicenceEmail(lic.id);
    } finally {
      setSendingEmailId(null);
    }
  };

  const handleConfirmRevoke = async () => {
    if (!revokingLicence) return;
    setRevoking(true);
    try {
      await revokeLicence(revokingLicence.id);
      setRevokingLicence(null);
    } finally {
      setRevoking(false);
    }
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editingLicence) return;
    const form = e.currentTarget;
    const formData = new FormData(form);

    const updates = {
      start_date: formData.get('start_date'),
      expiry_date: formData.get('expiry_date'),
      max_devices: Number(formData.get('max_devices')),
      notes: formData.get('notes'),
    };

    try {
      await updateLicence(editingLicence.id, updates);
      setEditingLicence(null);
    } catch {
      // handled
    }
  };

  const handleCreateSubmit = async (e) => {
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
      setCreateModalOpen(false);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Page Title & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
            Licence Management
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Create, inspect, toggle, and revoke customer activation entitlements.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreateModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm shadow-emerald-600/20 transition-all self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>Create Licence</span>
        </button>
      </div>

      {/* Filters & Search Bar */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 shadow-sm flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="w-full md:w-80">
          <SearchInput
            value={searchQuery}
            onChange={(val) => {
              setSearchQuery(val);
              if (val) {
                setSearchParams({ q: val });
              } else {
                setSearchParams({});
              }
            }}
            placeholder="Search by customer, key, email…"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          {/* Status filter */}
          <div className="flex items-center gap-2 text-xs">
            <Filter className="w-3.5 h-3.5 text-gray-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="ACTIVE">Active Only</option>
              <option value="EXPIRED">Expired</option>
              <option value="DISABLED">Disabled</option>
              <option value="REVOKED">Revoked</option>
            </select>
          </div>

          {/* Licence Type Filter */}
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value="ALL">All Types</option>
            <option value="TRIAL">Trial (30 days)</option>
            <option value="THREE_MONTHS">3 Months</option>
            <option value="SIX_MONTHS">6 Months</option>
            <option value="ONE_YEAR">1 Year</option>
            <option value="LIFETIME">Lifetime</option>
          </select>
        </div>
      </div>

      {/* Main Licences Table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden flex flex-col">
        <div className="overflow-x-auto">
          {paginatedLicences.length === 0 ? (
            <div className="p-8">
              <EmptyState
                icon={Key}
                title="No licences match your criteria"
                description={
                  searchQuery || statusFilter !== 'ALL' || typeFilter !== 'ALL'
                    ? 'Try clearing or modifying your search filters.'
                    : 'Get started by creating your very first customer licence.'
                }
                action={
                  searchQuery || statusFilter !== 'ALL' || typeFilter !== 'ALL' ? (
                    <button
                      type="button"
                      onClick={() => {
                        setSearchQuery('');
                        setStatusFilter('ALL');
                        setTypeFilter('ALL');
                        setSearchParams({});
                      }}
                      className="px-3.5 py-1.5 text-xs font-semibold bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 rounded-lg transition-colors"
                    >
                      Clear Filters
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setCreateModalOpen(true)}
                      className="px-4 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors"
                    >
                      + Create Licence
                    </button>
                  )
                }
              />
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-850/80 text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700 uppercase font-semibold">
                  <th className="px-4 py-3">#ID</th>
                  <th className="px-4 py-3">Customer</th>
                  <th className="px-4 py-3">Product Key</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Valid Period</th>
                  <th className="px-4 py-3 text-center">Devices</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700/60">
                {paginatedLicences.map((lic) => {
                  const customer = customers.find((c) => c.id === lic.customer_id);
                  const product = products.find((p) => p.id === lic.product_id);
                  const isRevealed = Boolean(revealedKeys[lic.id]);
                  const keyText = isRevealed ? revealedKeys[lic.id] : lic.masked_product_key;

                  return (
                    <tr
                      key={lic.id}
                      className="hover:bg-gray-50/70 dark:hover:bg-gray-750/50 transition-colors"
                    >
                      <td className="px-4 py-3 font-mono text-gray-400 dark:text-gray-500">
                        #{lic.id}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-semibold text-gray-900 dark:text-white">
                          {customer?.name || `Customer #${lic.customer_id}`}
                        </div>
                        <div className="text-gray-500 dark:text-gray-400 text-[11px]">
                          {customer?.email || '—'}
                        </div>
                        {product && (
                          <span className="inline-block mt-0.5 text-[10px] text-gray-400 dark:text-gray-500">
                            {product.name}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="inline-flex items-center gap-1.5 bg-gray-50 dark:bg-gray-900 p-1 px-2 rounded-lg border border-gray-200/60 dark:border-gray-800">
                          <code className="font-mono text-[11px] text-gray-800 dark:text-gray-200">
                            {keyText}
                          </code>
                          <button
                            type="button"
                            onClick={() => handleToggleKey(lic)}
                            disabled={loadingKeyId === lic.id}
                            className="p-1 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 rounded transition-colors"
                            title={isRevealed ? 'Hide' : 'Reveal Product Key'}
                          >
                            {isRevealed ? (
                              <EyeOff className="w-3.5 h-3.5" />
                            ) : (
                              <Eye className="w-3.5 h-3.5" />
                            )}
                          </button>
                          {isRevealed && (
                            <button
                              type="button"
                              onClick={() => handleCopyKey(lic.id, keyText)}
                              className="p-1 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 rounded transition-colors"
                              title="Copy unmasked key"
                            >
                              {copiedId === lic.id ? (
                                <Check className="w-3.5 h-3.5 text-emerald-600" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-[11px] font-medium text-gray-700 dark:text-gray-300">
                          {lic.licence_type || 'STANDARD'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <LicenceStatusBadge
                          status={lic.status}
                          isEnabled={lic.is_enabled}
                          isRevoked={lic.is_revoked}
                        />
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-gray-600 dark:text-gray-300">
                        {formatDate(lic.start_date || lic.issue_date)}
                        <span className="text-gray-300 dark:text-gray-600 mx-1">→</span>
                        {formatDate(lic.expiry_date)}
                      </td>
                      <td className="px-4 py-3 text-center font-semibold text-gray-700 dark:text-gray-300">
                        {lic.max_devices}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex items-center gap-1">
                          {/* Edit inline modal */}
                          <button
                            type="button"
                            onClick={() => setEditingLicence(lic)}
                            className="p-1.5 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
                            title="Edit Licence"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>

                          {/* Enable/Disable */}
                          {!lic.is_revoked && (
                            <button
                              type="button"
                              onClick={() => toggleLicenceStatus(lic)}
                              className={`p-1.5 rounded-md transition-colors ${
                                lic.is_enabled
                                  ? 'text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-950/40'
                                  : 'text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950/40'
                              }`}
                              title={lic.is_enabled ? 'Disable Licence' : 'Enable Licence'}
                            >
                              <Power className="w-3.5 h-3.5" />
                            </button>
                          )}

                          {/* Email key */}
                          <button
                            type="button"
                            onClick={() => handleSendEmail(lic)}
                            disabled={sendingEmailId === lic.id || lic.is_revoked}
                            className="p-1.5 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/40 rounded-md transition-colors disabled:opacity-40"
                            title="Send Licence Key via Email"
                          >
                            <Mail className="w-3.5 h-3.5" />
                          </button>

                          {/* Revoke */}
                          {!lic.is_revoked && (
                            <button
                              type="button"
                              onClick={() => setRevokingLicence(lic)}
                              className="p-1.5 text-red-500 hover:text-red-700 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 rounded-md transition-colors"
                              title="Permanently Revoke"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination bar */}
        <Pagination
          currentPage={currentPage}
          totalItems={totalItems}
          pageSize={pageSize}
          onPageChange={setCurrentPage}
        />
      </div>

      {/* Edit Licence Modal */}
      <Modal
        isOpen={Boolean(editingLicence)}
        onClose={() => setEditingLicence(null)}
        title={`Edit Licence #${editingLicence?.id}`}
        subtitle="Modify active dates, device concurrency, or notes."
        maxWidth="max-w-md"
      >
        {editingLicence && (
          <form onSubmit={handleEditSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                Start Date
              </label>
              <input
                name="start_date"
                type="date"
                required
                defaultValue={editingLicence.start_date || editingLicence.issue_date}
                className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                Expiry Date
              </label>
              <input
                name="expiry_date"
                type="date"
                required
                defaultValue={editingLicence.expiry_date}
                className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                Device Limit
              </label>
              <input
                name="max_devices"
                type="number"
                min="1"
                max="100"
                required
                defaultValue={editingLicence.max_devices}
                className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                Notes
              </label>
              <textarea
                name="notes"
                maxLength={1000}
                rows={3}
                defaultValue={editingLicence.notes || ''}
                className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-gray-100 dark:border-gray-700">
              <button
                type="button"
                onClick={() => setEditingLicence(null)}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm"
              >
                Save Changes
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* Revoke Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(revokingLicence)}
        onClose={() => setRevokingLicence(null)}
        onConfirm={handleConfirmRevoke}
        loading={revoking}
        title={`Revoke Licence #${revokingLicence?.id}?`}
        message="Permanently revoking this licence will instantly invalidate the product key on all connected client devices. This action cannot be reversed."
        confirmText="Revoke Licence"
        tone="danger"
      />

      {/* Create Licence Modal */}
      <Modal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Create Customer Licence"
        subtitle="Issue an encrypted product key and trigger activation dispatch."
        maxWidth="max-w-xl"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
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
              onClick={() => setCreateModalOpen(false)}
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
      </Modal>
    </div>
  );
}
