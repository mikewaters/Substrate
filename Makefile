### Makefile for Substrate project
#
# - Should contain commands for automating regular project maintenance
# - This should be the primary agent interface for the project
# - Individual modules may have their own utilities
# - Other utility commands can be found in `Justfile`, or by running `just`

.PHONY: install

install:
	@if [ ! -f .env.local ]; then \
		echo "SUBSTRATE_ENVIRONMENT=dev" > .env.local; \
		echo "Created .env.local from .env.example"; \
	else \
		echo ".env.local already exists"; \
	fi
