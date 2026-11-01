"""Select synthetic images for the k6 scripts and write an index.

Usage::

    make synthetic APPLICATIONS=20
    python load-tests/prepare_payloads.py --count 200

Writes ``load-tests/payloads/index.json`` (git-ignored) listing image
paths with their tenant and application, which k6 opens at start-up.
"""

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    """Pick the first ``count`` documents from the manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("synthetic/output"))
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--out", type=Path, default=Path("load-tests/payloads/index.json"))
    args = parser.parse_args(argv)
    entries = []
    with (args.dataset / "manifest.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            label = json.loads(line)
            entries.append(
                {
                    "path": str((args.dataset / label["image_path"]).resolve()),
                    "tenant_id": label["tenant_id"],
                    "application_id": label["application_id"],
                    "document_type": label["document_type"],
                }
            )
            if len(entries) >= args.count:
                break
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(entries, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
