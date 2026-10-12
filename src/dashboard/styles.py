"""Page styles: andon board, alert card, typography details (REQ-014).

Tokens: concrete #EEF1F3, plate #FFFFFF, graphite #1D2731, steel #5A6670,
hairline #D3D9DE, line blue #2a78d6, andon amber #FAB219 (attention only).
"""

CSS = """
<style>
:root {
  --plate: #FFFFFF;
  --graphite: #1D2731;
  --steel: #5A6670;
  --hairline: #D3D9DE;
  --andon-amber: #FAB219;
  --andon-green: #0CA30C;
  --andon-gray: #898781;
  --condensed: "Barlow Condensed", "Barlow", system-ui, sans-serif;
}

/* Numbers that are compared line by line stay aligned. */
[data-testid="stMetricValue"], [data-testid="stDataFrame"] { font-variant-numeric: tabular-nums; }
[data-testid="stMetricValue"] { font-family: var(--condensed); }

.stTabs [data-baseweb="tab"] p { font-family: var(--condensed); font-size: 1.15rem; font-weight: 600; }

/* Andon board: one plate per line; the lamp carries the state, the label says it. */
.andon-board {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin: 4px 0 8px;
}
.andon-plate {
  background: var(--plate);
  border: 1px solid var(--hairline);
  border-radius: 4px;
  padding: 0 16px 14px;
  overflow: hidden;
}
.andon-lamp { height: 8px; margin: 0 -16px 12px; background: var(--andon-gray); }
.andon-alert .andon-lamp { background: var(--andon-amber); }
.andon-normal .andon-lamp { background: var(--andon-green); }
.andon-line {
  font-family: var(--condensed);
  font-weight: 700;
  font-size: 2.6rem;
  line-height: 1;
  color: var(--graphite);
}
.andon-label { margin-top: 6px; font-weight: 600; color: var(--graphite); }
.andon-alert .andon-label span { color: #B37800; }
.andon-normal .andon-label span { color: var(--andon-green); }
.andon-not_evaluated .andon-label span { color: var(--andon-gray); }
/* Streamlit adds list indentation to rendered HTML; reset it inside the plates. */
.andon-plate ul.andon-details {
  list-style: none; margin: 4px 0 0 !important; padding: 0 !important;
  color: var(--steel); font-size: 0.9rem;
}
.andon-plate ul.andon-details li { margin: 0 !important; padding: 0 !important; }

/* Alert card: what happened, compared with what, and where to start. */
.alert-card {
  background: var(--plate);
  border: 1px solid var(--hairline);
  border-left: 8px solid var(--andon-amber);
  border-radius: 4px;
  padding: 16px 20px 18px;
  max-width: 920px;
}
.alert-card h3 {
  font-family: var(--condensed);
  font-weight: 700;
  font-size: 1.5rem;
  line-height: 1.2;
  margin: 0 0 12px;
  padding: 0;
  color: var(--graphite);
}
.alert-card dl {
  padding: 0 !important;
  display: grid;
  grid-template-columns: minmax(130px, max-content) 1fr;
  gap: 6px 20px;
  margin: 0;
}
.alert-card dt { color: var(--steel); font-weight: 600; margin: 0 !important; padding: 0 !important; }
.alert-card dd { margin: 0 !important; padding: 0 !important; color: var(--graphite); }
.alert-card .alert-focus { grid-column: 1 / -1; margin-top: 8px; padding-top: 10px; border-top: 1px solid var(--hairline); }
.alert-card .alert-focus strong { font-weight: 600; }

@media (max-width: 640px) {
  .alert-card dl { grid-template-columns: 1fr; gap: 2px; }
  .alert-card dd { margin-bottom: 6px; }
  .andon-line { font-size: 2.2rem; }
}
</style>
"""
