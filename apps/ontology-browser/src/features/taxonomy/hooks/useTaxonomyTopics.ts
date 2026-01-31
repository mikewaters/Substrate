import { useQuery } from '@tanstack/react-query'
import { fetchTaxonomyTopics } from '../../../api/taxonomies'
import { topicKeys } from '../state/queryKeys'
import type {
  ListTaxonomyTopicsQuery,
  ListTaxonomyTopicsPathParams,
  TopicOverviewListResponse,
} from '../../../api/types'

type UseTaxonomyTopicsArgs = {
  taxonomyId?: string
  params?: ListTaxonomyTopicsQuery
  enabled?: boolean
}

export function useTaxonomyTopics({
  taxonomyId,
  params,
  enabled = true,
}: UseTaxonomyTopicsArgs) {
  return useQuery<TopicOverviewListResponse>({
    queryKey: topicKeys.list(taxonomyId ?? 'unknown', params ?? {}),
    enabled: Boolean(taxonomyId) && enabled,
    queryFn: () =>
      fetchTaxonomyTopics(
        { taxonomy_id: taxonomyId } as ListTaxonomyTopicsPathParams,
        params,
      ),
  })
}

