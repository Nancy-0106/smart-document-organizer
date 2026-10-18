import csv
import io
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import streamlit as st

from organizer import scan_directory, extract_text
from ai_classifier import classify_document
from duplicate_detector import find_duplicates


# =========================================================
# CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Smart Document Organizer",
    page_icon="📂",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "organization_actions.json"
DEFAULT_TEST_FOLDER = r"C:\Users\AUGUSTIN\Downloads\Organizer_Test"

CATEGORIES = [
    "Academics",
    "Finance",
    "Work",
    "Media",
    "Personal",
    "Software & Code",
    "Other",
]

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".csv",
    ".jpg", ".jpeg", ".png", ".json", ".py",
}


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def safe_filename(name):
    """Remove directory components and unsafe filename characters."""
    name = Path(str(name)).name
    name = "".join(
        ch for ch in name
        if ch.isalnum() or ch in " ._-()"
    )
    name = name.strip(" .")[:180]
    return name or "organized_file"


def preserve_extension(suggested_name, original_extension):
    """Use the suggested base name and preserve the real extension."""
    safe_name = safe_filename(suggested_name)
    stem = Path(safe_name).stem.strip(" .") or "organized_file"
    extension = original_extension.lower()
    return safe_filename(stem + extension)


def load_actions():
    """Load the organization action log."""
    if not LOG_FILE.exists():
        return []

    try:
        data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_actions(actions):
    """Save the organization action log."""
    LOG_FILE.write_text(
        json.dumps(actions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def classify_text(text):
    """Classify extracted text using the existing AI module."""
    result = classify_document(text or "")

    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            result = {"reason": result}

    if not isinstance(result, dict):
        result = {}

    category = str(result.get("category", "Other"))
    if category not in CATEGORIES:
        category = "Other"

    filename = safe_filename(
        result.get("suggested_filename", "organized_file")
    )

    return {
        "category": category,
        "filename": filename,
        "reason": str(
            result.get("reason", "Classification completed.")
        ),
    }


def unique_destination(destination):
    """Find an unused destination without overwriting a file."""
    destination = Path(destination)

    if not destination.exists():
        return destination

    counter = 1

    while True:
        candidate = destination.with_name(
            f"{destination.stem}_{counter}{destination.suffix}"
        )

        if not candidate.exists():
            return candidate

        counter += 1


def build_plan(root):
    """Create a proposed organization plan without moving files."""
    root = Path(root).resolve()
    plan = []

    files = sorted(
        path for path in root.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and path.name != LOG_FILE.name
    )

    for source in files:
        try:
            text = extract_text(str(source)) or ""
            result = classify_text(text)

            filename = preserve_extension(
                result["filename"],
                source.suffix,
            )

            plan.append({
                "source": str(source.resolve()),
                "category": result["category"],
                "filename": filename,
                "reason": result["reason"],
            })

        except Exception as error:
            plan.append({
                "source": str(source.resolve()),
                "category": "Other",
                "filename": source.name,
                "reason": f"Classification error: {error}",
            })

    return plan


def execute_plan(root, plan):
    """Move approved files, keeping moves inside the selected folder."""
    root = Path(root).resolve()
    actions = load_actions()
    completed = []
    errors = []

    for item in plan:
        source = Path(item["source"]).resolve()

        try:
            if not source.is_file():
                raise FileNotFoundError(
                    "Source file no longer exists."
                )

            if not source.is_relative_to(root):
                raise ValueError(
                    "Source is outside the selected folder."
                )

            category = item["category"]
            if category not in CATEGORIES:
                raise ValueError("Invalid category.")

            destination_folder = (root / category).resolve()

            if not destination_folder.is_relative_to(root):
                raise ValueError("Invalid destination folder.")

            destination_folder.mkdir(
                parents=True,
                exist_ok=True,
            )

            filename = preserve_extension(
                item["filename"],
                source.suffix,
            )

            destination = unique_destination(
                destination_folder / filename
            ).resolve()

            if not destination.is_relative_to(root):
                raise ValueError(
                    "Destination is outside the selected folder."
                )

            if source == destination:
                raise ValueError(
                    "Source and destination are identical."
                )

            shutil.move(str(source), str(destination))

            entry = {
                "timestamp": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "source": str(source),
                "destination": str(destination),
                "undone": False,
            }

            actions.append(entry)
            completed.append(entry)

        except Exception as error:
            errors.append(f"{source}: {error}")

    save_actions(actions)
    return completed, errors


def undo_move(index):
    """Undo a move without overwriting the original path."""
    actions = load_actions()

    if index < 0 or index >= len(actions):
        return False, "Invalid action selected."

    entry = actions[index]

    if entry.get("undone"):
        return False, "This move has already been undone."

    source = Path(entry["source"]).resolve()
    destination = Path(entry["destination"]).resolve()

    try:
        if not destination.is_file():
            return False, "The organized file could not be found."

        if source.exists():
            return False, (
                "The original path already exists. Undo stopped "
                "to avoid overwriting it."
            )

        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(destination), str(source))

        entry["undone"] = True
        entry["undone_at"] = datetime.now().isoformat(
            timespec="seconds"
        )

        save_actions(actions)
        return True, f"File restored to: {source}"

    except Exception as error:
        return False, f"Undo failed: {error}"


# =========================================================
# HEADER
# =========================================================

st.title("📂 Smart Document Organizer")

st.write(
    "Upload documents, classify them with AI, detect duplicates, "
    "and organize files with explicit approval."
)

st.warning(
    "Review proposed changes before approving. Files are not moved "
    "until you approve the plan. Test with copies first."
)


# =========================================================
# 1. DOCUMENT ANALYSIS
# =========================================================

st.header("📄 Document Analysis")

uploaded_files = st.file_uploader(
    "Upload documents for analysis",
    type=[
        "pdf", "docx", "xlsx", "pptx", "txt",
        "csv", "jpg", "jpeg", "png", "json", "py",
    ],
    accept_multiple_files=True,
)

for uploaded in uploaded_files or []:
    with st.expander(f"📄 {uploaded.name}"):

        if st.button(
            "Extract and classify",
            key=f"analyze_{uploaded.name}",
        ):
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = (
                        Path(temp_dir)
                        / safe_filename(uploaded.name)
                    )

                    temp_path.write_bytes(uploaded.getvalue())

                    with st.spinner("Analyzing document..."):
                        text = extract_text(str(temp_path)) or ""
                        result = classify_text(text)

                    # Preserve the uploaded file's real extension.
                    result["filename"] = preserve_extension(
                        result["filename"],
                        temp_path.suffix,
                    )

                    st.write("**Category:**", result["category"])
                    st.write(
                        "**Suggested filename:**",
                        result["filename"],
                    )
                    st.write("**Reason:**", result["reason"])

                    if text:
                        st.text_area(
                            "Extracted text preview",
                            value=text[:3000],
                            height=160,
                            key=f"text_{uploaded.name}",
                        )
                    else:
                        st.info(
                            "No text was extracted. Scanned files "
                            "may need OCR support."
                        )

            except Exception as error:
                st.error(f"Analysis failed: {error}")


# =========================================================
# 2. LOCAL FOLDER SCANNER
# =========================================================

st.header("🗂️ Local Folder Scanner")

st.info(
    "This scans folders on the computer running the app. When hosted "
    "online, it scans the server, not your personal computer."
)

scan_path = st.text_input(
    "Folder path to scan",
    value=DEFAULT_TEST_FOLDER,
    key="scan_path",
)

if st.button("Scan folder"):
    try:
        target = Path(scan_path).expanduser().resolve()

        if not target.is_dir():
            st.error("Folder not found. Check the path.")
        else:
            with st.spinner("Scanning folder..."):
                result = scan_directory(str(target))

            st.success("Folder scan completed.")

            if isinstance(result, list) and result:
                st.write(f"Items found: {len(result)}")
                st.dataframe(result, use_container_width=True)
            elif result:
                st.write(result)
            else:
                st.info("No files were found.")

    except Exception as error:
        st.error(f"Folder scan failed: {error}")


# =========================================================
# 3. DUPLICATE DETECTION
# =========================================================

st.header("🔎 Duplicate File Detection")

st.write("Find exact duplicates. This feature does not delete files.")

duplicate_path = st.text_input(
    "Folder to check for duplicates",
    value=DEFAULT_TEST_FOLDER,
    key="duplicate_path",
)

if st.button("Find exact duplicates"):
    try:
        target = Path(duplicate_path).expanduser().resolve()

        if not target.is_dir():
            st.error("Folder not found. Check the path.")
        else:
            with st.spinner("Checking for duplicates..."):
                result = find_duplicates(str(target))

            if isinstance(result, dict):
                groups = result.get("duplicate_groups", [])

                st.write(
                    "Files scanned:",
                    result.get("files_scanned", "Not reported"),
                )

                if result.get("errors"):
                    st.warning(
                        f"{len(result['errors'])} file(s) "
                        "could not be checked."
                    )
            else:
                groups = result

            if groups:
                st.success(
                    f"Found {len(groups)} duplicate group(s)."
                )
                st.json(groups)
            else:
                st.info("No duplicate groups were reported.")

    except Exception as error:
        st.error(f"Duplicate detection failed: {error}")


# =========================================================
# 4. ORGANIZATION PLANNER
# =========================================================

st.header("📋 Organization Planner")

st.write(
    "Preview proposed category folders and filenames before "
    "making any changes."
)

plan_path = st.text_input(
    "Test folder to organize",
    value=DEFAULT_TEST_FOLDER,
    key="plan_path",
)

st.caption(
    "Only supported files directly inside this folder are included. "
    "Use a folder containing copies of your documents."
)

if st.button("Create organization plan"):
    try:
        root = Path(plan_path).expanduser().resolve()

        if not root.is_dir():
            st.error("Folder not found. Check the path.")
        else:
            with st.spinner("Preparing organization plan..."):
                plan = build_plan(root)

            st.session_state["organization_plan"] = plan
            st.session_state["organization_root"] = str(root)

            if plan:
                st.success(
                    f"Prepared a plan for {len(plan)} file(s)."
                )
            else:
                st.info(
                    "No supported files were found directly "
                    "in this folder."
                )

    except Exception as error:
        st.error(f"Could not create the plan: {error}")


plan = st.session_state.get("organization_plan", [])

if plan:
    st.subheader("Proposed changes")

    preview_rows = [
        {
            "Original file": item["source"],
            "Category": item["category"],
            "Proposed filename": item["filename"],
            "Reason": item["reason"],
        }
        for item in plan
    ]

    st.dataframe(
        preview_rows,
        use_container_width=True,
        hide_index=True,
    )

    csv_buffer = io.StringIO()

    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=[
            "original_path",
            "category",
            "proposed_filename",
            "reason",
        ],
    )

    writer.writeheader()

    for item in plan:
        writer.writerow({
            "original_path": item["source"],
            "category": item["category"],
            "proposed_filename": item["filename"],
            "reason": item["reason"],
        })

    st.download_button(
        "Download organization plan (CSV)",
        data=csv_buffer.getvalue(),
        file_name="organization_plan.csv",
        mime="text/csv",
    )

    st.warning(
        "Approval moves the listed files into category subfolders "
        "inside the selected test folder. Existing files will not "
        "be overwritten."
    )

    approved = st.checkbox(
        "I reviewed the plan and confirm these are test copies.",
        key="approval_checkbox",
    )

    if st.button(
        "Approve and organize files",
        type="primary",
    ):
        if not approved:
            st.error(
                "Tick the confirmation checkbox before approving."
            )
        else:
            completed, errors = execute_plan(
                st.session_state["organization_root"],
                plan,
            )

            st.session_state["organization_plan"] = []

            if completed:
                st.success(
                    f"Successfully moved {len(completed)} file(s)."
                )

            if errors:
                st.error("Some files could not be moved:")
                for error in errors:
                    st.write(f"- {error}")

            st.rerun()


# =========================================================
# 5. ACTION LOG AND UNDO
# =========================================================

st.header("↩️ Action Log and Undo")

actions = load_actions()

if not actions:
    st.info("No organization actions have been recorded yet.")

else:
    st.write(f"Recorded actions: {len(actions)}")

    for action in reversed(actions):
        with st.container(border=True):
            st.caption(
                action.get("timestamp", "Unknown time")
            )

            if action.get("undone"):
                st.success("Status: Undone")
            else:
                st.info("Status: Moved")

            st.markdown("**Original path**")
            st.code(action.get("source", ""), language=None)

            st.markdown("**New path**")
            st.code(action.get("destination", ""), language=None)

    available = [
        index
        for index, action in enumerate(actions)
        if not action.get("undone", False)
    ]

    if available:
        st.subheader("Undo a move")

        selected_index = st.selectbox(
            "Select an action",
            options=available,
            format_func=lambda index: (
                f"{actions[index].get('timestamp', '')} — "
                f"{Path(actions[index]['destination']).name}"
            ),
        )

        st.warning(
            "Undo restores the file to its original path only if that "
            "path is free. It will not overwrite an existing file."
        )

        if st.button("Undo selected move"):
            success, message = undo_move(selected_index)

            if success:
                st.success(message)
            else:
                st.error(message)

            st.rerun()

    else:
        st.info("There are no moves available to undo.")


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Smart Document Organizer | Preview, explicit approval, "
    "action log, and Undo. No automatic deletion."
)