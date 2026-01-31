import { Paper, Stack, Title, Text, List, Divider, Badge } from '@mantine/core'
import type { JSX } from 'react'
import type { TopicOverview } from '../../../api/types'
import { StatusBadge } from '../utils/statusBadge'
import type { TopicStatus } from '../utils/statusBadge'

type TopicDetailPanelProps = {
  topic?: TopicOverview
}

export function TopicDetailPanel({
  topic,
}: TopicDetailPanelProps): JSX.Element {
  if (!topic) {
    return (
      <Paper
        shadow="sm"
        radius="md"
        p="lg"
        h="100%"
        data-testid="topic-detail-panel"
      >
        <Stack gap="xs">
          <Title order={3}>Topic details</Title>
          <Text c="dimmed" size="sm">
            Select a topic to view its description, parents, and children.
          </Text>
        </Stack>
      </Paper>
    )
  }

  return (
    <Paper
      shadow="sm"
      radius="md"
      p="lg"
      h="100%"
      data-testid="topic-detail-panel"
    >
      <Stack gap="md">
        <div>
          <Title order={3}>{topic.topic.title}</Title>
          <StatusBadge status={topic.topic.status as TopicStatus} />
          <Text size="sm" mt="sm">
            {topic.topic.description ?? 'No description provided.'}
          </Text>
        </div>
        <div>
          <Text fw={600}>Topic children:</Text>
          <List spacing="xs" withPadding c="dimmed" size="sm">
            {topic.children?.length ? (
              topic.children.map((child) => (
                <List.Item key={child.id}>
                  <Stack gap={4} miw={0}>
                    <Text fw={500}>{child.title}</Text>
                    <Text size="xs" c="dimmed">
                      {child.identifier}
                    </Text>
                  </Stack>
                </List.Item>
              ))
            ) : (
              <List.Item>No children</List.Item>
            )}
          </List>
        </div>
        <Divider />
        <div>
          <Text fw={600}>Topic parents:</Text>
          <List spacing="xs" withPadding c="dimmed" size="sm">
            {topic.parents?.length ? (
              topic.parents.map((parent) => (
                <List.Item key={parent.id}>
                  <Stack gap={4} miw={0}>
                    <Text fw={500}>{parent.title}</Text>
                    <Badge size="xs" variant="light">
                      {parent.identifier}
                    </Badge>
                  </Stack>
                </List.Item>
              ))
            ) : (
              <List.Item>(none)</List.Item>
            )}
          </List>
        </div>
      </Stack>
    </Paper>
  )
}
