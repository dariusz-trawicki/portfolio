"""Lightweight file-based model registry.

Directory layout:
    artifacts/models/v0001/   <- immutable bundle (model + preprocessing + metadata)
    artifacts/models/v0002/
    artifacts/registry.json   <- pointer: which version is "production" right now

MLflow Model Registry with aliases (e.g. a "champion" alias) works the same way:
versions are immutable, and deploying or rolling back just moves a pointer.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .config import ARTIFACTS_DIR


def models_dir(artifacts: Path) -> Path:
    return Path(artifacts) / "models"


def bundle_dir(artifacts: Path, version: str) -> Path:
    return models_dir(artifacts) / version


def next_version(artifacts: Path) -> str:
    existing = [int(p.name[1:]) for p in models_dir(artifacts).glob("v[0-9][0-9][0-9][0-9]")] if models_dir(artifacts).exists() else []
    return f"v{max(existing, default=0) + 1:04d}"


def _registry_path(artifacts: Path) -> Path:
    return Path(artifacts) / "registry.json"


def read_registry(artifacts: Path) -> dict:
    path = _registry_path(artifacts)
    return json.loads(path.read_text()) if path.exists() else {"production": None, "history": []}


def production_version(artifacts: Path) -> str | None:
    return read_registry(artifacts)["production"]


def promote(artifacts: Path, version: str, reason: str = "") -> None:
    if not bundle_dir(artifacts, version).exists():
        raise FileNotFoundError(f"bundle {version} does not exist")
    reg = read_registry(artifacts)
    reg["history"].append({
        "version": version, "previous": reg["production"], "reason": reason,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    reg["production"] = version
    _write_atomic(artifacts, reg)


def rollback(artifacts: Path) -> str:
    """Return to the previous production version (moves the pointer, deletes nothing)."""
    reg = read_registry(artifacts)
    if not reg["history"] or reg["history"][-1]["previous"] is None:
        raise RuntimeError("nothing to roll back to")
    previous = reg["history"][-1]["previous"]
    promote(artifacts, previous, reason=f"rollback from {reg['production']}")
    return previous


def _write_atomic(artifacts: Path, reg: dict) -> None:
    """Write via a temp file + os.replace: a reader never sees a half-written file."""
    path = _registry_path(artifacts)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, indent=2))
    os.replace(tmp, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Model registry")
    parser.add_argument("command", choices=["show", "rollback"])
    parser.add_argument("--artifacts", default=str(ARTIFACTS_DIR))
    args = parser.parse_args()
    if args.command == "rollback":
        print(f"production -> {rollback(Path(args.artifacts))}")
    print(json.dumps(read_registry(Path(args.artifacts)), indent=2))


if __name__ == "__main__":
    main()
