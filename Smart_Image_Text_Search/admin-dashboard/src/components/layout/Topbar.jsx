import { useState, useRef, useEffect } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import {
  Bell,
  Plus,
  Sun,
  Moon,
  LogOut,
  ChevronRight,
  Shield,
  RefreshCw,
  Search,
} from 'lucide-react';
import { useData } from '../../hooks/useApi';

export default function Topbar({
  onOpenCreateLicence,
  adminEmail = 'admin@scanora.prakshal.com',
  onLogout,
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const { loading, refreshData } = useData();

  const [darkMode, setDarkMode] = useState(() => {
    return document.documentElement.classList.contains('dark') ||
      localStorage.getItem('scanora-theme') === 'dark';
  });

  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [globalSearch, setGlobalSearch] = useState('');
  const userMenuRef = useRef(null);
  const notifRef = useRef(null);

  // Sync theme
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('scanora-theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('scanora-theme', 'light');
    }
  }, [darkMode]);

  // Click outside listener for dropdowns
  useEffect(() => {
    function handleClickOutside(e) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setUserMenuOpen(false);
      }
      if (notifRef.current && !notifRef.current.contains(e.target)) {
        setNotifOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Compute breadcrumbs
  const getBreadcrumb = () => {
    const path = location.pathname;
    if (path === '/') return 'Dashboard';
    if (path.startsWith('/licences')) return 'Licences';
    if (path.startsWith('/customers')) return 'Customers';
    if (path.startsWith('/email')) return 'Email Delivery';
    if (path.startsWith('/settings')) return 'Settings';
    return 'Portal';
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (!globalSearch.trim()) return;
    // Route to licences page with query if not already there
    navigate(`/licences?q=${encodeURIComponent(globalSearch.trim())}`);
  };

  return (
    <header className="sticky top-0 z-30 h-16 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-800 px-6 flex items-center justify-between gap-4">
      {/* Left: Breadcrumbs */}
      <div className="flex items-center gap-2 text-sm">
        <Link
          to="/"
          className="text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 font-medium transition-colors"
        >
          Portal
        </Link>
        <ChevronRight className="w-4 h-4 text-gray-400 dark:text-gray-600" />
        <span className="font-semibold text-gray-900 dark:text-white">
          {getBreadcrumb()}
        </span>
      </div>

      {/* Center: Search Bar */}
      <form
        onSubmit={handleSearchSubmit}
        className="hidden md:flex items-center flex-1 max-w-md mx-4"
      >
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={globalSearch}
            onChange={(e) => setGlobalSearch(e.target.value)}
            placeholder="Search licences, keys, customers… (Press Enter)"
            className="w-full pl-9 pr-4 py-1.5 text-xs bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:bg-white dark:focus:bg-gray-800 transition-all"
          />
        </div>
      </form>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
        {/* Refresh button */}
        <button
          type="button"
          onClick={() => refreshData()}
          disabled={loading}
          className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
          title="Refresh Data"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-emerald-600' : ''}`} />
        </button>

        {/* Theme Toggle */}
        <button
          type="button"
          onClick={() => setDarkMode(!darkMode)}
          className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
          title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
          {darkMode ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-gray-500" />
          )}
        </button>

        {/* Notifications Dropdown */}
        <div className="relative" ref={notifRef}>
          <button
            type="button"
            onClick={() => setNotifOpen(!notifOpen)}
            className="relative p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
            title="Notifications"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-emerald-500 ring-2 ring-white dark:ring-gray-900" />
          </button>

          {notifOpen && (
            <div className="absolute right-0 mt-2 w-72 bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-100 dark:border-gray-700 py-2 z-50 text-xs">
              <div className="px-4 py-2 font-semibold text-gray-900 dark:text-white border-b border-gray-100 dark:border-gray-700">
                System Activity
              </div>
              <div className="p-3 text-gray-600 dark:text-gray-300 space-y-2">
                <div className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
                  <p>Licensing engine is running normally and connected to database.</p>
                </div>
                <div className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5 shrink-0" />
                  <p>SMTP status can be monitored in the Email Delivery tab.</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Quick Action: Create Licence */}
        <button
          type="button"
          onClick={onOpenCreateLicence}
          className="hidden sm:inline-flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white px-3.5 py-1.5 rounded-lg font-medium text-xs shadow-sm transition-all shadow-emerald-600/20 active:scale-95"
        >
          <Plus className="w-4 h-4" />
          <span>New Licence</span>
        </button>

        {/* User Avatar + Dropdown */}
        <div className="relative" ref={userMenuRef}>
          <button
            type="button"
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2 p-1 pl-1.5 pr-2.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 border border-transparent hover:border-gray-200 dark:hover:border-gray-700 transition-all"
          >
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 text-white font-semibold text-xs flex items-center justify-center shadow-sm">
              A
            </div>
            <span className="text-xs font-semibold text-gray-800 dark:text-gray-200 hidden lg:inline">
              Admin
            </span>
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-100 dark:border-gray-700 py-1.5 z-50 animate-fadeIn">
              <div className="px-3.5 py-2 border-b border-gray-100 dark:border-gray-700">
                <p className="text-xs font-semibold text-gray-900 dark:text-white">
                  Admin Operator
                </p>
                <p className="text-[11px] text-gray-500 dark:text-gray-400 truncate">
                  {adminEmail}
                </p>
              </div>

              <div className="py-1">
                <Link
                  to="/settings"
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-2 px-3.5 py-2 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700/60 transition-colors"
                >
                  <Shield className="w-4 h-4 text-gray-400" />
                  <span>Portal Settings</span>
                </Link>
              </div>

              <div className="border-t border-gray-100 dark:border-gray-700 pt-1">
                <button
                  type="button"
                  onClick={() => {
                    setUserMenuOpen(false);
                    onLogout();
                  }}
                  className="w-full flex items-center gap-2 px-3.5 py-2 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign out</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
