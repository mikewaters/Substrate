# Substrate
The data layer for the Life Business.

**THIS FILE IS MEANT FOR HUMANS; agent *must* use AGENTS.md and should ignore this file.**

## Notes
### Claude Code
- Claude will pickup `.mcp.json` and you can add them to the project config (which will use `.claude/settings.local.json`).

### Secrets management
I am storing secrets in macos keychain and grabbing it using `direnv`.

Creating a new secret:
```bash
# Adds/updates a generic password named by -s (service) and -a (account)
security add-generic-password -U \
  -s "substrate/<secret name>" \
  -a "$USER" \
  -w "<THE SECRET>" \
  ~/Library/Keychains/login.keychain-db
```

See `.envrc` for details.


### Browser-use MCP
Needs a hacked command line `uvx --from "browser-use[cli]==0.7.5" browser-use --mcp` due to [GitHub - Bug: mcp can not run, because CLI addon is not installed. · Issue #3023 (browser-use/browser-use)](https://github.com/browser-use/browser-use/issues/3023)

## Components
Each component should have its own README as well as component-specific agent instructions.

### Python Modules
- `src/ontology` - lifeos ontology classification and entity store
- `src/catalog` - data catalog for ingestion, storage, and search
- `src/agentbase` - reusable agent components
- `src/notes` - conversion of notes to indexable content

### Frontend Applications
- `apps/ontology-browser` – React + Vite app scaffolded for FEAT-015. Use Node.js 24.x LTS (`.nvmrc`) and pnpm to install dependencies (`cd apps/ontology-browser && pnpm install`). Development commands: `pnpm dev` for the local server, `pnpm lint`, `pnpm test`, `pnpm typecheck`, and `pnpm build`.

## Development tools
- project uses `direnv` to set environment variables for the workspace; new checkouts may require running `direnv allow`

## SDLC
- using github issues for feature backlog; `docs/features/` directory is used solely for the agent to drop non-persistent docs; it is gitignored
