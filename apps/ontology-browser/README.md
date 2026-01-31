# Ontology Browser Frontend

The `ontology-browser` app is a Vite-powered React application that provides the web UI foundation for FEAT-015/FEAT-016. It lives under `apps/ontology-browser/` in the monorepo and uses pnpm for dependency management.

## Prerequisites
- Node.js 24.x LTS (`nvm use` reads `.nvmrc`)
- pnpm ≥ 10 (`corepack enable pnpm` if pnpm is not on your PATH)

## Getting Started
```sh
pnpm install
pnpm dev
```

The dev server runs on http://localhost:5173 by default and hot-reloads as you edit files in `src/`.

## Available Scripts
- `pnpm dev` – start the Vite dev server.
- `pnpm build` – type-check (`tsc -b`) and build a production bundle into `dist/`.
- `pnpm preview` – serve the production bundle locally.
- `pnpm lint` – run ESLint with zero-warning enforcement.
- `pnpm typecheck` – run TypeScript in no-emit mode for editor parity.
- `pnpm test` – execute Vitest in CI mode with jsdom environment.
- `pnpm test:watch` – run Vitest in watch mode.
- `pnpm generate:api-types` – regenerate REST typings from `docs/features/FEAT-016/openapi-after-amendments.yaml`.

## Code Quality
- ESLint + `eslint-config-prettier` enforce code quality and formatting rules.
- Prettier (`.prettierrc.json`) governs formatting; run it via your editor integration.
- Vitest + Testing Library exercise UI components; see `src/App.test.tsx` for an example.

## Project Structure
- `src/` – application code (entry point `main.tsx`, root component `App.tsx`, styles, assets).
  - `api/` – generated types and thin fetch wrappers for the ontology API.
  - `features/taxonomy/` – FEAT-016 taxonomy browsing page (components, hooks, tests).
  - `mocks/` – Mock Service Worker setup and fixtures.
- `public/` – static assets served as-is (includes `mockServiceWorker.js`).
- `vitest.config.ts` & `src/setupTests.ts` – test runner configuration and global test utilities.

## Architecture Overview
- **App shell (`src/App.tsx`)** renders the `TaxonomyBrowserPage` inside global providers that supply Mantine theming and TanStack Query caching (`src/app/providers.tsx`).
- **Theming** is centralized in `src/theme/index.ts` and shared across Mantine components and future React Flow integrations.
- **Data layer** lives in `src/api/`, where `client.ts` wraps `fetch`, enforces JSON parsing, and applies query parameters. Generated types (`types.gen.ts`) and curated aliases (`types.ts`) ensure calls to `/taxonomies` and the read-model endpoints stay aligned with the OpenAPI spec.
- **State management** relies on TanStack Query. Hooks such as `useTaxonomies` and `useTaxonomyTopics` encapsulate request/response lifecycles and feed the presentation layer.
- **Presentation layer** is organized under `features/taxonomy/components/`. Each component is view-focused (select list, toolbar, data table, detail panel) and is composed on the page in `TaxonomyBrowserPage.tsx` alongside layout primitives.
- **Testing & mocking** use Vitest with Testing Library plus Mock Service Worker. The handlers in `src/mocks/handlers.ts` mirror API responses so integration tests exercise the same contract as production.

### Data Flow
1. Providers bootstrap Mantine, color scheme, and TanStack Query in `main.tsx` before rendering the app.
2. When a taxonomy is selected, `useTaxonomyTopics` issues a query to `/read-model/taxonomies/{taxonomy_id}/topics`, caching results per taxonomy, filters, and pagination.
3. Table interactions (pagination, sorting, filtering) mutate local state which recalculates query parameters and triggers cached or fresh fetches.
4. Selecting a row updates local UI state so the detail panel renders the corresponding `TopicOverview` without a second network call (data already present in the list response).
5. Error parsing and empty states surface through the hooks and UI components, ensuring consistent messaging.

## Integration Notes
- The app is managed via pnpm workspaces (`pnpm-workspace.yaml`); frontend commands should be run from this directory.
- Generated artifacts (`dist/`, `coverage/`, `node_modules/`) are ignored globally in `.gitignore`.
- Frontend CI integration is not yet wired into the repo’s automation; track follow-ups to add lint/test/build to CI.

## API Contract & Mocking
- The UI targets the enriched ontology endpoints described in `docs/features/FEAT-016/openapi-after-amendments.yaml`, notably:
  - `GET /taxonomies`
  - `GET /read-model/taxonomies/{taxonomy_id}/topics`
  - `GET /read-model/topics/{topic_id}`
- Regenerate local typings after spec changes with `pnpm generate:api-types`.
- Development and tests default to Mock Service Worker (MSW). Configure via `.env`:

  ```env
  VITE_ENABLE_API_MOCKS=true
  VITE_ONTOLOGY_API_BASE_URL=http://localhost:8000
  ```

  Set `VITE_ENABLE_API_MOCKS=false` when pointing at a running backend instance.

## Development Operations
1. **Install dependencies**: `pnpm install` inside `apps/ontology-browser/`.
2. **Generate typings** after OpenAPI updates: `pnpm generate:api-types`.
3. **Run dev server**: `pnpm dev` (MSW auto-starts when `VITE_ENABLE_API_MOCKS` is omitted or `true`).
4. **Quality gates**: `pnpm lint`, `pnpm typecheck`, `pnpm test`. These commands run in-memory against the MSW fixtures and must pass before committing.
5. **Adjust fixtures**: update `src/mocks/handlers.ts` or add JSON fixtures when new API fields are needed; keep data aligned with `openapi-after-amendments.yaml`.
6. **Troubleshooting**: If encountering browser API errors in tests (e.g., `matchMedia`), ensure polyfills remain in `src/setupTests.ts`.

## Production Operations
1. **Build**: `pnpm build` (executes `tsc -b` followed by `vite build`). Artifacts land in `dist/`.
2. **Environment configuration**:
   - `VITE_ONTOLOGY_API_BASE_URL` should point to the deployed ontology API (no trailing slash).
   - `VITE_ENABLE_API_MOCKS` must be set to `false` for production deployments.
3. **Static hosting**: serve the `dist/` directory with any static server (Vercel, Netlify, S3/CloudFront, etc.). Ensure the hosting platform forwards API requests to the configured backend (typically via reverse proxy or separate domain).
4. **Runtime monitoring**: instrumentation is client-side only; leverage browser dev tools or add logging hooks if deeper insight is required. The TanStack Query devtools can be included during troubleshooting but should be excluded from production bundles.
5. **Version alignment**: whenever the backend spec changes, regenerate client types, update UI assumptions, rerun the test suite, and rebuild.
