### Makefile for Substrate project
#
# - Should contain commands for automating regular project maintenance
# - This should be the primary agent interface for the project
# - Individual modules may have their own utilities
# - Other utility commands can be found in `Justfile`, or by running `just`

.PHONY: install purge purge-all

install:
	@if [ ! -f .env.local ]; then \
		echo "SUBSTRATE_ENVIRONMENT=dev" > .env.local; \
		echo "Created .env.local from .env.example"; \
	else \
		echo ".env.local already exists"; \
	fi

# Resolve config root for current env (from .env.local) and delete that directory.
purge:
	@root=$$(uv run python -c "from catalog.core.settings import get_settings; print(get_settings().config_root)"); \
	rm -rf "$$root"; \
	echo "Purged $$root"

# Delete config root directories for all environments except prod (dev and test).
# Uses Python to resolve paths from catalog.core.settings.DEFAULT_CONFIG_ROOTS.
purge-all:
	@uv run python -c "\
import os; \
from catalog.core.settings import _resolve_config_root_from_env; \
for env in ('dev', 'test'): \
	os.environ['SUBSTRATE_ENVIRONMENT'] = env; \
	[os.environ.pop(k, None) for k in list(os.environ) if k.startswith('SUBSTRATE_CONFIG_ROOT')]; \
	print(_resolve_config_root_from_env())" | while read -r r; do rm -rf "$$r"; echo "Purged $$r"; done
