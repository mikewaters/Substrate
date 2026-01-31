import { useState, type ReactNode, type JSX } from 'react'
import {
  MantineProvider,
  ColorSchemeScript,
  type MantineProviderProps,
} from '@mantine/core'
import {
  QueryClient,
  QueryClientProvider,
  type QueryClientConfig,
} from '@tanstack/react-query'
import { mantineTheme } from '../theme'

const queryClientConfig: QueryClientConfig = {
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
}

type AppProvidersProps = {
  children: ReactNode
  MantineProps?: Partial<MantineProviderProps>
}

export function AppProviders({
  children,
  MantineProps,
}: AppProvidersProps): JSX.Element {
  const [queryClient] = useState(() => new QueryClient(queryClientConfig))

  return (
    <MantineProvider theme={mantineTheme} defaultColorScheme="light" {...MantineProps}>
      <ColorSchemeScript defaultColorScheme="light" />
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </MantineProvider>
  )
}
