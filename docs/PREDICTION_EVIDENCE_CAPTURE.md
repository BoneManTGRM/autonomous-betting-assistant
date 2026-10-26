# Current prediction evidence download

On Pro Predictor or Pro Predictor Volume, the paper-evidence panel can download
available fields from every row in `pro_predictor_all_rows` with one tap. It
works on reruns without another scan. It reads only this session key, never
saved lists or history. Opening the panel does not buy data, place a bet, train,
promote a model or change stored records. Existing scan actions are unchanged.

This is an **evidence snapshot and gap report**, not a completed prospective
packet or authenticated forward test. Current predictor output lacks exact
market/selection identifiers, event namespace, original/raw and baseline model
versions and their availability timestamps, plus odds-observation timestamps.
Its `prediction_timestamp` is blank. Existing clean/learned probabilities may
have been adjusted and cannot honestly be renamed as original raw predictions.
No values are invented to bridge these gaps.

The download:
- Keeps every supplied row, original order and repeated events, without choosing
  winners or dropping incomplete rows.
- Captures an explicit allowlist of prediction fields, retaining their values.
  Extra field names are listed as omitted; this is not a full-original-record
  archive. Arbitrary API context/error payloads and credential-named fields are excluded.
  This is not a secret scanner: sensitive text mistakenly embedded in an allowed
  event/source value or a field name is not detected. Review downloads before sharing.
- Represents nonfinite numeric values explicitly as invalid numeric tags, not
  zero, missingness or usable probabilities. Unsupported values fail the whole
  export rather than silently losing rows.
- Lists missing exact-schema fields, unapplied possible aliases and structural
  validation errors. Merely having fields does not authenticate their contents.
- Always keeps `packet_ready`, training and promotion false. A predeclared
  protocol and cohort-wide consistency review are still required even when all
  per-row fields are present.

Capture time is the local download-preparation time, not prediction creation or
an independent timestamp. Old session rows can be stale. The source already
passed predictor filters; it is not every scanned candidate or a precommitted
selection cohort. A hash detects an internal content change, not an attacker
rewriting content and recomputing it. No actual outcome, authenticated timestamp
or predictive-performance improvement is established here.

English and Spanish labels are available. This removes JSON entry for collecting
the currently available fields; it does not yet remove the missing upstream
provenance required for a valid prospective experiment. Users must retain their
downloads; server persistence is not implemented or proven by this panel.

Limits: 1–1,000 row objects, at most 10,000 characters per retained text value,
and an 8,000,000-byte UTF-8 canonical body. Exceeding a limit rejects the entire
export; rows are never silently truncated. Supported numeric values are native
integers/floats and losslessly representable NumPy integer/float16/32/64 scalars.
Other numeric types, including extended-precision floats, are rejected rather
than rounded.
