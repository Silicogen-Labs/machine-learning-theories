from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rtl_analyzer.ml.dataset_manifest import (
    DatasetEntry,
    build_grouped_splits,
    read_manifest,
    sha256_file,
    write_manifest,
)


SUPPORTED_SUFFIXES = (".v", ".sv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a deterministic Phase 3 dataset manifest.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--synthetic-source", required=True, type=Path)
    parser.add_argument("--external-source", required=True, type=Path)
    return parser.parse_args()


def iter_source_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix in SUPPORTED_SUFFIXES)


def build_entries(source_root: Path, source_type: str) -> list[DatasetEntry]:
    files = iter_source_files(source_root)
    entries: list[DatasetEntry] = []
    for path in files:
        relative_path = path.relative_to(source_root)
        labels = ["clean"] if "clean" in path.parts else ["buggy"]
        portable_source_path = relative_path.as_posix()
        source_group = f"{source_type}:{portable_source_path}"
        sample_id = f"{source_type}:{relative_path.as_posix()}"
        entries.append(
            DatasetEntry(
                sample_id=sample_id,
                source_group=source_group,
                source_type=source_type,
                path=portable_source_path,
                labels=labels,
                metadata={"source_path": portable_source_path},
            )
        )
    return entries


def materialize_dataset(
    entries: list[DatasetEntry],
    output_dir: Path,
    seed: int,
    source_roots: dict[str, Path],
) -> Path:
    reset_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val", "test"):
        (output_dir / split).mkdir(parents=True, exist_ok=True)

    manifest_entries: list[DatasetEntry] = []
    for entry in build_grouped_splits(entries, seed=seed):
        source_path = source_roots[entry.source_type] / str(entry.metadata["source_path"])
        destination = output_dir / entry.split / entry.source_type / entry.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        manifest_entries.append(
            DatasetEntry(
                sample_id=entry.sample_id,
                source_group=entry.source_group,
                source_type=entry.source_type,
                path=destination.relative_to(output_dir).as_posix(),
                labels=entry.labels,
                security_labels=entry.security_labels,
                rationale=entry.rationale,
                line_hints=entry.line_hints,
                sha256=sha256_file(destination),
                split=entry.split,
                metadata=entry.metadata,
            )
        )

    manifest_path = output_dir / "manifest.json"
    write_manifest(manifest_path, manifest_entries, seed=seed)
    return manifest_path


def reset_output_dir(output_dir: Path) -> None:
    for split in ("train", "val", "test"):
        split_dir = output_dir / split
        if split_dir.exists():
            shutil.rmtree(split_dir)

    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest_path.unlink()


def main() -> int:
    args = parse_args()
    try:
        entries = collect_entries(args.synthetic_source, args.external_source)
        manifest_path = materialize_dataset(
            entries,
            args.output_dir,
            seed=args.seed,
            source_roots={
                "synthetic": args.synthetic_source,
                "external": args.external_source,
            },
        )
    except DatasetBuildError as exc:
        print(f"dataset build unavailable: {exc}", file=sys.stderr)
        return 2

    manifest = read_manifest(manifest_path)
    print(f"dataset manifest written to {manifest_path}")
    print(f"entries: {len(manifest.entries)} seed: {manifest.seed}")
    return 0


def collect_entries(synthetic_source: Path, external_source: Path) -> list[DatasetEntry]:
    entries: list[DatasetEntry] = []
    for source_root, source_type in (
        (synthetic_source, "synthetic"),
        (external_source, "external"),
    ):
        if not source_root.exists():
            raise DatasetBuildError(f"missing source directory: {source_root}")
        source_entries = build_entries(source_root, source_type)
        if not source_entries:
            raise DatasetBuildError(f"no Verilog sources found in {source_root}")
        entries.extend(source_entries)
    return entries


class DatasetBuildError(RuntimeError):
    pass


if __name__ == "__main__":
    raise SystemExit(main())
