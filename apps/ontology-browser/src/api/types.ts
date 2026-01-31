import type { paths, components } from './types.gen'

export type TaxonomyListResponse =
  components['schemas']['TaxonomyListResponse']
export type TaxonomyResponse = components['schemas']['TaxonomyResponse']

export type TopicOverviewListResponse =
  components['schemas']['TopicOverviewListResponse']
export type TopicOverview = components['schemas']['TopicOverview']
export type TopicRelationshipRef =
  components['schemas']['TopicRelationshipRef']

export type ListTaxonomiesQuery =
  paths['/taxonomies']['get']['parameters']['query']

type TaxonomyTopicPath = '/taxonomies/{taxonomy_id}/topics'

export type ListTaxonomyTopicsQuery =
  paths[TaxonomyTopicPath]['get']['parameters']['query']
export type ListTaxonomyTopicsPathParams =
  paths[TaxonomyTopicPath]['get']['parameters']['path']

type TopicOverviewPath = '/topics/{topic_id}'
export type GetTopicOverviewPathParams =
  paths[TopicOverviewPath]['get']['parameters']['path']
