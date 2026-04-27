import { useMemo, useState } from 'react'
import {
  type ColumnDef, flexRender, getCoreRowModel, getFilteredRowModel,
  getPaginationRowModel, getSortedRowModel, useReactTable,
  type SortingState, type ColumnFiltersState,
} from '@tanstack/react-table'
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Search } from 'lucide-react'

interface Props {
  rows: Record<string, any>[]
  columns: string[]                       // visible column names (in order)
  defaultSort?: string | null
  defaultSortDesc?: boolean
  pageSize?: number
  height?: number
  searchable?: boolean
  perColumnFilter?: boolean
}

export default function InteractiveTable({
  rows, columns, defaultSort, defaultSortDesc = false,
  pageSize = 25, height = 320, searchable = true, perColumnFilter = false,
}: Props) {
  const [sorting, setSorting] = useState<SortingState>(
    defaultSort ? [{ id: defaultSort, desc: defaultSortDesc }] : []
  )
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [globalFilter, setGlobalFilter] = useState('')
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize })

  const tableColumns = useMemo<ColumnDef<Record<string, any>>[]>(() => {
    return columns.map((col) => ({
      accessorKey: col,
      header: col,
      cell: ({ getValue }) => formatCell(getValue()),
      filterFn: 'includesString',
    }))
  }, [columns])

  const table = useReactTable({
    data: rows,
    columns: tableColumns,
    state: { sorting, columnFilters, globalFilter, pagination },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: setPagination,
    globalFilterFn: 'includesString',
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  })

  const totalRows = table.getFilteredRowModel().rows.length
  const pageCount = table.getPageCount()
  const { pageIndex } = table.getState().pagination
  const fromRow = pageIndex * pagination.pageSize + 1
  const toRow = Math.min(fromRow + pagination.pageSize - 1, totalRows)

  return (
    <div>
      {searchable && (
        <div className="relative mb-2">
          <Search
            size={12}
            className="absolute left-2.5 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--text-muted)' }}
          />
          <input
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            placeholder={`Filter ${rows.length.toLocaleString()} rows…`}
            className="w-full pl-7 pr-3 py-1.5 rounded-md text-xs"
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              color: 'var(--text-primary)',
            }}
          />
        </div>
      )}

      <div
        className="overflow-auto rounded-lg"
        style={{ border: '1px solid var(--border)', maxHeight: height }}
      >
        <table className="w-full text-xs font-mono">
          <thead style={{ background: 'var(--bg-elevated)', position: 'sticky', top: 0, zIndex: 1 }}>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => {
                  const sorted = header.column.getIsSorted()
                  return (
                    <th
                      key={header.id}
                      onClick={header.column.getCanSort() ? header.column.getToggleSortingHandler() : undefined}
                      className="text-left py-1.5 px-3 whitespace-nowrap cursor-pointer select-none"
                      style={{
                        fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
                        textTransform: 'uppercase', color: 'var(--text-secondary)',
                        borderBottom: '1px solid var(--border)',
                      }}
                    >
                      <span className="flex items-center gap-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {sorted === 'asc' && <ArrowUp size={10} style={{ color: 'var(--accent)' }} />}
                        {sorted === 'desc' && <ArrowDown size={10} style={{ color: 'var(--accent)' }} />}
                      </span>
                    </th>
                  )
                })}
              </tr>
            ))}

            {perColumnFilter && (
              <tr>
                {table.getHeaderGroups()[0].headers.map((header) => (
                  <th key={`f-${header.id}`} className="px-3 pb-1.5" style={{ background: 'var(--bg-elevated)' }}>
                    <input
                      value={(header.column.getFilterValue() as string) ?? ''}
                      onChange={(e) => header.column.setFilterValue(e.target.value)}
                      placeholder="filter"
                      className="w-full px-1.5 py-0.5 rounded text-[10px]"
                      style={{
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border)',
                        color: 'var(--text-primary)',
                      }}
                    />
                  </th>
                ))}
              </tr>
            )}
          </thead>
          <tbody>
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="text-center py-6"
                  style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}
                >
                  No matching rows
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="py-1.5 px-3 whitespace-nowrap"
                      style={{ borderBottom: '1px solid var(--border-subtle)' }}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination strip */}
      {pageCount > 1 && (
        <div
          className="flex items-center justify-between mt-2 px-1 text-[11px]"
          style={{ color: 'var(--text-muted)' }}
        >
          <div className="flex items-center gap-2">
            <span>
              {fromRow.toLocaleString()}–{toRow.toLocaleString()} of {totalRows.toLocaleString()}
              {totalRows !== rows.length && ` (filtered from ${rows.length.toLocaleString()})`}
            </span>
            <select
              value={pagination.pageSize}
              onChange={(e) => setPagination((p) => ({ ...p, pageSize: Number(e.target.value), pageIndex: 0 }))}
              className="rounded px-1 py-0.5"
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                color: 'var(--text-secondary)', fontSize: 10,
              }}
            >
              {[10, 25, 50, 100].map((n) => (
                <option key={n} value={n}>{n} / page</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              className="p-1 rounded disabled:opacity-30"
              style={{ color: 'var(--text-secondary)' }}
            >
              <ChevronLeft size={12} />
            </button>
            <span className="font-mono px-1.5">
              {pageIndex + 1} / {pageCount}
            </span>
            <button
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              className="p-1 rounded disabled:opacity-30"
              style={{ color: 'var(--text-secondary)' }}
            >
              <ChevronRight size={12} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function formatCell(v: any): string {
  if (v == null) return '—'
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toLocaleString()
    return Math.abs(v) < 0.0001 || Math.abs(v) >= 1e9 ? v.toExponential(3) : v.toFixed(4)
  }
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
