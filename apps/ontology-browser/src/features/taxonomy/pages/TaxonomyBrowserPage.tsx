import {
  Container,
  Group,
  Stack,
  Title,
  Text,
  Grid,
  Paper,
  Alert,
  Divider,
} from '@mantine/core'
import { IconAlertCircle } from '@tabler/icons-react'
import { useMemo, useState, type JSX } from 'react'
import { TaxonomySelect } from '../components/TaxonomySelect'
import { TableToolbar } from '../components/TableToolbar'
import { TopicsTable } from '../components/TopicsTable'
import type { TopicSortKey } from '../components/TopicsTable'
import { TopicDetailPanel } from '../components/TopicDetailPanel'
import { useTaxonomyTopics } from '../hooks/useTaxonomyTopics'
import type { TopicStatus } from '../utils/statusBadge'

const DEFAULT_PAGE_SIZE = 10

export function TaxonomyBrowserPage(): JSX.Element {
  const [selectedTaxonomy, setSelectedTaxonomy] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<TopicStatus | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [sortBy, setSortBy] = useState<TopicSortKey>('title')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null)

  const queryParams = useMemo(
    () => ({
      limit: pageSize,
      offset: (page - 1) * pageSize,
      status: status ?? undefined,
      search: search ? search : undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
    }),
    [page, pageSize, search, sortBy, sortOrder, status],
  )

  const {
    data: topics,
    isLoading,
    isFetching,
  } = useTaxonomyTopics({
    taxonomyId: selectedTaxonomy ?? undefined,
    params: queryParams,
    enabled: Boolean(selectedTaxonomy),
  })

  const topicItems = topics?.items ?? []
  const total = topics?.total ?? 0
  const selectedTopic = topicItems.find(
    (item) => item.topic.id === selectedTopicId,
  )

  const handleSortChange = (column: TopicSortKey) => {
    if (sortBy === column) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(column)
      setSortOrder('asc')
    }
    setPage(1)
  }

  const resetStateForNewTaxonomy = (taxonomyId: string | null) => {
    setSelectedTaxonomy(taxonomyId)
    setSearch('')
    setStatus(null)
    setPage(1)
    setSortBy('title')
    setSortOrder('asc')
    setSelectedTopicId(null)
  }

  return (
    <Container size="xl" py="lg">
      <Stack gap="lg">
        <Group justify="space-between" align="flex-end">
          <div>
            <Title order={1} fz={{ base: '1.5rem', md: '2rem' }}>
              Taxonomy Browser
            </Title>
            <Text c="dimmed" size="sm">
              Choose a taxonomy to view its topics, status, and relationships.
            </Text>
          </div>
        </Group>

        <Paper shadow="sm" radius="md" p="lg">
          <Stack gap="md">
            <div>
              <Text fw={600}>Taxonomy</Text>
              <Divider my="sm" />
              <TaxonomySelect
                value={selectedTaxonomy}
                onChange={(value) => resetStateForNewTaxonomy(value)}
                w={{ base: '100%', md: 360 }}
              />
            </div>

            {selectedTaxonomy ? (
              <Stack gap="lg">
                <TableToolbar
                  search={search}
                  onSearchChange={setSearch}
                  status={status}
                  onStatusChange={setStatus}
                  total={total}
                  page={page}
                  pageSize={pageSize}
                  onPageChange={setPage}
                  onPageSizeChange={setPageSize}
                  disabled={isLoading && !topics}
                />
                <Grid gutter="lg">
                  <Grid.Col span={{ base: 12, md: 8 }}>
                    <TopicsTable
                      data={topicItems}
                      isLoading={isLoading || isFetching}
                      sortBy={sortBy}
                      sortOrder={sortOrder}
                      onSortChange={handleSortChange}
                      selectedTopicId={selectedTopicId}
                      onSelect={(topic) => setSelectedTopicId(topic.topic.id)}
                    />
                  </Grid.Col>
                  <Grid.Col span={{ base: 12, md: 4 }}>
                    <TopicDetailPanel topic={selectedTopic} />
                  </Grid.Col>
                </Grid>
              </Stack>
            ) : (
              <Alert
                icon={<IconAlertCircle size={16} />}
                color="blue"
                variant="light"
              >
                Please select a taxonomy to load topics.
              </Alert>
            )}
          </Stack>
        </Paper>
      </Stack>
    </Container>
  )
}
