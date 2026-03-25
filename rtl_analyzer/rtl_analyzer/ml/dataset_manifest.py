from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import json
from pathlib import Path
import random


@dataclass(frozen=True)
class DatasetEntry:
    sample_id: str
    source_group: str
    source_type: str
    path: str
    labels: list[str]
    security_labels: list[str] = field(default_factory=list)
    rationale: str = ""
    line_hints: list[int] = field(default_factory=list)
    sha256: str = ""
    split: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class DatasetManifest:
    seed: int
    entries: list[DatasetEntry]


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_grouped_splits(
    entries: list[DatasetEntry],
    seed: int,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> list[DatasetEntry]:
    if not entries:
        return []

    groups = sorted({entry.source_group for entry in entries})
    shuffled_groups = groups[:]
    random.Random(seed).shuffle(shuffled_groups)

    assignments = _assign_group_splits(shuffled_groups, train_ratio=train_ratio, val_ratio=val_ratio)
    return [replace(entry, split=assignments[entry.source_group]) for entry in entries]


def write_manifest(path: Path, entries: list[DatasetEntry], seed: int) -> None:
    manifest = {
        "seed": seed,
        "entries": [asdict(entry) for entry in entries],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_manifest(path: Path) -> DatasetManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = [DatasetEntry(**entry_payload) for entry_payload in payload.get("entries", [])]
    return DatasetManifest(seed=payload["seed"], entries=entries)


def _assign_group_splits(
    groups: list[str],
    train_ratio: float,
    val_ratio: float,
) -> dict[str, str]:
    total = len(groups)
    if total == 1:
        counts = {"train": 1, "val": 0, "test": 0}
    elif total == 2:
        counts = {"train": 1, "val": 0, "test": 1}
    else:
        train_count = max(1, int(total * train_ratio))
        val_count = max(1, int(total * val_ratio))
        test_count = total - train_count - val_count

        if test_count < 1:
            if train_count >= val_count and train_count > 1:
                train_count -= 1
            else:
                val_count -= 1
            test_count = total - train_count - val_count

        counts = {"train": train_count, "val": val_count, "test": test_count}

    assignments: dict[str, str] = {}
    index = 0
    for split in ("train", "val", "test"):
        for group in groups[index : index + counts[split]]:
            assignments[group] = split
        index += counts[split]
    return assignments
