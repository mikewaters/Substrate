# Tool CLI Test Cases

## `tool/cli/user.py`

- `test_substrate_help_sections_follow_required_order`
  - Verifies `substrate --help` renders all required sections in contract order.
- `test_substrate_help_json_contains_required_contract_fields`
  - Verifies `substrate --help-json` returns JSON with required top-level keys.
- `test_substrate_help_shows_log_level_option`
  - Verifies `substrate --help` documents the global log-level option.
- `test_substrate_rejects_operational_arguments_in_v0`
  - Verifies v0 runtime commands are rejected with exit code `2`.
- `test_substrate_rejects_invalid_log_level`
  - Verifies invalid global log level fails with exit code `2`.
- `test_substrate_defaults_to_critical_logging`
  - Verifies `substrate` defaults to `CRITICAL` log level.

## `tool/cli/operator.py`

- `test_operator_help_exposes_eval_and_search_groups`
  - Verifies `substrate-admin --help` shows delegated command groups.
- `test_operator_eval_golden_help_is_delegated`
  - Verifies `substrate-admin eval golden --help` is available.
- `test_operator_help_includes_global_log_level_option`
  - Verifies `substrate-admin --help` includes the global log-level option.
- `test_operator_main_normalizes_missing_queries_file_to_exit_code_five`
  - Verifies delegated command failure is normalized to exit code `5`.
- `test_operator_default_log_level_is_info`
  - Verifies `substrate-admin` global log-level default is `INFO`.
