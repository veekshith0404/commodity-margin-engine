from __future__ import annotations

import hashlib
import importlib.metadata
import os
import re
import subprocess
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from build_review_package import main as build_review_package
from refresh_sample_outputs import SAMPLE_RUNS, main as refresh_sample_outputs


ROOT = Path(__file__).resolve().parent

DATA_FILES = (
    ROOT / "data" / "daily-retail-prices-of-essential-commodities.csv",
    ROOT / "data" / "state-level-daily-wholesale-price.csv",
)

REQUIREMENTS_FILES = (
    ROOT / "requirements.txt",
    ROOT / "requirements-dev.txt",
)


def _normalize_package_name(name: str) -> str:
    """Normalize package names according to standard Python naming rules."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _validate_release_environment() -> str:
    """Require this project's virtual environment and compatible Python."""
    if sys.version_info < (3, 12):
        raise RuntimeError(
            "Python 3.12 or newer is required. "
            "Activate this project's .venv and try again."
        )

    expected_venv = (ROOT / ".venv").resolve()
    active_venv = Path(sys.prefix).resolve()

    if active_venv != expected_venv:
        raise RuntimeError(
            "This release check must run inside this project's .venv.\n"
            "In PowerShell, run:\n"
            "  .\\.venv\\Scripts\\Activate.ps1\n"
            "Then run:\n"
            "  python prepare_review.py\n"
            f"Expected environment: {expected_venv}\n"
            f"Active environment:   {active_venv}"
        )

    return f"Active project .venv verified ({sys.version.split()[0]})."


def _validate_pinned_versions() -> str:
    """Ensure installed packages match exact versions in requirements files."""
    pinned_versions: dict[str, tuple[str, str]] = {}

    for requirements_file in REQUIREMENTS_FILES:
        if not requirements_file.is_file():
            raise FileNotFoundError(
                f"Required dependency file is missing: {requirements_file}"
            )

        for raw_line in requirements_file.read_text(
            encoding="utf-8"
        ).splitlines():
            line = raw_line.split("#", 1)[0].strip()

            if not line or line.startswith("-"):
                continue

            match = re.match(
                r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*"
                r"([A-Za-z0-9][A-Za-z0-9.!+_-]*)$",
                line,
            )

            if match is None:
                continue

            package_name, expected_version = match.groups()
            normalized_name = _normalize_package_name(package_name)
            pinned_versions[normalized_name] = (
                package_name,
                expected_version,
            )

    if not pinned_versions:
        raise RuntimeError(
            "No exact package versions were found in the requirements files."
        )

    mismatches: list[str] = []

    for normalized_name, (package_name, expected_version) in sorted(
        pinned_versions.items()
    ):
        try:
            installed_version = importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            installed_version = "not installed"

        if installed_version != expected_version:
            mismatches.append(
                f"  {package_name}: expected {expected_version}, "
                f"found {installed_version}"
            )

    if mismatches:
        details = "\n".join(mismatches)
        raise RuntimeError(
            "Installed package versions do not match the pinned requirements:\n"
            f"{details}\n\n"
            "Activate this project's .venv and install the pinned dependencies:\n"
            "  python -m pip install -r requirements-dev.txt\n"
            "Then rerun python prepare_review.py."
        )

    return "Installed package versions match the pinned requirements."


def _run_check(label: str, command: list[str]) -> str:
    """Run a validation command and stop on failure."""
    print(f"\n--- {label} ---")

    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    output = result.stdout.strip()

    if output:
        print(output)

    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit code {result.returncode}. "
            "No new release ZIP was created. Fix the reported failure first."
        )

    return output or "Completed without reported errors."


def _sha256(path: Path) -> str:
    """Return the SHA-256 fingerprint of a source file."""
    digest = hashlib.sha256()

    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def _read_report_metrics(state: str, commodity: str) -> dict[str, str]:
    """Read key metrics from a generated analysis report."""
    state_slug = "_".join(state.lower().split())
    commodity_slug = "_".join(commodity.lower().split())

    path = (
        ROOT
        / "output"
        / f"{state_slug}_{commodity_slug}_price_alert_report.md"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Expected report was not generated: {path}"
        )

    expected_outputs = [
        ROOT / "output" / f"{state_slug}_relative_dispersion.png",
        ROOT / "output" / f"{state_slug}_{commodity_slug}_price_alerts.png",
    ]

    missing_outputs = [
        str(item) for item in expected_outputs if not item.is_file()
    ]

    if missing_outputs:
        raise FileNotFoundError(
            "Expected chart output(s) were not generated: "
            + ", ".join(missing_outputs)
        )

    text = path.read_text(encoding="utf-8")

    patterns = {
        "matched_rows": (
            r"Matched rows across the supported commodity basket:"
            r"\*\*\s*([\d,]+)"
        ),
        "coverage": (
            r"Selected commodity retail-key match coverage:"
            r"\*\*\s*([\d.]+%)"
        ),
        "alert_days": r"Alert days:\*\*\s*([\d,]+)",
        "groups": r"Grouped alert periods:\*\*\s*([\d,]+)",
        "negative_spreads": (
            r"Negative spread review flags "
            r"\(spread below -₹0\.000001\):\*\*\s*([\d,]+)"
        ),
        "outlier_associated_alerts": (
            r"Alerts associated with the isolated-outlier heuristic:"
            r"\*\*\s*([\d,]+)"
        ),
    }

    values: dict[str, str] = {}

    for key, pattern in patterns.items():
        match = re.search(pattern, text)

        if match is None:
            raise ValueError(
                f"Could not extract '{key}' from {path}."
            )

        values[key] = match.group(1)

    return values


def _write_test_results(
    pip_check: str,
    compile_check: str,
    test_output: str,
) -> None:
    """Generate TEST_RESULTS.md from the current release checks and reports."""
    version_rows = [
        ("Python", sys.version.split()[0]),
        ("pandas", pd.__version__),
        ("NumPy", np.__version__),
        ("Matplotlib", matplotlib.__version__),
        ("pytest", importlib.metadata.version("pytest")),
    ]

    test_match = re.search(
        r"(\d+ passed(?:, [^\n]+)?(?: in [^\n]+)?)",
        test_output,
    )
    test_summary = (
        test_match.group(1)
        if test_match
        else test_output.splitlines()[-1]
    )

    run_rows = []

    for state, commodity in SAMPLE_RUNS:
        stats = _read_report_metrics(state, commodity)

        run_rows.append(
            f"| {state} | {commodity} | {stats['matched_rows']} "
            f"| {stats['coverage']} | {stats['alert_days']} "
            f"| {stats['groups']} | {stats['negative_spreads']} "
            f"| {stats['outlier_associated_alerts']} |"
        )

    first_report = (
        ROOT / "output" / "karnataka_tomato_price_alert_report.md"
    )
    first_report_text = (
        first_report.read_text(encoding="utf-8")
        if first_report.exists()
        else ""
    )

    source_hash_rows = []

    for path in DATA_FILES:
        source_label = (
            "Retail"
            if "daily-retail-prices" in path.name
            else "Wholesale"
        )

        row_match = re.search(
            rf"\| {source_label} \| ([\d,]+) \|",
            first_report_text,
        )
        source_rows = (
            row_match.group(1) if row_match else "not recorded"
        )

        source_hash_rows.append(
            f"| `{path.name}` | {source_rows} | `{_sha256(path)}` |"
        )

    report = [
        "# Project Validation Results",
        "",
        (
            "This file is generated by `python prepare_review.py`. "
            "It records the checks and sample outputs from the current "
            "local code and source CSV files."
        ),
        "",
        "## Environment",
        "",
        "| Component | Version |",
        "|---|---|",
        *[f"| {name} | {version} |" for name, version in version_rows],
        "",
        "## Source file fingerprints",
        "",
        (
            "SHA-256 identifies the exact CSV versions used for "
            "the recorded local runs."
        ),
        "",
        "| Source file | Rows read | SHA-256 |",
        "|---|---:|---|",
        *source_hash_rows,
        "",
        "## Automated checks",
        "",
        f"- **Dependency check:** {pip_check}",
        f"- **Python compilation:** {compile_check}",
        (
            f"- **Test command:** `python -m pytest -q` — "
            f"**{test_summary}**"
        ),
        (
            "- **Test scope:** synthetic unit tests and temporary CSV files; "
            "these do not prove that every possible real-world input is valid."
        ),
        "",
        "## End-to-end sample runs",
        "",
        (
            "All four sample analyses were executed against the local source "
            "CSVs using defaults: absolute log-change Z-score threshold 2.5, "
            "minimum conventional absolute seven-day percentage change 10%, "
            "a baseline spanning up to 30 prior same-weekday weekly "
            "observations (minimum five valid), and alert grouping gap of "
            "3 calendar days. Alerts are detected from retail observations "
            "before wholesale matching."
        ),
        "",
        (
            "| State | Commodity | Matched basket rows | "
            "Selected commodity retail-key match coverage | Alert days | "
            "Grouped alert periods | Negative spread review flags | "
            "Outlier-associated alert days |"
        ),
        "|---|---|---:|---:|---:|---:|---:|---:|",
        *run_rows,
        "",
        (
            "Alert groups are analytical clusters, not verified independent "
            "market events. Negative spreads and alerts associated with "
            "isolated observations are review signals, not automatic proof "
            "of errors. Coverage in this table is for the selected commodity; "
            "basket-wide coverage is reported separately in each detailed report."
        ),
        "",
        "## Data validation notes",
        "",
        (
            "The loader records invalid-date, blank-price, malformed-price, "
            "non-finite-price, non-positive-price, and missing-key counts. "
            "It excludes invalid rows in memory without modifying the source "
            "CSVs. The reports include source row-retention counts."
        ),
        "",
        "## Mutation testing status",
        "",
        (
            "Mutation trials are not executed by `prepare_review.py` and are "
            "not represented as part of this run. The regular test suite is "
            "rerun on each release check. Previously performed mutation "
            "trials are historical evidence, not part of this automated run."
        ),
        "",
        "## Limits of this validation",
        "",
        (
            "Passing tests, successful sample runs, compilation, and "
            "dependency checks do not guarantee the absence of all bugs. "
            "Unit mappings remain source-based assumptions, and unusual "
            "numeric observations must be investigated with source context "
            "rather than removed automatically."
        ),
        "",
        (
            "This report was generated by running `prepare_review.py` inside "
            "the project's `.venv`. The script verifies that the active "
            "environment is the project's `.venv` and that installed "
            "packages match the exact versions pinned in the requirements "
            "files. Re-run the checks whenever the code, dependencies, "
            "methodology, source data, or parameters change."
        ),
        "",
    ]

    (ROOT / "TEST_RESULTS.md").write_text(
        "\n".join(report),
        encoding="utf-8",
    )


def main() -> None:
    os.chdir(ROOT)

    environment_check = _validate_release_environment()
    print(f"--- Release environment ---\n{environment_check}")

    pinned_check = _validate_pinned_versions()
    print(pinned_check)

    missing = [
        str(path) for path in DATA_FILES if not path.is_file()
    ]

    if missing:
        raise FileNotFoundError(
            "Required source data file(s) are missing. "
            "Put both CSVs in data/ before running this release check:\n"
            + "\n".join(missing)
            + "\nNo output cleanup or package generation was performed."
        )

    pip_check = _run_check(
        "Dependency compatibility",
        [sys.executable, "-m", "pip", "check"],
    )
    pip_check = f"{pip_check} {pinned_check}"

    compile_check = _run_check(
        "Python syntax compilation",
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "core",
            "main.py",
            "tests",
            "refresh_sample_outputs.py",
            "build_review_package.py",
            "prepare_review.py",
        ],
    )

    test_output = _run_check(
        "Automated test suite",
        [sys.executable, "-m", "pytest", "-q"],
    )

    # Refresh full-data outputs only after non-destructive checks pass.
    print("\n--- Full-data sample runs ---")
    refresh_sample_outputs()

    _write_test_results(
        pip_check,
        compile_check,
        test_output,
    )

    print("\n--- Build final release ZIP ---")
    build_review_package()

    print(
        "\nRelease preparation completed. Review TEST_RESULTS.md "
        "and the generated output reports before publishing the final ZIP."
    )


if __name__ == "__main__":
    main()