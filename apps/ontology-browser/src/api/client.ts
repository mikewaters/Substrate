const API_BASE_URL =
  import.meta.env.VITE_ONTOLOGY_API_BASE_URL?.replace(/\/$/, '') || '/api'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

type RequestOptions = Omit<RequestInit, 'method'> & {
  params?: Record<string, unknown>
}

export async function request<TResponse>(
  path: string,
  {
    method = 'GET',
    params,
    headers,
    ...init
  }: RequestOptions & { method?: HttpMethod } = {},
): Promise<TResponse> {
  const url = buildUrl(`${API_BASE_URL}${path}`, params)

  const response = await fetch(url, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    ...init,
  })

  if (!response.ok) {
    const message = await safeParseError(response)
    throw new Error(message)
  }

  if (response.status === 204) {
    return undefined as TResponse
  }

  return (await response.json()) as TResponse
}

function buildUrl(
  base: string,
  params?: Record<string, unknown>,
): URL | string {
  if (!params || Object.keys(params).length === 0) {
    return base
  }

  const url = new URL(base, window.location.origin)
  Object.entries(params).forEach(([key, value]) => {
    if (
      value === undefined ||
      value === null ||
      (typeof value === 'string' && value.length === 0)
    ) {
      return
    }
    url.searchParams.append(key, String(value))
  })
  return url.toString()
}

type ErrorDetail = { msg?: string; type?: string } | string

async function safeParseError(response: Response): Promise<string> {
  try {
    const payload = (await response.clone().json()) as {
      detail?: unknown
    }
    const { detail } = payload

    if (typeof detail === 'string') {
      return detail
    }

    if (Array.isArray(detail)) {
      return (detail as ErrorDetail[])
        .map((entry) => {
          if (typeof entry === 'string') {
            return entry
          }
          return entry.msg ?? entry.type ?? 'Unknown error'
        })
        .join(', ')
    }

    return JSON.stringify(payload)
  } catch {
    return `${response.status} ${response.statusText}`
  }
}
