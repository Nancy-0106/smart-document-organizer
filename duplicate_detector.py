
import hashlib
from pathlib import Path
from collections import defaultdict


def calculate_sha256(file_path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()

    with open(file_path, "rb") as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


def find_duplicates(folder_path):
    folder = Path(folder_path).expanduser()

    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")

    if not folder.is_dir():
        raise NotADirectoryError(f"Not a folder: {folder}")

    # Group files by size first.
    size_groups = defaultdict(list)
    errors = []
    files_scanned = 0

    for path in folder.rglob("*"):
        try:
            if path.is_file():
                size_groups[path.stat().st_size].append(path)
                files_scanned += 1
        except OSError as error:
            errors.append(f"{path}: {error}")

    # Hash only files that have another file of the same size.
    hash_groups = defaultdict(list)

    for same_size_files in size_groups.values():
        if len(same_size_files) < 2:
            continue

        for path in same_size_files:
            try:
                file_hash = calculate_sha256(path)
                hash_groups[file_hash].append(str(path.resolve()))
            except OSError as error:
                errors.append(f"{path}: {error}")

    duplicates = [
        paths for paths in hash_groups.values()
        if len(paths) > 1
    ]

    return {
        "duplicate_groups": duplicates,
        "files_scanned": files_scanned,
        "errors": errors
    }
