"""Write artifact-to-commit provenance for CI uploads."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

artifacts = []
for path in sorted(Path("dist").glob("*")):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    artifacts.append({"name": path.name, "sha256": digest})
Path("provenance.json").write_text(
    json.dumps(
        {
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "commit": os.environ.get("GITHUB_SHA"),
            "ref": os.environ.get("GITHUB_REF"),
            "artifacts": artifacts,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
