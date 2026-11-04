import { useState, useMemo } from 'react';
import { useData } from '../hooks/useApi';
import { LicenceStatusBadge } from '../components/ui/Badge';
import SearchInput from '../components/ui/SearchInput';
import Modal from '../components/ui/Modal';
import EmptyState from '../components/ui/EmptyState';
import { formatDate } from '../api';
import {
  Users,
  Plus,
  Building,
  Mail,
  Phone,
  Hash,
  Key,
  ChevronDown,
  ChevronUp,
  Package,
} from 'lucide-react';

export default function CustomersPage() {
  const {
    customers,
    licences,
    products,
    createCustomer,
    createProduct,
    loading,
  } = useData();

  const [searchQuery, setSearchQuery] = useState('');
  const [expandedCustomerId, setExpandedCustomerId] = useState(null);

  // Add Customer Modal
  const [addCustomerOpen, setAddCustomerOpen] = useState(false);
  const [addingCustomer, setAddingCustomer] = useState(false);

  // Add Product Modal
  const [addProductOpen, setAddProductOpen] = useState(false);
  const [addingProduct, setAddingProduct] = useState(false);

  // Filtered customer list
  const filteredCustomers = useMemo(() => {
    return customers.filter((c) => {
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        c.name?.toLowerCase().includes(q) ||
        c.email?.toLowerCase().includes(q) ||
        c.company_name?.toLowerCase().includes(q) ||
        c.phone?.toLowerCase().includes(q) ||
        c.order_reference?.toLowerCase().includes(q)
      );
    });
  }, [customers, searchQuery]);

  const handleCreateCustomerSubmit = async (e) => {
    e.preventDefault();
    setAddingCustomer(true);
    const form = e.currentTarget;
    const formData = new FormData(form);

    const payload = {
      name: formData.get('name')?.trim(),
      email: formData.get('email')?.trim(),
      company_name: formData.get('company_name')?.trim() || null,
      phone: formData.get('phone')?.trim() || null,
      order_reference: formData.get('order_reference')?.trim() || null,
    };

    try {
      await createCustomer(payload);
      setAddCustomerOpen(false);
      form.reset();
    } catch {
      // toast shown in useApi
    } finally {
      setAddingCustomer(false);
    }
  };

  const handleCreateProductSubmit = async (e) => {
    e.preventDefault();
    setAddingProduct(true);
    const form = e.currentTarget;
    const formData = new FormData(form);

    const payload = {
      name: formData.get('name')?.trim(),
      sku: formData.get('sku')?.trim(),
      description: formData.get('description')?.trim() || '',
    };

    try {
      await createProduct(payload);
      setAddProductOpen(false);
      form.reset();
    } catch {
      // toast shown in useApi
    } finally {
      setAddingProduct(false);
    }
  };

  const toggleExpand = (id) => {
    setExpandedCustomerId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Page Header & Action Buttons */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
            Customers & Products
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Manage customer directories, registered organizations, and catalog SKUs.
          </p>
        </div>
        <div className="flex items-center gap-2.5 self-start sm:self-auto">
          <button
            type="button"
            onClick={() => setAddProductOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/60 rounded-lg shadow-xs transition-colors"
          >
            <Package className="w-3.5 h-3.5" />
            <span>Add Product</span>
          </button>
          <button
            type="button"
            onClick={() => setAddCustomerOpen(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm shadow-emerald-600/20 transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Add Customer</span>
          </button>
        </div>
      </div>

      {/* Search and Summary */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="w-full sm:w-80">
          <SearchInput
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search by name, company, email, phone…"
          />
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400 font-medium">
          Total Customers:{' '}
          <span className="font-semibold text-gray-900 dark:text-white">
            {customers.length}
          </span>{' '}
          · Products:{' '}
          <span className="font-semibold text-gray-900 dark:text-white">
            {products.length}
          </span>
        </div>
      </div>

      {/* Customers List / Table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
        {filteredCustomers.length === 0 ? (
          <div className="p-8">
            <EmptyState
              icon={Users}
              title="No customers found"
              description={
                searchQuery
                  ? 'No results match your search query.'
                  : 'Get started by creating your first client customer record.'
              }
              action={
                searchQuery ? (
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    className="px-3 py-1.5 text-xs font-semibold bg-gray-100 hover:bg-gray-200 rounded-lg"
                  >
                    Clear Search
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setAddCustomerOpen(true)}
                    className="px-4 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg"
                  >
                    + Add Customer
                  </button>
                )
              }
            />
          </div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-700/70">
            {filteredCustomers.map((cust) => {
              const customerLicences = licences.filter((l) => l.customer_id === cust.id);
              const isExpanded = expandedCustomerId === cust.id;

              return (
                <div key={cust.id} className="transition-colors">
                  <div
                    onClick={() => toggleExpand(cust.id)}
                    className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-gray-50/70 dark:hover:bg-gray-750/50 cursor-pointer select-none"
                  >
                    {/* Customer Info */}
                    <div className="flex items-start sm:items-center gap-3.5 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-950/80 border border-emerald-200 dark:border-emerald-800 flex items-center justify-center text-emerald-800 dark:text-emerald-300 font-bold text-sm shrink-0">
                        {cust.name?.charAt(0)?.toUpperCase() || 'C'}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <h4 className="text-sm font-semibold text-gray-900 dark:text-white truncate">
                            {cust.name}
                          </h4>
                          {cust.order_reference && (
                            <span className="text-[10px] font-mono bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-1.5 py-0.5 rounded">
                              {cust.order_reference}
                            </span>
                          )}
                        </div>
                        <div className="flex flex-wrap items-center gap-y-1 gap-x-3 text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          <span className="flex items-center gap-1">
                            <Mail className="w-3 h-3 text-gray-400" />
                            {cust.email}
                          </span>
                          {cust.company_name && (
                            <span className="flex items-center gap-1">
                              <Building className="w-3 h-3 text-gray-400" />
                              {cust.company_name}
                            </span>
                          )}
                          {cust.phone && (
                            <span className="flex items-center gap-1">
                              <Phone className="w-3 h-3 text-gray-400" />
                              {cust.phone}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Stats & Expand Toggle */}
                    <div className="flex items-center justify-between sm:justify-end gap-4 shrink-0 pl-13 sm:pl-0">
                      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/60">
                        <Key className="w-3 h-3" />
                        <span>
                          {customerLicences.length} {customerLicences.length === 1 ? 'Licence' : 'Licences'}
                        </span>
                      </div>
                      <button
                        type="button"
                        className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-md transition-colors"
                        title={isExpanded ? 'Collapse' : 'Expand licences'}
                      >
                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Expanded Licences Panel */}
                  {isExpanded && (
                    <div className="px-4 sm:px-6 py-4 bg-gray-50/80 dark:bg-gray-850/60 border-t border-gray-100 dark:border-gray-700/60 animate-fadeIn">
                      <h5 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3 flex items-center gap-1.5">
                        <Key className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Assigned Product Licences</span>
                      </h5>

                      {customerLicences.length === 0 ? (
                        <div className="text-xs text-gray-500 dark:text-gray-400 italic py-2">
                          No licences assigned to this customer yet. You can create one from the Licences tab.
                        </div>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full text-left text-xs bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                            <thead>
                              <tr className="bg-gray-100/70 dark:bg-gray-750 text-gray-600 dark:text-gray-300 border-b border-gray-200 dark:border-gray-700 font-semibold">
                                <th className="px-3 py-2">ID</th>
                                <th className="px-3 py-2">Product</th>
                                <th className="px-3 py-2">Masked Key</th>
                                <th className="px-3 py-2">Type</th>
                                <th className="px-3 py-2">Status</th>
                                <th className="px-3 py-2">Expiry</th>
                                <th className="px-3 py-2">Devices</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
                              {customerLicences.map((lic) => {
                                const prod = products.find((p) => p.id === lic.product_id);
                                return (
                                  <tr key={lic.id} className="hover:bg-gray-50 dark:hover:bg-gray-750/30">
                                    <td className="px-3 py-2 font-mono text-gray-400">#{lic.id}</td>
                                    <td className="px-3 py-2 font-medium text-gray-800 dark:text-gray-200">
                                      {prod?.name || `Product #${lic.product_id}`}
                                    </td>
                                    <td className="px-3 py-2 font-mono text-gray-600 dark:text-gray-300">
                                      {lic.masked_product_key}
                                    </td>
                                    <td className="px-3 py-2 text-gray-600 dark:text-gray-300">
                                      {lic.licence_type || 'ONE_YEAR'}
                                    </td>
                                    <td className="px-3 py-2">
                                      <LicenceStatusBadge
                                        status={lic.status}
                                        isEnabled={lic.is_enabled}
                                        isRevoked={lic.is_revoked}
                                      />
                                    </td>
                                    <td className="px-3 py-2 text-gray-600 dark:text-gray-300 whitespace-nowrap">
                                      {formatDate(lic.expiry_date)}
                                    </td>
                                    <td className="px-3 py-2 text-center text-gray-700 dark:text-gray-300">
                                      {lic.max_devices}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Add Customer Modal */}
      <Modal
        isOpen={addCustomerOpen}
        onClose={() => setAddCustomerOpen(false)}
        title="Add Customer"
        subtitle="Register a new customer account or organization."
        maxWidth="max-w-md"
      >
        <form onSubmit={handleCreateCustomerSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
              Full Name *
            </label>
            <input
              name="name"
              required
              minLength={2}
              maxLength={255}
              placeholder="e.g. John Doe"
              className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
              Email Address *
            </label>
            <input
              name="email"
              type="email"
              required
              maxLength={255}
              placeholder="john@example.com"
              className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
              Company Name
            </label>
            <input
              name="company_name"
              maxLength={255}
              placeholder="Acme Corporation"
              className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                Phone Number
              </label>
              <input
                name="phone"
                maxLength={50}
                placeholder="+91 98765 43210"
                className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                Order Reference
              </label>
              <input
                name="order_reference"
                maxLength={255}
                placeholder="INV-2026-001"
                className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-gray-100 dark:border-gray-700">
            <button
              type="button"
              onClick={() => setAddCustomerOpen(false)}
              className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={addingCustomer}
              className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition-colors disabled:opacity-50"
            >
              {addingCustomer ? 'Adding…' : 'Create Customer'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Add Product Modal */}
      <Modal
        isOpen={addProductOpen}
        onClose={() => setAddProductOpen(false)}
        title="Add Product SKU"
        subtitle="Define a software tier or product edition."
        maxWidth="max-w-md"
      >
        <form onSubmit={handleCreateProductSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
              Product Name *
            </label>
            <input
              name="name"
              required
              minLength={2}
              maxLength={255}
              placeholder="e.g. Scanora Professional"
              className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
              SKU Identifier *
            </label>
            <input
              name="sku"
              required
              minLength={2}
              maxLength={100}
              placeholder="SCAN-PRO-2026"
              className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
              Description
            </label>
            <textarea
              name="description"
              maxLength={1000}
              rows={2}
              placeholder="Product edition details and licensing features…"
              className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-gray-100 dark:border-gray-700">
            <button
              type="button"
              onClick={() => setAddProductOpen(false)}
              className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={addingProduct}
              className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition-colors disabled:opacity-50"
            >
              {addingProduct ? 'Creating…' : 'Create Product'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
