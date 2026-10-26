"""Explicit download only; never imported from an HTTP handler."""

import argparse, re
from pathlib import Path
from huggingface_hub import snapshot_download

p = argparse.ArgumentParser()
p.add_argument("--directory", required=True)
p.add_argument(
    "--reranker-revision",
    required=True,
    help="Immutable SHA from the official model repository",
)
a = p.parse_args()
if not re.fullmatch("[0-9a-f]{40}", a.reranker_revision):
    p.error("Use an immutable 40-character commit SHA")
root = Path(a.directory)
snapshot_download(
    "BAAI/bge-m3",
    revision="5617a9f61b028005a4858fdac845db406aefb181",
    local_dir=root / "bge-m3",
    allow_patterns=["*.json", "*.bin", "*.model", "1_Pooling/*"],
)
snapshot_download(
    "BAAI/bge-reranker-v2-m3",
    revision=a.reranker_revision,
    local_dir=root / "reranker",
    allow_patterns=["*.json", "*.safetensors", "*.model"],
)
(root / "manifest.json").write_text(
    __import__("json").dumps(
        {
            "embedding_revision": "5617a9f61b028005a4858fdac845db406aefb181",
            "reranker_revision": a.reranker_revision,
        }
    )
)
