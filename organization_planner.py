
import re
from pathlib import Path


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

CATEGORIES = [
    "Academics",
    "Finance",
    "Work",
    "Media",
    "Personal",
    "Software & Code",
    "Other",
]


# ---------------------------------------------------------
# FILENAME CLEANING
# ---------------------------------------------------------

def clean_filename(filename):
    """
    Clean a filename while preserving its extension.
    This function does not rename the original file.
    """
    filename = Path(str(filename)).name

    stem = Path(filename).stem
    extension = Path(filename).suffix

    # Replace characters that are unsafe in Windows filenames.
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem)
    stem = re.sub(r"\s+", "_", stem)
    stem = re.sub(r"_+", "_", stem)
    stem = stem.strip(" ._")

    if not stem:
        stem = "organized_file"

    # Avoid Windows reserved filenames.
    reserved_names = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }

    if stem.upper() in reserved_names:
        stem = f"_{stem}"

    return f"{stem[:150]}{extension}"


# ---------------------------------------------------------
# CATEGORY VALIDATION
# ---------------------------------------------------------

def validate_category(category):
    """
    Return a valid category.
    Unknown or missing categories become Other.
    """
    if not category:
        return "Other"

    category = str(category).strip()

    for valid_category in CATEGORIES:
        if category.casefold() == valid_category.casefold():
            return valid_category

    return "Other"


# ---------------------------------------------------------
# DOCUMENT INFORMATION HELPERS
# ---------------------------------------------------------

def get_document_value(document, *keys, default=None):
    """
    Read a value from a dictionary or an object attribute.
    Supports common field names used by document scanners.
    """
    if isinstance(document, dict):
        for key in keys:
            if document.get(key) is not None:
                return document[key]

    else:
        for key in keys:
            value = getattr(document, key, None)
            if value is not None:
                return value

    return default


def get_original_path(document):
    """
    Obtain the original path from a document record.
    """
    value = get_document_value(
        document,
        "original_path",
        "full_path",
        "file_path",
        "path",
        "source",
        default=None,
    )

    if value:
        return Path(str(value))

    filename = get_document_value(
        document,
        "original_filename",
        "filename",
        "name",
        default=None,
    )

    if filename:
        return Path(str(filename))

    return None


# ---------------------------------------------------------
# ORGANIZATION PLAN
# ---------------------------------------------------------

def create_organization_plan(documents):
    """
    Create a proposed organization plan.

    Accepted document fields may include:
        original_path / full_path / file_path / path
        original_filename / filename / name
        category
        suggested_filename / proposed_filename

    Returns a list of dictionaries containing:
        original_path
        original_filename
        category
        proposed_folder
        proposed_filename
        proposed_destination
        status

    IMPORTANT:
    This function only prepares a plan.
    It does not create folders, move files, rename files,
    or delete files.
    """
    organization_plan = []

    if not documents:
        return organization_plan

    for document in documents:
        original_path = get_original_path(document)

        if original_path is None:
            continue

        original_filename = get_document_value(
            document,
            "original_filename",
            "filename",
            "name",
            default=original_path.name,
        )

        category = validate_category(
            get_document_value(
                document,
                "category",
                "predicted_category",
                "suggested_category",
                default="Other",
            )
        )

        proposed_filename = get_document_value(
            document,
            "suggested_filename",
            "proposed_filename",
            "recommended_filename",
            default=original_filename,
        )

        proposed_filename = clean_filename(proposed_filename)

        # Propose a category subfolder beside the original file.
        # No folder is actually created here.
        proposed_folder = original_path.parent / category

        proposed_destination = (
            proposed_folder / proposed_filename
        )

        organization_plan.append({
            "original_path": str(original_path),
            "original_filename": str(original_filename),
            "category": category,
            "proposed_folder": str(proposed_folder),
            "proposed_filename": proposed_filename,
            "proposed_destination": str(proposed_destination),
            "status": "Pending approval",
        })

    return organization_plan


# ---------------------------------------------------------
# PLAN SUMMARY
# ---------------------------------------------------------

def get_plan_summary(organization_plan):
    """
    Return simple counts for a proposed organization plan.
    """
    summary = {
        "total_files": len(organization_plan),
        "categories": {},
        "status": "Preview only",
    }

    for item in organization_plan:
        category = item.get("category", "Other")
        summary["categories"][category] = (
            summary["categories"].get(category, 0) + 1
        )

    return summary
