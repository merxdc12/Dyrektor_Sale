# ITHutir Pinterest OS — Phase 0 Integration Audit

Date: 2026-11-09. Scope: read-only review of GitHub source, followed by limited corrective commits. No local Linux Mint access. **CI and GUI execution not verified** (commit workflow-run lookup returned no runs; this is not a passing result).

## Interaction map

Pinterest metrics CSV -> pinterest_metrics -> analytics_metrics -> AnalyticsPage
Business attribution CSV -> business_metrics -> business_summary -> product_profitability -> decision_report -> AnalyticsPage
Manual cost entry -> cost_entries -> cost_summary -> product_profitability
TIME entries -> labor_rates + time_entries -> labor_summary -> product_profitability
Projects -> Storage(database) -> AnalyticsPage.refresh -> nested ProfitCostsPanel

## Findings and evidence

| ID | Severity | Finding | Evidence | Status |
|---|---|---|---|---|
| A01 | High | SCALE recommendation ignored unassigned overhead and unassigned labor, overstating readiness | product_decisions.py / profit_costs.py | Corrected: downgrade SCALE to TEST when unassigned costs/time exist |
| A02 | Medium | Analytics currency filter showed only currencies in business_metrics; cost-only data could be invisible | analytics.py refresh() | Corrected: union currencies across business_metrics, cost_entries and labor_rates |
| A03 | High | Duplicate expense entry possible between CSV reported_cost_cents and manual cost_entries; no source ID or reconciliation | business_metrics.py / profit_costs.py | Open: user warning only; no deduplication across sources |
| A04 | High | Product profitability uses CURRENT pin.product_id for all historical records | product_profitability.py | Open: historical attribution not tracked |
| A05 | Medium | Labor uses CURRENT hourly rate for all historical time_entries | profit_costs.py | Open: no rate history |
| A06 | Medium | Unassigned cost and time are kept separate, not allocated | product_profitability.py | Partially mitigated by A01; allocation policy still required |
| A07 | Medium | Project switch updates analytics_page.storage and calls refresh; nested profit_costs.storage is updated inside refresh | app.py _switch_project / analytics.py refresh | Source path confirmed; GUI runtime unverified |
| A08 | Medium | Analytics tab contains multiple large tables and nested panel without dedicated internal scrolling | app.py / analytics.py | Open: UI usability needs offscreen GUI acceptance test |
| A09 | High | ROI denominator represents recorded expenses, not necessarily full invested capital; SCALE thresholds are heuristic | product_profitability.py / product_decisions.py | Open: keep as decision support, never verified net profit |
| A10 | Medium | No proof of successful workflow execution for latest commits | GitHub commit workflow runs lookup returned empty | Open: verify Actions on GitHub |
| A11 | Medium | Business CSV accepts conversions greater than visits; may be valid for multi-order attribution but needs defined metric semantics | business_metrics.py | Open: document counting policy |
| A12 | Medium | Financial amount display uses floating-point division for formatting; storage and aggregation remain integer cents | analytics.py / profit_panel.py | Open: prefer Decimal formatting |

## Capability matrix

| Capability | Source implemented | Verified by execution |
|---|---|---|
| Local SQLite schema creation | Yes | No |
| CSV Pinterest metrics import | Yes | No |
| CSV business metrics import | Yes | No |
| Cost ledger / labor rate | Yes | No |
| Product contribution and ROI | Yes | No |
| Conservative product decisions | Yes | No |
| Project switching | Yes | No |
| Regression tests in workflow | Yes | No |

## Prioritized next steps

1. Run GitHub Actions and inspect exact failing jobs; repair before feature expansion.
2. Add cost provenance/source identifiers and explicit reconciliation to prevent double counting.
3. Introduce immutable attribution snapshots and effective-dated labor rates.
4. Define reporting period and accounting rules; isolate unallocated overhead from product contribution.
5. Perform PyQt6 offscreen smoke test and manual Linux Mint acceptance test.

**Decision:** NOT RELEASE-READY until tests pass and double-counting controls are implemented. No claims of real profit, actual Pinterest sales, or measured commercial ROI without evidence.
