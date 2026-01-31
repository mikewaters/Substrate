import {
  Group,
  TextInput,
  Select,
  Pagination,
  Flex,
  Text,
} from '@mantine/core'
import { useMemo, type ChangeEvent, type JSX } from 'react'
import type { TopicStatus } from '../utils/statusBadge'

type TableToolbarProps = {
  search: string
  onSearchChange: (value: string) => void
  status: TopicStatus | null
  onStatusChange: (value: TopicStatus | null) => void
  total: number
  page: number
  pageSize: number
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
  disabled?: boolean
}

const STATUS_LABELS: Record<TopicStatus, string> = {
  active: 'Success',
  draft: 'Processing',
  deprecated: 'Failed',
  merged: 'Merged',
}

const STATUS_OPTIONS = Object.entries(STATUS_LABELS).map(([value, label]) => ({
  value,
  label,
}))

const PAGE_SIZES = ['10', '20', '50']

export function TableToolbar({
  search,
  onSearchChange,
  status,
  onStatusChange,
  total,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  disabled = false,
}: TableToolbarProps): JSX.Element {
  const pageCount = useMemo(
    () => Math.max(1, Math.ceil(total / pageSize)),
    [total, pageSize],
  )

  const handlePageSize = (value: string | null) => {
    if (!value) return
    const numeric = Number(value)
    if (!Number.isNaN(numeric)) {
      onPageSizeChange(numeric)
      onPageChange(1)
    }
  }

  const handleSearch = (event: ChangeEvent<HTMLInputElement>) => {
    onSearchChange(event.target.value)
    onPageChange(1)
  }

  return (
    <Flex
      direction={{ base: 'column', md: 'row' }}
      gap="sm"
      justify="space-between"
      align="center"
    >
      <Group gap="sm" align="center">
        <TextInput
          placeholder="Search topics"
          value={search}
          onChange={handleSearch}
          disabled={disabled}
          miw={220}
        />
        <Select
          data-testid="status-filter"
          placeholder="Filter by status"
          data={STATUS_OPTIONS}
          clearable
          value={status}
          onChange={(value) => {
            onStatusChange((value ?? null) as TopicStatus | null)
            onPageChange(1)
          }}
          disabled={disabled}
        />
      </Group>
      <Group gap="sm" align="center">
        <Text size="sm" c="dimmed">
          Page size
        </Text>
        <Select
          data={PAGE_SIZES}
          value={String(pageSize)}
          onChange={handlePageSize}
          disabled={disabled}
          w={80}
        />
        <Pagination
          total={pageCount}
          value={page}
          onChange={onPageChange}
          disabled={disabled}
          withEdges
        />
      </Group>
    </Flex>
  )
}
