from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

# Repo root on path when running as `python scripts/reindex.py`
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

load_dotenv()

from src.core.indexing import reindex_tenant_from_truth_pdf  # noqa: E402
from src.core.storage import tenant_paths  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild tenant Chroma index from truth PDF.")
    parser.add_argument("--tenant-id", required=True, help="Tenant folder name under tenants/")
    parser.add_argument(
        "--pdf",
        default=None,
        help="Optional PDF path (default: tenants/<id>/truth/truth.pdf)",
    )
    args = parser.parse_args()
    paths = tenant_paths(args.tenant_id)
    pdf = Path(args.pdf) if args.pdf else paths.truth_pdf_path
    if not pdf.is_file():
        print(f"Error: PDF not found: {pdf}", file=sys.stderr)
        return 1
    n = reindex_tenant_from_truth_pdf(paths.tenant_id, pdf)
    print(f"Indexed {n} chunks for tenant={paths.tenant_id} -> {paths.vectorstore_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
