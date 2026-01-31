/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ONTOLOGY_API_BASE_URL?: string
  readonly VITE_ENABLE_API_MOCKS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
