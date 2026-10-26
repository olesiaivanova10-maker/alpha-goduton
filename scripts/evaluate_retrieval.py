"""Evaluate a manually labelled JSON dataset. Never invent labels or quality claims."""

import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.rag.retriever import retrieve_bank_context

p = argparse.ArgumentParser()
p.add_argument("dataset", type=Path)
p.add_argument("--k", type=int, default=5)
a = p.parse_args()
rows = json.loads(a.dataset.read_text())
recalls = []
pages = []
no_answer = []
for row in rows:
    chunks = retrieve_bank_context(
        row["query"], top_k=a.k, filenames=row.get("allowed_files")
    )
    found = {(c.filename, c.page) for c in chunks}
    expected = {tuple(x) for x in row["expected_pages"]}
    if expected:
        recalls.append(len(found & expected) / len(expected))
        pages.append(len(found & expected) / max(1, len(found)))
    else:
        no_answer.append(not chunks)
print(
    json.dumps(
        {
            "queries": len(rows),
            "Recall@k": sum(recalls) / len(recalls) if recalls else None,
            "page_precision": sum(pages) / len(pages) if pages else None,
            "no_answer_accuracy": sum(no_answer) / len(no_answer)
            if no_answer
            else None,
        },
        indent=2,
    )
)
