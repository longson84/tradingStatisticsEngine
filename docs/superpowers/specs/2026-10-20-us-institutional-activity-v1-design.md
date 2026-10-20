# US Institutional Activity v1 Design

## Goal

Add a PostgreSQL-backed US equity view of institutional positions and reported
quarter-to-quarter position changes derived from SEC Form 13F filings.

## Product contract

- The feature is named **Institutional Activity**. It must not call inferred
  changes confirmed transactions or claim an execution date or price.
- It supports exact active US common-stock Instruments only.
- The first release shows up to eight report periods, current holders, and
  `new`, `added`, `unchanged`, `reduced`, and `exited` position changes.
- Every response exposes both the portfolio report period and the filing
  acceptance time. Research availability begins at the filing acceptance time;
  factors and strategies may consume it only from the next eligible session.
- Page reads use PostgreSQL only. SEC and identifier-provider access occurs in
  explicit refresh workflows.

## Canonical data

- `institutional_managers` identifies a filer by SEC CIK.
- `institutional_filings` stores immutable SEC accessions and amendments.
- `instrument_identifiers` stores security-level identifiers such as CUSIP and
  FIGI against the exact Instrument, never against Company.
- `institutional_filing_positions` preserves each as-filed information-table
  row, including unmapped CUSIPs, options, and source-row identity.
- Position changes are a versioned analytical projection over effective filing
  revisions. They are not authoritative trade records.
- Common stock, put, and call rows remain separate. V1 presents common-stock
  activity only.

## Acquisition

- SEC quarterly 13F archives are the canonical public source. The adapter
  streams official ZIP/TSV content and preserves accession/source provenance.
- A position attaches to an Instrument only through a verified effective-dated
  CUSIP mapping. Issuer-name or ticker similarity never creates a mapping.
- Amendments remain immutable and supersede earlier filings only through an
  explicit effective-revision rule.
- Invalid or unmapped rows are retained with machine-readable quality status.

## UI

The page reuses the shared instrument picker, constrained to US common stocks.
It shows freshness, coverage, holder count, action totals, reported-shares
history, latest changes, current holders, source filing links, and explicit
unsupported/unmapped/no-data states.

## Deferred

- Schedule 13D/13G beneficial-ownership events.
- Automatic CUSIP discovery without a verified identifier provider.
- Estimated trade price, conviction scores, or strategy signals.
- A manager-centric portfolio page.
