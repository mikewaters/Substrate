import { Select } from '@mantine/core'
import { useMemo, type JSX } from 'react'
import type { SelectProps } from '@mantine/core'
import { useTaxonomies } from '../hooks/useTaxonomies'

type TaxonomySelectProps = Omit<SelectProps, 'data' | 'onChange'> & {
  value: string | null
  onChange: (value: string | null) => void
}

export function TaxonomySelect({
  value,
  onChange,
  ...rest
}: TaxonomySelectProps): JSX.Element {
  const { data, isLoading, isError, error } = useTaxonomies()

  const options = useMemo(
    () =>
      data?.items.map((taxonomy) => ({
        value: taxonomy.id,
        label: taxonomy.title,
      })) ?? [],
    [data],
  )

  return (
    <Select
      data-testid="taxonomy-select"
      data={options}
      value={value}
      onChange={onChange}
      disabled={isLoading || isError}
      placeholder={
        isLoading
          ? 'Loading taxonomies...'
          : isError
            ? 'Failed to load taxonomies'
            : 'Select a taxonomy'
      }
      error={isError ? error?.message ?? 'Unable to load taxonomies' : undefined}
      searchable
      nothingFoundMessage="No taxonomies"
      {...rest}
    />
  )
}
