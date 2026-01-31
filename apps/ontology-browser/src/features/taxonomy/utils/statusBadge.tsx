import { Badge } from '@mantine/core'
import type { BadgeProps } from '@mantine/core'
import type { JSX } from 'react'

export type TopicStatus = 'draft' | 'active' | 'deprecated' | 'merged'

const STATUS_MAP: Record<
  TopicStatus,
  { label: string; color: BadgeProps['color'] }
> = {
  active: { label: 'Success', color: 'green' },
  draft: { label: 'Processing', color: 'yellow' },
  deprecated: { label: 'Failed', color: 'red' },
  merged: { label: 'Merged', color: 'grape' },
}

export function StatusBadge({ status }: { status: TopicStatus }): JSX.Element {
  const mapping = STATUS_MAP[status]
  if (!mapping) {
    return (
      <Badge color="gray" variant="light">
        {status}
      </Badge>
    )
  }

  return (
    <Badge color={mapping.color} variant="light" tt="capitalize">
      {mapping.label}
    </Badge>
  )
}
