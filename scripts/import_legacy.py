"""Manual offline import. Never runs at startup; source files remain untouched."""

import argparse, json, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.storage import repositories as repo

p = argparse.ArgumentParser()
p.add_argument("--news-json", type=Path)
p.add_argument("--insights-sqlite", type=Path)
p.add_argument("--dry-run", action="store_true")
a = p.parse_args()
if a.news_json:
    data = json.loads(a.news_json.read_text())
    print("News records", len(data["items"]))
    if not a.dry_run:
        repo.put_news(data["items"], data.get("sources", {}))
if a.insights_sqlite:
    db = sqlite3.connect(
        "file:" + str(a.insights_sqlite.resolve()) + "?mode=ro", uri=True
    )
    for company, role, raw in db.execute("select company_id,role,event from insights"):
        event = json.loads(raw)
        audit = event.get("audit", {})
        if (
            audit.get("is_valid") is not True
            or audit.get("hallucination_detected") is not False
        ):
            print("Skipped unverified legacy result")
            continue
        print("Verified legacy card", event["card_id"])
        if not a.dry_run:
            repo.put_news(
                [
                    {
                        "news_id": event["news_id"],
                        "title": event["title"],
                        "published_at": event.get("published_at"),
                    }
                ]
            )
            # Legacy dependencies cannot be reconstructed; retain trace but never pretend version is current.
            repo.save_insight(company, role, event, "legacy-unknown")
    db.close()
