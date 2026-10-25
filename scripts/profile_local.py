"""Local preprocessing benchmark. Never invokes a provider or estimates money."""

import sys, argparse, json, time, statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.data_loader import DATA
from backend.app.company_context import get_company_context
from backend.app.news_ingestion import parse_rss, sort_news

p = argparse.ArgumentParser()
p.add_argument("--news", type=int, default=1000)
p.add_argument("--companies", type=int, default=10)
a = p.parse_args()
xml = (
    "<rss><channel>"
    + "".join(
        "<item><guid>"
        + str(i)
        + "</guid><title>Кредит и ключевая ставка "
        + str(i)
        + "</title><link>https://example.com/"
        + str(i)
        + "</link><description>Макроэкономическая новость</description></item>"
        for i in range(a.news)
    )
    + "</channel></rss>"
).encode()
t = time.perf_counter()
rows = parse_rss(xml, "Fixture")
parse_ms = (time.perf_counter() - t) * 1000
profiles = []
ranks = []
for company in DATA.companies["SYNTHETIC_U"].drop_duplicates().head(a.companies):
    t = time.perf_counter()
    context = get_company_context(str(company))
    profiles.append((time.perf_counter() - t) * 1000)
    t = time.perf_counter()
    sort_news(rows, context, 3)
    ranks.append((time.perf_counter() - t) * 1000)
print(
    json.dumps(
        {
            "news": len(rows),
            "companies": len(profiles),
            "csv_mode": "synthetic"
            if any(w.startswith("DEMO_FALLBACK") for w in DATA.warnings)
            else "csv",
            "rss_parse_ms": round(parse_ms, 2),
            "profile_mean_ms": round(statistics.mean(profiles), 2),
            "presort_mean_ms": round(statistics.mean(ranks), 2),
            "model_calls": 0,
            "scope": "Preprocessing only; no inference, DB-load or concurrent production SLO claim",
        },
        ensure_ascii=False,
        indent=2,
    )
)
