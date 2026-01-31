import { request } from './client'
import type {
  ListTaxonomiesQuery,
  ListTaxonomyTopicsPathParams,
  ListTaxonomyTopicsQuery,
  TaxonomyListResponse,
  TopicOverviewListResponse,
} from './types'

export async function fetchTaxonomies(
  query?: ListTaxonomiesQuery,
): Promise<TaxonomyListResponse> {
  return request<TaxonomyListResponse>('/taxonomies', {
    params: query as Record<string, unknown>,
  })
}

export async function fetchTaxonomyTopics(
  { taxonomy_id }: ListTaxonomyTopicsPathParams,
  query?: ListTaxonomyTopicsQuery,
): Promise<TopicOverviewListResponse> {
  return request<TopicOverviewListResponse>(
    `/taxonomies/${taxonomy_id}/topics`,
    {
      params: query as Record<string, unknown>,
    },
  )
}
