export const taxonomyKeys = {
  all: ['taxonomies'] as const,
  list: (params?: Record<string, unknown>) =>
    ['taxonomies', 'list', params] as const,
}

export const topicKeys = {
  all: ['topics'] as const,
  list: (taxonomyId: string, params?: Record<string, unknown>) =>
    ['topics', 'list', taxonomyId, params] as const,
}

