export default function EmptyState({
  icon: Icon,
  title = 'No items found',
  description = 'There are no records matching your criteria.',
  action,
  className = '',
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 sm:p-12 text-center rounded-xl border border-dashed border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-850/50 ${className}`}
    >
      {Icon && (
        <div className="p-3 mb-4 rounded-xl bg-white dark:bg-gray-800 text-gray-400 dark:text-gray-500 shadow-sm border border-gray-100 dark:border-gray-700">
          <Icon className="w-8 h-8" />
        </div>
      )}
      <h3 className="text-base font-semibold text-gray-900 dark:text-white">
        {title}
      </h3>
      {description && (
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400 max-w-sm">
          {description}
        </p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
