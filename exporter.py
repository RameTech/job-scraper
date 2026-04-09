"""Export scored job listings to CSV and HTML."""
from __future__ import annotations

import csv
import html as html_lib
from datetime import date
from pathlib import Path

from analyzer import ScoredListing


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "rank", "total", "role_score", "visa_score", "candidate_score",
    "title", "company", "location", "salary", "source", "url",
]


def export_csv(ranked: list[ScoredListing], out_path: str) -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for rank, sl in enumerate(ranked, 1):
            writer.writerow({
                "rank": rank,
                "total": sl.total,
                "role_score": sl.role_score,
                "visa_score": sl.visa_score,
                "candidate_score": sl.candidate_score,
                "title": sl.listing.title,
                "company": sl.listing.company,
                "location": sl.listing.location,
                "salary": sl.listing.salary,
                "source": sl.listing.source,
                "url": sl.listing.url,
            })
    return out_path


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def _score_class(total: int) -> str:
    if total >= 100: return "top"
    if total >= 60:  return "good"
    if total >= 20:  return "ok"
    if total >= 0:   return "neutral"
    return "low"


def _bar(score: int, max_score: int = 100) -> str:
    pct = max(0, min(100, int(score / max_score * 100))) if max_score else 0
    return f'<div class="bar"><div class="bar-fill" style="width:{pct}%"></div></div>'


def export_html(ranked: list[ScoredListing], out_path: str, run_date: str | None = None) -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    run_date = run_date or str(date.today())

    rows = []
    for rank, sl in enumerate(ranked, 1):
        l = sl.listing
        e = html_lib.escape
        url = e(l.url)
        title_link = f'<a href="{url}" target="_blank">{e(l.title)}</a>' if url else e(l.title)
        cls = _score_class(sl.total)
        salary = e(l.salary) if l.salary else "—"
        rows.append(f"""
        <tr class="{cls}">
          <td class="rank">{rank}</td>
          <td class="title">{title_link}</td>
          <td>{e(l.company)}</td>
          <td>{e(l.location)}</td>
          <td>{salary}</td>
          <td class="score">{sl.role_score}</td>
          <td class="score">{sl.visa_score}</td>
          <td class="score">{sl.candidate_score}</td>
          <td class="score total">{sl.total}</td>
          <td class="source">{e(l.source)}</td>
        </tr>""")

    rows_html = "\n".join(rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Results — {run_date}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #f5f5f5; color: #222; padding: 24px; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .meta {{ color: #666; font-size: .85rem; margin-bottom: 20px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border-radius: 8px; overflow: hidden;
           box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  th {{ background: #1a1a2e; color: #fff; text-align: left;
        padding: 10px 12px; font-size: .8rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: .04em; }}
  td {{ padding: 10px 12px; font-size: .88rem; border-bottom: 1px solid #eee;
        vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #fafafa; }}
  td.rank {{ color: #999; font-size: .8rem; width: 36px; }}
  td.title a {{ color: #1a6ef5; text-decoration: none; font-weight: 500; }}
  td.title a:hover {{ text-decoration: underline; }}
  td.score {{ text-align: right; font-variant-numeric: tabular-nums; width: 52px; }}
  td.total {{ font-weight: 700; }}
  td.source {{ color: #888; font-size: .8rem; }}
  /* Row colouring by total score */
  tr.top  td {{ background: #f0fdf4; }}
  tr.good td {{ background: #fffbeb; }}
  tr.low  td {{ background: #fff5f5; color: #888; }}
  tr.top:hover  td,
  tr.good:hover td,
  tr.low:hover  td {{ filter: brightness(.97); }}
  .legend {{ display: flex; gap: 16px; margin-top: 14px; font-size: .8rem; color: #666; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 4px; }}
  .dot-top  {{ background: #86efac; }}
  .dot-good {{ background: #fcd34d; }}
  .dot-low  {{ background: #fca5a5; }}
</style>
</head>
<body>
<h1>Job Results — Martha Hartl</h1>
<div class="meta">Run: {run_date} &nbsp;·&nbsp; {len(ranked)} listings &nbsp;·&nbsp;
Sorted by total score &nbsp;·&nbsp;
Scores: Role fit + Visa eligibility + Candidate fit</div>
<table>
  <thead>
    <tr>
      <th>#</th>
      <th>Role</th>
      <th>Company</th>
      <th>Location</th>
      <th>Salary</th>
      <th title="Role fit score">Role</th>
      <th title="Visa eligibility score">Visa</th>
      <th title="Candidate fit score">Cand</th>
      <th title="Total score">Total</th>
      <th>Source</th>
    </tr>
  </thead>
  <tbody>
{rows_html}
  </tbody>
</table>
<div class="legend">
  <span><span class="dot dot-top"></span>≥ 100 — strong match</span>
  <span><span class="dot dot-good"></span>60–99 — good match</span>
  <span><span class="dot dot-low"></span>negative — short-term / ineligible</span>
</div>
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path
