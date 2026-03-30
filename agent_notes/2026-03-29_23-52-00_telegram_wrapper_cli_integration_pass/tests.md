# Tests

## Test file
`src/tests/test_telegram_sidecar.py`

## Test count
38 tests (expanded from 7 original)

## Test run command
```bash
python3 -m pytest src/tests/test_telegram_sidecar.py -v --tb=short
```

## Full suite regression check
```bash
python3 -m pytest src/tests/ -v --tb=short
```
Result: 779 passed, 0 failures.

## Test categories

### Action mapping (4 tests)
- `test_action_mapping_long_short_exit_and_non_actionable` — LONG_ENTRY→BUY, SHORT_ENTRY→SELL, EXIT→EXIT, NO_TRADE→None
- `test_action_map_covers_all_contract_actions` — ACTION_MAP dict exact match
- `test_actionable_actions_matches_map_values` — ACTIONABLE_ACTIONS set exact match
- `test_actionable_filter_uses_final_contract_not_raw_signal` — Contract EXIT overrides signal WAIT

### Actionable-only filter (6 tests)
- `test_signal_action_buy_fallback_when_contract_absent` — BUY fallback from signal.action
- `test_signal_action_sell_fallback_when_contract_absent` — SELL fallback from signal.action
- `test_wait_signal_with_no_trade_contract_returns_none` — WAIT + NO_TRADE → None
- `test_non_actionable_empty_string_contract` — Empty contract → None
- `test_non_actionable_unknown_contract_action` — Unknown action → None
- `test_missing_status_panel_returns_none_when_signal_wait` — Missing status_panel → None
- `test_missing_entry_exit_decision_returns_none_when_signal_wait` — Missing entry_exit_decision → None

### Dedupe (5 tests)
- `test_dedupe_key_uses_symbol_action_signal_id` — Key format validation
- `test_dedupe_store_load_and_save_roundtrip` — Persist/load roundtrip
- `test_dedupe_skips_repeat_alert` — Second identical alert skipped
- `test_dedupe_allows_different_actions_same_signal_id` — BUY and SELL on same signal_id both sent
- `test_dedupe_corrupted_state_file_recovers` — Invalid JSON in state file → empty set
- `test_dedupe_state_missing_sent_keys_field` — Missing sent_keys field → empty set

### Fail-open (4 tests)
- `test_fail_open_when_send_raises` — RuntimeError → fail-open result
- `test_fail_open_on_connection_error` — ConnectionError → fail-open result
- `test_fail_open_on_timeout_error` — TimeoutError → fail-open result
- `test_fail_open_does_not_persist_dedupe_key` — Failed send does not persist key

### Credentials missing (2 tests)
- `test_missing_token_skips_gracefully` — Empty token → skipped
- `test_missing_chat_id_skips_gracefully` — Empty chat_id → skipped

### Payload shape and format (3 tests)
- `test_payload_to_dict_shape` — Dict keys and types
- `test_telegram_text_format` — Text includes all expected fields
- `test_telegram_text_exit_no_price` — EXIT alert omits price

### Helper functions (8 tests)
- `test_round_confidence_edge_cases` — Float, string, None, invalid
- `test_top_reasons_limits` — Limit, empty, non-list
- `test_extract_price_buy_sell_returns_float` — BUY/SELL returns entry_price
- `test_extract_price_exit_returns_none` — EXIT returns None
- `test_extract_price_missing_entry_price` — Missing key returns None
- `test_derive_signal_id_uses_snapshot_when_present` — Uses snapshot_id
- `test_derive_signal_id_fallback_hash_when_no_snapshot` — Generates telegram_ hash
- `test_derive_signal_id_deterministic` — Same inputs → same hash

### Integration (3 tests)
- `test_run_pipeline_with_telegram_returns_output_even_on_send_failure` — Pipeline output preserved
- `test_successful_send_persists_key` — Sent key in state file
- `test_delivery_result_contains_alert_on_success` — Alert dict in result
- `test_delivery_result_contains_alert_on_dedupe` — Alert dict in dedupe result
