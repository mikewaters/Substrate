import { http, HttpResponse } from 'msw'
import { formatISO } from 'date-fns'

const API_BASE_URL = import.meta.env.VITE_ONTOLOGY_API_BASE_URL ?? '/api'

const now = new Date()
const timestamp = (daysAgo: number) =>
  formatISO(new Date(now.getTime() - daysAgo * 24 * 60 * 60 * 1000))

const taxonomies = [
  {
    id: '00000000-0000-0000-0889-42373c0947bc',
    identifier: 'tx:taxonomy-one',
    title: 'Taxonomy One',
    description: 'Primary taxonomy for demonstration data.',
    skos_uri: null,
    created_at: timestamp(120),
    updated_at: timestamp(5),
  },
  {
    id: '00000000-0000-0000-6a71-44b413811639',
    identifier: 'tx:taxonomy-two',
    title: 'Taxonomy Two',
    description: 'Secondary taxonomy for exploration.',
    skos_uri: null,
    created_at: timestamp(200),
    updated_at: timestamp(14),
  },
]

type TopicOverviewFixture = {
  id: string
  taxonomy_id: string
  identifier: string
  title: string
  status: 'draft' | 'active' | 'deprecated' | 'merged'
  description?: string | null
  parents?: Array<{ id: string; identifier: string; title: string; status: string }>
  children?: Array<{ id: string; identifier: string; title: string; status: string }>
  created_at_offset_days: number
  updated_at_offset_days: number
}

const taxonomyTopicFixtures: Record<string, TopicOverviewFixture[]> = {
  '00000000-0000-0000-0889-42373c0947bc': [
    {
      id: '10000000-0000-0000-0000-000000000001',
      taxonomy_id: '00000000-0000-0000-0889-42373c0947bc',
      identifier: 'tx:topic-1',
      title: 'Topic number one',
      status: 'active',
      description: 'Description text from topic one',
      children: [
        {
          id: '00000000-0000-0000-1234-111111111111',
          identifier: 'tx:topic-19',
          title: 'topic 19',
          status: 'draft',
        },
        {
          id: '00000000-0000-0000-1234-222222222222',
          identifier: 'tx:topic-20',
          title: 'topic gfgfgfgfgf',
          status: 'active',
        },
      ],
      parents: [],
      created_at_offset_days: 40,
      updated_at_offset_days: 10,
    },
    {
      id: '10000000-0000-0000-0000-000000000002',
      taxonomy_id: '00000000-0000-0000-0889-42373c0947bc',
      identifier: 'tx:topic-2',
      title: 'Topic number two',
      status: 'active',
      description: 'Description text from topic two',
      children: [],
      parents: [
        {
          id: '00000000-0000-0000-9999-777777777777',
          identifier: 'tx:topic-17',
          title: 'Topic 17',
          status: 'active',
        },
      ],
      created_at_offset_days: 38,
      updated_at_offset_days: 12,
    },
    {
      id: '10000000-0000-0000-0000-000000000003',
      taxonomy_id: '00000000-0000-0000-0889-42373c0947bc',
      identifier: 'tx:topic-3',
      title: 'Topic number three',
      status: 'draft',
      children: [],
      parents: [],
      description: 'This topic is processing new data',
      created_at_offset_days: 30,
      updated_at_offset_days: 3,
    },
    {
      id: '10000000-0000-0000-0000-000000000004',
      taxonomy_id: '00000000-0000-0000-0889-42373c0947bc',
      identifier: 'tx:topic-4',
      title: 'Topic number four',
      status: 'deprecated',
      children: [],
      parents: [],
      description: 'Deprecated topic example',
      created_at_offset_days: 60,
      updated_at_offset_days: 45,
    },
    {
      id: '10000000-0000-0000-0000-000000000005',
      taxonomy_id: '00000000-0000-0000-0889-42373c0947bc',
      identifier: 'tx:topic-5',
      title: 'Topic number five',
      status: 'active',
      children: [],
      parents: [],
      created_at_offset_days: 22,
      updated_at_offset_days: 5,
    },
    {
      id: '10000000-0000-0000-0000-000000000006',
      taxonomy_id: '00000000-0000-0000-0889-42373c0947bc',
      identifier: 'tx:topic-6',
      title: 'Topic 10',
      status: 'draft',
      description: 'Description text for topic 10',
      children: [],
      parents: [],
      created_at_offset_days: 15,
      updated_at_offset_days: 1,
    },
  ],
}

function buildTopicOverview(fixture: TopicOverviewFixture) {
  const id = fixture.id
  return {
    topic: {
      id,
      taxonomy_id: fixture.taxonomy_id,
      taxonomy_identifier: taxonomies.find(
        (tax) => tax.id === fixture.taxonomy_id,
      )?.identifier,
      identifier: fixture.identifier,
      title: fixture.title,
      slug: fixture.identifier.replace(':', '-'),
      description: fixture.description ?? null,
      status: fixture.status ?? 'active',
      path: `/${fixture.identifier}`,
      aliases: [],
      external_refs: {},
      created_at: timestamp(fixture.created_at_offset_days),
      updated_at: timestamp(fixture.updated_at_offset_days),
    },
    child_count: fixture.children?.length ?? 0,
    children: fixture.children ?? [],
    parents: fixture.parents ?? [],
  }
}

const topicCache = new Map<string, ReturnType<typeof buildTopicOverview>[]>()

export const handlers = [
  http.get(`${API_BASE_URL}/taxonomies`, () =>
    HttpResponse.json({
      items: taxonomies,
      total: taxonomies.length,
      limit: 50,
      offset: 0,
    }),
  ),
  http.get(
    `${API_BASE_URL}/taxonomies/:taxonomyId/topics`,
    ({ params, request }) => {
      const taxonomyId = params.taxonomyId as string
      if (!topicCache.has(taxonomyId)) {
        const fixtures = taxonomyTopicFixtures[taxonomyId] ?? []
        topicCache.set(
          taxonomyId,
          fixtures.map((fixture) => buildTopicOverview(fixture)),
        )
      }

      let items = [...(topicCache.get(taxonomyId) ?? [])]
      const url = new URL(request.url)
      const offset = Number(url.searchParams.get('offset') ?? 0)
      const limit = Number(url.searchParams.get('limit') ?? 50)
      const status = url.searchParams.get('status')
      const search = url.searchParams.get('search')?.toLowerCase()
      const sortBy = url.searchParams.get('sort_by') ?? 'title'
      const sortOrder = url.searchParams.get('sort_order') ?? 'asc'

      if (status) {
        items = items.filter(
          (record) => record.topic.status.toLowerCase() === status.toLowerCase(),
        )
      }

      if (search) {
        items = items.filter(
          (record) =>
            record.topic.title.toLowerCase().includes(search) ||
            record.topic.description?.toLowerCase().includes(search),
        )
      }

      items.sort((a, b) => {
        const orderFactor = sortOrder === 'desc' ? -1 : 1
        switch (sortBy) {
          case 'status':
            return (
              a.topic.status.localeCompare(b.topic.status) * orderFactor
            )
          case 'created_at':
            return (
              (a.topic.created_at > b.topic.created_at ? 1 : -1) * orderFactor
            )
          case 'updated_at':
            return (
              (a.topic.updated_at > b.topic.updated_at ? 1 : -1) * orderFactor
            )
          case 'child_count':
            return (a.child_count - b.child_count) * orderFactor
          case 'title':
          default:
            return a.topic.title.localeCompare(b.topic.title) * orderFactor
        }
      })

      const total = items.length
      const paginated = items.slice(offset, offset + limit)

      return HttpResponse.json({
        items: paginated,
        total,
        limit,
        offset,
      })
    },
  ),
  http.get(
    `${API_BASE_URL}/topics/:topicId`,
    ({ params }) => {
      const topicId = params.topicId as string
      const all = Array.from(topicCache.values()).flat()
      const record = all.find((item) => item.topic.id === topicId)
      if (!record) {
        return HttpResponse.json(
          { detail: `Topic ${topicId} not found` },
          {
            status: 404,
          },
        )
      }
      return HttpResponse.json(record)
    },
  ),
]
