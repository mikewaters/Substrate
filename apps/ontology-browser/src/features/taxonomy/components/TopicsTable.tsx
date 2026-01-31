import {
  Checkbox,
  Loader,
  ScrollArea,
  Table,
  Text,
  UnstyledButton,
  Group,
  Center,
} from '@mantine/core'
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { IconChevronDown, IconChevronUp } from '@tabler/icons-react'
import { useMemo, type JSX } from 'react'
import type { TopicOverview } from '../../../api/types'
import { StatusBadge } from '../utils/statusBadge'
import type { TopicStatus } from '../utils/statusBadge'

export type TopicSortKey =
  | 'title'
  | 'status'
  | 'child_count'
  | 'created_at'
  | 'updated_at'

type TopicsTableProps = {
  data: TopicOverview[]
  isLoading: boolean
  sortBy: TopicSortKey
  sortOrder: 'asc' | 'desc'
  onSortChange: (column: TopicSortKey) => void
  selectedTopicId: string | null
  onSelect: (topic: TopicOverview) => void
}

const columnHelper = createColumnHelper<TopicOverview>()

export function TopicsTable({
  data,
  isLoading,
  sortBy,
  sortOrder,
  onSortChange,
  selectedTopicId,
  onSelect,
}: TopicsTableProps): JSX.Element {
  const columns = useMemo(
    () => [
      columnHelper.display({
        id: 'select',
        header: () => <Checkbox aria-label="Select all topics" disabled />,
        cell: ({ row }) => (
          <Center>
            <Checkbox
              aria-label={`Select topic ${row.original.topic.title}`}
              checked={row.original.topic.id === selectedTopicId}
              onChange={() => onSelect(row.original)}
            />
          </Center>
        ),
      }),
      columnHelper.accessor((row) => row.topic.title, {
        id: 'title',
        header: () => (
          <SortableHeader
            label="Topic Name"
            isActive={sortBy === 'title'}
            direction={sortOrder}
            onClick={() => onSortChange('title')}
          />
        ),
        cell: ({ row }) => (
          <Text fw={500} lineClamp={1}>
            {row.original.topic.title}
          </Text>
        ),
      }),
      columnHelper.accessor((row) => row.topic.status, {
        id: 'status',
        header: () => (
          <SortableHeader
            label="Status"
            isActive={sortBy === 'status'}
            direction={sortOrder}
            onClick={() => onSortChange('status')}
          />
        ),
        cell: ({ row }) => (
          <StatusBadge status={row.original.topic.status as TopicStatus} />
        ),
      }),
      columnHelper.accessor((row) => row.child_count, {
        id: 'child_count',
        header: () => (
          <SortableHeader
            label="# Children"
            isActive={sortBy === 'child_count'}
            direction={sortOrder}
            onClick={() => onSortChange('child_count')}
          />
        ),
        cell: ({ row }) => row.original.child_count,
      }),
      columnHelper.accessor((row) => row.topic.description ?? '', {
        id: 'description',
        header: () => <Text>Description</Text>,
        cell: ({ row }) => (
          <Text size="sm" c="dimmed" lineClamp={2}>
            {row.original.topic.description ?? '—'}
          </Text>
        ),
      }),
      columnHelper.accessor((row) => row.topic.created_at, {
        id: 'created_at',
        header: () => (
          <SortableHeader
            label="Date added"
            isActive={sortBy === 'created_at'}
            direction={sortOrder}
            onClick={() => onSortChange('created_at')}
          />
        ),
        cell: ({ row }) => formatDate(row.original.topic.created_at),
      }),
      columnHelper.accessor(
        (row) => row.parents?.[0]?.title ?? '—',
        {
          id: 'parent',
          header: () => <Text>Parent topic name</Text>,
          cell: ({ row }) => row.original.parents?.[0]?.title ?? '—',
        },
      ),
    ],
    [onSelect, onSortChange, selectedTopicId, sortBy, sortOrder],
  )

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  return (
    <ScrollArea mah={520}>
      <Table verticalSpacing="sm" highlightOnHover>
        <Table.Thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <Table.Tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <Table.Th key={header.id}>
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                </Table.Th>
              ))}
            </Table.Tr>
          ))}
        </Table.Thead>
        <Table.Tbody>
          {isLoading ? (
            <Table.Tr>
              <Table.Td colSpan={columns.length}>
                <Group justify="center" py="xl">
                  <Loader size="sm" />
                  <Text c="dimmed">Loading topics…</Text>
                </Group>
              </Table.Td>
            </Table.Tr>
          ) : table.getRowModel().rows.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={columns.length}>
                <Text ta="center" c="dimmed" py="md">
                  No topics found for this taxonomy.
                </Text>
              </Table.Td>
            </Table.Tr>
          ) : (
            table.getRowModel().rows.map((row) => {
              const topic = row.original
              const isSelected = topic.topic.id === selectedTopicId
              return (
                <Table.Tr
                  key={row.id}
                  bg={isSelected ? 'blue.0' : undefined}
                  onClick={() => onSelect(topic)}
                  style={{ cursor: 'pointer' }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <Table.Td key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </Table.Td>
                  ))}
                </Table.Tr>
              )
            })
          )}
        </Table.Tbody>
      </Table>
    </ScrollArea>
  )
}

function SortableHeader({
  label,
  isActive,
  direction,
  onClick,
}: {
  label: string
  isActive: boolean
  direction: 'asc' | 'desc'
  onClick: () => void
}) {
  const Icon = direction === 'asc' ? IconChevronUp : IconChevronDown
  return (
    <UnstyledButton onClick={onClick}>
      <Group gap={4}>
        <Text fw={600}>{label}</Text>
        {isActive && <Icon size={16} />}
      </Group>
    </UnstyledButton>
  )
}

function formatDate(iso: string | null | undefined) {
  if (!iso) return '—'
  try {
    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}
