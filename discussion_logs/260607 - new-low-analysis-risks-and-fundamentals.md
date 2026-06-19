---
createdate: 2026-06-07
changedate: 2026-06-07
topic: "New-low event analysis risks and fundamental context"
source: "discussion"
status: "active"
---

# New-Low Analysis Risks And Fundamentals

## Context

We explored a new type of analysis for what happens after an asset makes a new
N-session low. This is not a normal factor. It is an event/episode study:
identify the start of a new-low episode, deduplicate clustered lower lows, then
measure further downside, recovery duration, ignored new lows, and forward
returns.

We also discussed adding fundamentals as a separate dashboard to understand
whether a company is financially deteriorating before or during severe
drawdowns.

## Key Points

- New-low analysis is an event study, not a factor score.
- The dedup rule treats the first N-session low as the episode start and ignores
  later new lows until price recovers to the original pre-break level.
- Quick recoveries can be ignored so very short dips do not dominate the sample.
- Useful outputs include current episode status, max drawdown percentile,
  recovery-session percentile, ignored-new-low percentile, and forward returns.
- Comparing stocks side by side can show different character: some names tend to
  recover cleanly, while others can remain impaired for much longer.
- Fundamentals should be separate from price-event analysis because they answer
  a different question: whether the business quality is improving, stable, or
  deteriorating.

## Decisions / Current Understanding

- Keep new-low analysis as an event analysis module/page, separate from factors.
- Keep the fundamental dashboard as its own page.
- Use SEC EDGAR companyfacts for US company fundamentals.
- Use SEC submissions metadata for filing acceptance time when measuring
  earnings/filing reaction returns.
- For after-close filings, use the next trading session as the reaction date.
- For before-open or market-hours filings, use that same trading session as the
  reaction date.
- Fundamentals to watch include revenue, operating income, net income, free cash
  flow, margins, capex intensity, debt, net cash, EPS, and share count.

## Risks / Caveats

- Historical percentiles are descriptive, not causal. A current episode can
  exceed all historical cases.
- Survivorship bias is serious. If only surviving companies are studied, the
  analysis may underestimate permanent impairment and delisting risk.
- Index filtering can reduce some catastrophic-loss exposure, but it is not a
  complete solution. A company can suffer severe losses before leaving an index.
- Using current index membership for old history creates lookahead bias. Index
  membership must be point-in-time if it is used as a rule.
- Fundamentals are lagged and can be revised. SEC data is useful, but it is not
  real-time business truth.
- Accounting quality can vary by company and sector; the same metric is not
  always comparable across all businesses.
- Earnings reaction analysis needs timing awareness. Same-day return can be
  wrong for after-close releases, so the reaction session must be selected from
  filing acceptance time.
- Price-event data can be distorted by splits, bad adjusted prices, missing
  sessions, or source-specific differences.
- Deduplication rules shape the statistics. Changing the recovery threshold or
  quick-ignore threshold can materially change the sample.

## Future Follow-Ups

- Add point-in-time index membership if index inclusion/exclusion becomes part
  of a strategy rule.
- Add delisted/dead-company datasets if we want to directly study survivorship
  bias.
- Add next-session, two-session, and five-session filing reaction returns.
- Separate SEC filing reaction from actual earnings press-release reaction when
  earnings release timestamps are available.
- Add fundamental deterioration flags before and during new-low episodes.
- Add sector-aware fundamental templates because banks, software, restaurants,
  and industrial companies need different metric emphasis.
