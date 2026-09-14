"""Fail CI when approved architecture silently drifts or required evidence disappears."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BASELINE_FILE = ROOT / "architecture-baseline.json"


def main() -> int:
    baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    architecture = ROOT / baseline["architecture_document"]
    actual_hash = hashlib.sha256(architecture.read_bytes()).hexdigest()
    errors: list[str] = []
    if actual_hash != baseline["sha256"]:
        errors.append(
            "approved architecture document changed without an updated, user-approved ACP baseline"
        )
    for relative_path, required_tokens in baseline["required_evidence"].items():
        path = ROOT / relative_path
        if not path.is_file():
            errors.append(f"required architecture evidence file is missing: {relative_path}")
            continue
        text = path.read_text(encoding="utf-8")
        for token in required_tokens:
            if token not in text:
                errors.append(f"required architecture evidence is missing: {relative_path} -> {token}")
    for relative_dir in baseline.get("required_directories", []):
        if not (ROOT / relative_dir).is_dir():
            errors.append(f"required module directory is missing: {relative_dir}")
    for relative_path, max_lines in baseline.get("thin_entrypoints", {}).items():
        path = ROOT / relative_path
        if not path.is_file():
            errors.append(f"thin entrypoint is missing: {relative_path}")
            continue
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > max_lines:
            errors.append(f"entrypoint became a catch-all module: {relative_path} has {line_count} lines, max {max_lines}")
    for relative_path in baseline.get("forbidden_root_modules", []):
        if (ROOT / relative_path).exists():
            errors.append(f"flat root module must remain moved into an owned package: {relative_path}")
    if errors:
        for error in errors:
            print(f"ARCHITECTURE_GUARD_FAIL: {error}")
        return 1
    print(
        "ARCHITECTURE_GUARD_PASS: "
        f"{baseline['approved_change_id']} {architecture.name} sha256={actual_hash}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
