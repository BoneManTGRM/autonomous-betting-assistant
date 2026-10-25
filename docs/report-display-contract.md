# Report snapshot display contract

## Scope
Report generation is a read-only presentation of supplied observations. It does not improve or recalibrate the prediction model and does not prove a stated model probability is realized accuracy. No history, outcome, stake, ledger, credential, or provider account is changed.

Report Studio cards use the existing accounting/learning adapter. The display patch does not own those adapters or `report_verification_gate.py`. `report_accounting_quarantined` remains monotonic through child markets and is explicitly enforced even before an updated gate is integrated.

## Boundaries and fields
- `prepare_report_snapshot_row(s)` is the report-only, no-provider-dispatch boundary. Both Report Studio cards export and selected-PNG cache use it, as does the renderer installer. Configured keys do not authorize a refresh. Legacy live-enrichment helpers remain separate; optional explicit refresh behavior is tested separately and is not called by report generation.
- Original `source_trace_json`, `field_provenance_json`, `model_probability_source`, supplied context and its locale are retained. Report-derived traces use separate `report_generation_trace_json` and `report_field_provenance_json` fields. `report_generated_at` is not an observation or refresh time.
- Observation priority is `source_observed_at`, provider/price/odds/captured timestamp, then generic timestamp. A stored live flag is not fresh provider evidence. Saved/stale rows cannot become actionable on render.
- `selected_market`, market aliases, explicit selections and numeric bookmaker line aliases are checked for contradiction before resolution. `total` is a bookmaker-line alias; `model_total` and `projected_total` are not. Equivalent EN/ES market/side values, supported O/U shorthand and Unicode-minus inputs are normalized before comparison; distinct provider ID namespaces are not compared. Same-provider current/verified IDs and the named provider's own ID alias must agree. Contradictions set `report_market_issue` and `report_field_conflicts` on an in-memory copy and stay non-actionable across wrappers.
- A child market owns its own market/selection/line aliases, not the anchor's. Distinct event identities remain distinct even when market labels are identical. Explicit team-total/player-prop families survive repeated normalization. Accounting quarantine cannot be cleared by a child false value.
- `display_decision` combines the existing source gate with explicit market consistency, exact selection/line and accounting guards. First-page final recommendation, metrics and evidence agree with these guards; page-two eligibility independently retains all original quote, SGP, freshness and cancellation checks.
- Stored model probability/EV remain stored values, not confidence/accuracy claims. Stake has units (`u`); an unverified report shows no actionable stake rather than replacing the saved target with zero.

## Language and evidence
Generated messages are complete EN/ES messages, not fragments translated inside arbitrary prose. Supplied narrative requires a `${field}_en`/`${field}_es` value or an explicit matching `${field}_language`, `${field}_locale`, `content_language`, or `source_content_language`. Unknown/mismatched language produces a localized missing-content reason, never guessed translation.

Team and injury sections accept only their own side-specific fields. General matchup/Perplexity prose is not recycled as injury or team evidence. Indoor basketball/explicit indoor venues show a non-applicability weather explanation. Outdoor weather requires event/source content supplied in the requested locale.

## Layout and exports
Normal short reports retain the two-page base. Pixel-measured text that cannot fit at readable size is explicitly redirected to complete source-note continuation pages. Rationale, both teams, both injury panels, weather/matchup, page-two diagnostics and final detail all retain full overflow text. Page numbering, source-note references, PDF/PNG cache counts and ZIP page ownership include continuations. Rejected child markets retain event/player identity and all missing-field diagnostics; scan and rejection/line counts remain visible. Headline fit measures the complete name before accepting its line budget. Preview cache uses JSON serialization, never Python repr evaluation, so nested markets, quotes, receipts and boolean flags survive.

## Acceptance evidence
`tests/test_report_display_contract.py` and standalone `tests/report_display_render_probe.py` cover canonical conflicts and valid controls, immutable provenance, configured-key no-call behavior across seven sports, quarantine inheritance, actual Report Studio cards→branding→JSON cache→selected PNG and full PDF, runtime bridges ON/OFF, EN/ES, stale/missing/conflicting/zero-leg cases and short/long text end markers. Report Studio source-order assertions now name the explicit snapshot boundary and prohibit live-enrichment calls; provider-refresh compatibility tests now opt in explicitly; existing mathematical, SGP, quote and branding assertions remain intact. The old July timestamp fixture's direct-anchor expectation is intentionally replaced by stale/no-verified assertions.

All rendered fixture teams, venues, receipts and keys are synthetic; no real provider request is permitted by the probe. Final image/PDF visual review is independent of text-draw assertions.

## Runtime compatibility (integration follow-up)

- Pure snapshots always expose `live_api_enrichment_status` as `PROVIDED_DATA_ONLY` or `DEMONSTRATION_ONLY`, without inspecting API keys. The legacy facade retains missing-key/refresh-disabled diagnostic fields without dispatching providers or overwriting existing observations.
- Snapshot-capable enrichment owns the explicit `allow_provider_refresh` contract. The incompatible older provider-usage interceptor is installed only for older modules; supported explicit non-report refresh still uses its original request adapter and provider helpers.
- BALLDONTLIE and cleanup wrappers honor `report_provider_calls_allowed=False`; they cannot add provider calls or generic matchup evidence to snapshots. Demonstration rows never dispatch BALLDONTLIE.
- Bootstrap does not replace the sale gate helper with the renderer normalizer. This preserves caller/export compatibility fields (including demo-only zero stakes) while final rendering independently applies the canonical, freshness and quarantine guards. Saved real-row stakes are not zeroed.
