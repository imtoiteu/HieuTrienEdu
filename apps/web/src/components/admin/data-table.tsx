'use client';

import {
  ArrowDown,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  Search,
  SlidersHorizontal,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { Button, EmptyState, Spinner, cn } from '@hietedu/ui';

import { useI18n } from '@/lib/i18n';

export interface Column<T> {
  key: string;
  header: string;
  /** Column key to send as `sort`; omit to make the column unsortable. */
  sortKey?: string;
  render: (row: T) => ReactNode;
  className?: string;
  /** Hide below the `sm` breakpoint — tables must stay readable on a phone. */
  hideOnMobile?: boolean;
}

export interface FilterOption {
  key: string;
  label: string;
  options: { value: string; label: string }[];
}

/**
 * The one table every admin list uses.
 *
 * Server-driven: it holds search/sort/page state and calls back, rather than receiving a full
 * array and slicing it. Loading a thousand students into the browser to show twenty-five is the
 * failure mode this deliberately makes impossible.
 */
export function DataTable<T extends { id: number }>({
  columns,
  rows,
  total,
  page,
  pageSize,
  pages,
  loading,
  search,
  onSearchChange,
  sort,
  order,
  onSortChange,
  onPageChange,
  filters,
  filterValues,
  onFilterChange,
  emptyTitle,
  emptyBody,
  emptyAction,
  actions,
  selectable,
  selectedIds,
  onSelectionChange,
  rowHref,
  onRowClick,
}: {
  columns: Column<T>[];
  rows: T[];
  total: number;
  page: number;
  pageSize: number;
  pages: number;
  loading?: boolean;
  search?: string;
  onSearchChange?: (value: string) => void;
  sort?: string;
  order?: 'asc' | 'desc';
  onSortChange?: (sort: string, order: 'asc' | 'desc') => void;
  onPageChange: (page: number) => void;
  filters?: FilterOption[];
  filterValues?: Record<string, string>;
  onFilterChange?: (key: string, value: string) => void;
  emptyTitle?: string;
  emptyBody?: string;
  emptyAction?: ReactNode;
  actions?: ReactNode;
  selectable?: boolean;
  selectedIds?: number[];
  onSelectionChange?: (ids: number[]) => void;
  rowHref?: (row: T) => string;
  onRowClick?: (row: T) => void;
}) {
  const { t } = useI18n();
  const [searchDraft, setSearchDraft] = useState(search ?? '');
  const [showFilters, setShowFilters] = useState(false);
  const firstRender = useRef(true);

  // Debounce search so typing does not fire a request per keystroke.
  useEffect(() => {
    if (!onSearchChange) return;
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const timer = window.setTimeout(() => onSearchChange(searchDraft), 300);
    return () => window.clearTimeout(timer);
  }, [searchDraft, onSearchChange]);

  const activeFilterCount = useMemo(
    () => Object.values(filterValues ?? {}).filter(Boolean).length,
    [filterValues],
  );

  const allSelected = rows.length > 0 && rows.every((row) => selectedIds?.includes(row.id));

  function toggleSort(column: Column<T>) {
    if (!column.sortKey || !onSortChange) return;
    const nextOrder = sort === column.sortKey && order === 'asc' ? 'desc' : 'asc';
    onSortChange(column.sortKey, nextOrder);
  }

  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="rounded-3xl border-2 border-ink-100 bg-white">
      {/* toolbar */}
      <div className="flex flex-wrap items-center gap-3 border-b-2 border-ink-100 p-4">
        {onSearchChange && (
          <div className="relative min-w-0 flex-1 sm:max-w-xs">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
              aria-hidden="true"
            />
            <input
              type="search"
              value={searchDraft}
              onChange={(event) => setSearchDraft(event.target.value)}
              placeholder={t('admin.a.search')}
              aria-label={t('admin.a.searchLabel')}
              className="w-full rounded-xl border-2 border-ink-200 py-2 pl-9 pr-3 text-sm outline-none focus:border-brand-400"
            />
          </div>
        )}

        {filters && filters.length > 0 && (
          <Button
            size="sm"
            variant={activeFilterCount ? 'primary' : 'outline'}
            onClick={() => setShowFilters((value) => !value)}
            aria-expanded={showFilters}
          >
            <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
            {t('admin.a.filters')}
            {activeFilterCount ? ` (${activeFilterCount})` : ''}
          </Button>
        )}

        <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div>
      </div>

      {showFilters && filters && (
        <div className="flex flex-wrap gap-3 border-b-2 border-ink-100 bg-ink-50/60 p-4">
          {filters.map((filter) => (
            <label key={filter.key} className="min-w-[10rem] flex-1 sm:max-w-[14rem]">
              <span className="text-xs font-bold text-ink-600">{filter.label}</span>
              <select
                value={filterValues?.[filter.key] ?? ''}
                onChange={(event) => onFilterChange?.(filter.key, event.target.value)}
                className="mt-1 w-full rounded-xl border-2 border-ink-200 bg-white px-3 py-2 text-sm outline-none focus:border-brand-400"
              >
                <option value="">{t('admin.a.all')}</option>
                {filter.options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          ))}
          {activeFilterCount > 0 && (
            <button
              type="button"
              onClick={() => filters.forEach((filter) => onFilterChange?.(filter.key, ''))}
              className="self-end pb-2 text-sm font-semibold text-brand-600 underline"
            >
              {t('admin.a.clearAll')}
            </button>
          )}
        </div>
      )}

      {/* body */}
      {loading ? (
        <div className="flex items-center justify-center gap-3 py-20 text-ink-500">
          <Spinner className="h-6 w-6 text-brand-500" />
          <span className="text-sm">{t('admin.a.loading')}</span>
        </div>
      ) : rows.length === 0 ? (
        <div className="p-6">
          <EmptyState
            title={emptyTitle ?? t('admin.a.nothingHere')}
            description={emptyBody}
            action={emptyAction}
          />
        </div>
      ) : (
        <div className="scroll-x">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="bg-ink-50">
              <tr>
                {selectable && (
                  <th scope="col" className="w-10 px-4 py-3">
                    <input
                      type="checkbox"
                      aria-label={t('admin.a.selectAll')}
                      checked={allSelected}
                      onChange={(event) =>
                        onSelectionChange?.(event.target.checked ? rows.map((r) => r.id) : [])
                      }
                      className="h-4 w-4 rounded border-ink-300"
                    />
                  </th>
                )}
                {columns.map((column) => (
                  <th
                    key={column.key}
                    scope="col"
                    className={cn(
                      'px-4 py-3 font-display text-ink-800',
                      column.hideOnMobile && 'hidden sm:table-cell',
                      column.className,
                    )}
                  >
                    {column.sortKey ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(column)}
                        className="inline-flex items-center gap-1 hover:text-brand-700"
                      >
                        {column.header}
                        {sort === column.sortKey &&
                          (order === 'asc' ? (
                            <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
                          ) : (
                            <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
                          ))}
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={cn(
                    'border-t border-ink-100',
                    (onRowClick || rowHref) && 'cursor-pointer hover:bg-brand-50/50',
                  )}
                >
                  {selectable && (
                    <td className="px-4 py-3" onClick={(event) => event.stopPropagation()}>
                      <input
                        type="checkbox"
                        aria-label={`${t('admin.a.selectRow')} ${row.id}`}
                        checked={selectedIds?.includes(row.id) ?? false}
                        onChange={(event) => {
                          const current = selectedIds ?? [];
                          onSelectionChange?.(
                            event.target.checked
                              ? [...current, row.id]
                              : current.filter((id) => id !== row.id),
                          );
                        }}
                        className="h-4 w-4 rounded border-ink-300"
                      />
                    </td>
                  )}
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cn(
                        'px-4 py-3 align-middle',
                        column.hideOnMobile && 'hidden sm:table-cell',
                        column.className,
                      )}
                    >
                      {column.render(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* pagination */}
      {total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t-2 border-ink-100 p-4">
          <p className="text-xs text-ink-600">
            {t('admin.a.showing')} <span className="font-bold text-ink-900">{from}</span>–
            <span className="font-bold text-ink-900">{to}</span> {t('admin.a.of')}{' '}
            <span className="font-bold text-ink-900">{total}</span>
          </p>
          {pages > 1 && (
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => onPageChange(page - 1)}
                aria-label={t('admin.a.previousPage')}
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              </Button>
              <span className="text-xs font-semibold text-ink-700">
                {t('admin.a.pageOf', { page, pages })}
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={page >= pages}
                onClick={() => onPageChange(page + 1)}
                aria-label={t('admin.a.nextPage')}
              >
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
