"""Create an independent-review ZIP without raw data or local environments."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


EXCLUDED_DIRS = {".venv", "venv", "env", ".git", "__pycache__", ".pytest_cache"}
EXCLUDED_FILES = {
    "daily-retail-prices-of-essential-commodities.csv",
    "state-level-daily-wholesale-price.csv",
    "commodity-margin-engine-review.zip",
}


def main() -> None:
    root = Path.cwd()
    archive = root / "commodity-margin-engine-final-release.zip"
    included = []

    with ZipFile(archive, "w", ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if any(
                part in EXCLUDED_DIRS
                or part.startswith(".venv")
                or part.startswith("venv-")
                for part in relative.parts
            ):
                continue
            is_raw_data_csv = relative.parts and relative.parts[0] == "data" and path.suffix.lower() == ".csv"
            if path.name in EXCLUDED_FILES or path.suffix.lower() == ".zip" or is_raw_data_csv:
                continue
            zf.write(path, relative.as_posix())
            included.append(relative.as_posix())

    print(f"Created: {archive}")
    print(f"Files included: {len(included)}")
    print("Raw CSVs, virtual environments, Git metadata, and old ZIPs excluded.")


if __name__ == "__main__":
    main()
