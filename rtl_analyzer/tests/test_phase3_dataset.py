from pathlib import Path
import shutil
import subprocess
import sys

from rtl_analyzer.ml.dataset_manifest import (
    DatasetEntry,
    build_grouped_splits,
    read_manifest,
    write_manifest,
)


FIXTURES = Path(__file__).parent / "fixtures"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_phase3_dataset.py"


def run_build_script(output_dir: Path, *, synthetic_source: Path, external_source: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-dir",
            str(output_dir),
            "--seed",
            "7",
            "--synthetic-source",
            str(synthetic_source),
            "--external-source",
            str(external_source),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_grouped_split_is_deterministic(tmp_path):
    entries = [
        DatasetEntry(
            sample_id="a",
            source_group="repo_a",
            source_type="synthetic",
            path="a.v",
            labels=["clean"],
        ),
        DatasetEntry(
            sample_id="b",
            source_group="repo_b",
            source_type="external",
            path="b.v",
            labels=["combo_loop"],
        ),
        DatasetEntry(
            sample_id="c",
            source_group="repo_c",
            source_type="external",
            path="c.v",
            labels=["clean"],
        ),
    ]

    assert build_grouped_splits(entries, seed=7) == build_grouped_splits(entries, seed=7)


def test_grouped_split_uses_all_splits_with_three_groups(tmp_path):
    entries = [
        DatasetEntry(
            sample_id="a",
            source_group="repo_a",
            source_type="synthetic",
            path="a.v",
            labels=["clean"],
        ),
        DatasetEntry(
            sample_id="b",
            source_group="repo_b",
            source_type="external",
            path="b.v",
            labels=["combo_loop"],
        ),
        DatasetEntry(
            sample_id="c",
            source_group="repo_c",
            source_type="external",
            path="c.v",
            labels=["clean"],
        ),
    ]

    splits = {entry.split for entry in build_grouped_splits(entries, seed=7)}

    assert splits == {"train", "val", "test"}


def test_manifest_round_trip_preserves_seed_and_sha(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    entry = DatasetEntry(
        sample_id="demo",
        source_group="repo_x",
        source_type="external",
        path="demo.v",
        labels=["clean"],
        sha256="abc",
    )

    write_manifest(manifest_path, [entry], seed=7)
    manifest = read_manifest(manifest_path)

    assert manifest.seed == 7
    assert manifest.entries[0].sha256 == "abc"


def test_manifest_can_store_security_scanner_fields(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    entry = DatasetEntry(
        sample_id="sec-1",
        source_group="repo_sec",
        source_type="external",
        path="demo.v",
        labels=["clean"],
        security_labels=["CWE-1245"],
        rationale="demo rationale",
        line_hints=[12, 18],
    )

    write_manifest(manifest_path, [entry], seed=7)
    manifest = read_manifest(manifest_path)

    assert manifest.entries[0].security_labels == ["CWE-1245"]
    assert manifest.entries[0].line_hints == [12, 18]


def test_build_script_writes_manifest_and_split_directories(tmp_path):
    output_dir = tmp_path / "dataset"

    result = run_build_script(
        output_dir,
        synthetic_source=FIXTURES / "buggy",
        external_source=FIXTURES / "clean",
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "train").is_dir()
    assert (output_dir / "val").is_dir()
    assert (output_dir / "test").is_dir()

    manifest = read_manifest(output_dir / "manifest.json")

    assert {entry.split for entry in manifest.entries} == {"train", "val", "test"}


def test_build_script_reports_missing_sources_cleanly(tmp_path):
    output_dir = tmp_path / "dataset"

    result = run_build_script(
        output_dir,
        synthetic_source=tmp_path / "missing-buggy",
        external_source=FIXTURES / "clean",
    )

    assert result.returncode == 2
    assert "dataset build unavailable:" in result.stderr


def test_build_script_manifest_is_portable_across_checkout_roots(tmp_path):
    first_root = tmp_path / "checkout-a"
    second_root = tmp_path / "checkout-b"

    shutil.copytree(FIXTURES / "buggy", first_root / "buggy")
    shutil.copytree(FIXTURES / "clean", first_root / "clean")
    shutil.copytree(FIXTURES / "buggy", second_root / "buggy")
    shutil.copytree(FIXTURES / "clean", second_root / "clean")

    first_output = tmp_path / "dataset-a"
    second_output = tmp_path / "dataset-b"

    first_result = run_build_script(
        first_output,
        synthetic_source=first_root / "buggy",
        external_source=first_root / "clean",
    )
    second_result = run_build_script(
        second_output,
        synthetic_source=second_root / "buggy",
        external_source=second_root / "clean",
    )

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    assert (first_output / "manifest.json").read_text(encoding="utf-8") == (
        second_output / "manifest.json"
    ).read_text(encoding="utf-8")

    manifest = read_manifest(first_output / "manifest.json")

    assert all(not Path(str(entry.metadata["source_path"])).is_absolute() for entry in manifest.entries)


def test_build_script_recreates_split_outputs_on_rerun(tmp_path):
    output_dir = tmp_path / "dataset"

    first_result = run_build_script(
        output_dir,
        synthetic_source=FIXTURES / "buggy",
        external_source=FIXTURES / "clean",
    )

    assert first_result.returncode == 0, first_result.stderr

    stale_file = output_dir / "train" / "stale.txt"
    stale_file.parent.mkdir(parents=True, exist_ok=True)
    stale_file.write_text("stale\n", encoding="utf-8")
    (output_dir / "manifest.json").write_text("stale\n", encoding="utf-8")

    second_result = run_build_script(
        output_dir,
        synthetic_source=FIXTURES / "buggy",
        external_source=FIXTURES / "clean",
    )

    assert second_result.returncode == 0, second_result.stderr
    assert not stale_file.exists()
    assert read_manifest(output_dir / "manifest.json").seed == 7


def test_build_script_uses_source_relative_groups_for_duplicate_stems(tmp_path):
    synthetic_source = tmp_path / "buggy"
    external_source = tmp_path / "clean"
    (synthetic_source / "alpha").mkdir(parents=True)
    (synthetic_source / "beta").mkdir(parents=True)
    shutil.copy2(FIXTURES / "buggy" / "buggy_counter.v", synthetic_source / "alpha" / "shared.v")
    shutil.copy2(FIXTURES / "buggy" / "buggy_combo_loop.v", synthetic_source / "beta" / "shared.v")
    shutil.copytree(FIXTURES / "clean", external_source)

    result = run_build_script(
        tmp_path / "dataset",
        synthetic_source=synthetic_source,
        external_source=external_source,
    )

    assert result.returncode == 0, result.stderr

    manifest = read_manifest(tmp_path / "dataset" / "manifest.json")
    shared_entries = [
        entry for entry in manifest.entries if entry.metadata.get("source_path") in {"alpha/shared.v", "beta/shared.v"}
    ]

    assert {entry.source_group for entry in shared_entries} == {
        "synthetic:alpha/shared.v",
        "synthetic:beta/shared.v",
    }
