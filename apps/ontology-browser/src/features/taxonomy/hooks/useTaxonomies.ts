import { useQuery } from '@tanstack/react-query'
import { fetchTaxonomies } from '../../../api/taxonomies'
import { taxonomyKeys } from '../state/queryKeys'
import type { ListTaxonomiesQuery, TaxonomyListResponse } from '../../../api/types'

export function useTaxonomies(params?: ListTaxonomiesQuery) {
  return useQuery<TaxonomyListResponse>({
    queryKey: taxonomyKeys.list(params ?? {}),
    queryFn: () => fetchTaxonomies(params),
  })
}

