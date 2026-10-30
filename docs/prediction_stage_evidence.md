# Session-only pre-ranking evidence

Pro Predictor and Volume retain a separate download of all **built** rows before
scanner scoring, adaptive ranking and decision filters. The unchanged pipeline
continues normally. No evidence columns are added to persisted rows; this feature
does not call providers, train, write files, alter history or launch a scan.

The stage is after provider truncation, summarization, optional existing market
calibration and build-time sport/date/team/book filters. It is not the whole
scanned population or a predeclared cohort. Stage probabilities are named as
stage values, not independent original raw-model or baseline forecasts.

The local stage capture clock is not prediction creation time, provider update
time, odds observation time or authenticated pre-event commitment. Original timing,
immutable model/baseline artifacts and canonical settlement identities remain
unknown. Training, promotion, packet readiness and predictive-gain proof remain
false. A hash detects internal changes only, not independent authenticity.

The immutable JSON retains order and duplicate rows. It includes only allowlisted
event/selection labels, supplied event time/market/line, stage probabilities and
prices/book display title/count. Unknown field names and values, API context,
outcomes, credentials and error payloads are not exported. Allowed text may still
contain sensitive text supplied upstream: this is not a secret scanner. Review
downloads before sharing. Nonfinite numbers are explicitly invalid numeric tags.

Limits: 1–1000 rows, 10,000 characters per retained text field, 8,000,000 UTF-8
bytes including the digest. Unsupported values or any limit failure reject the
entire snapshot, never silently truncating it. Failure affects evidence only,
not existing predictions. Each requested run clears old stage evidence before
key checks/other early exits. A run with no built rows has no snapshot. A run with
built rows but no passing decisions still retains stage evidence for a later
rerun. Downloads keep the actual originating route and original stage capture
time across reruns or route changes. Session loss loses this snapshot; server
persistence is neither implemented nor certified. The existing passed-row
download and its schema are unchanged.
