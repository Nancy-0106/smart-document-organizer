
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from organizer import scan_directory, extract_text
from ai_classifier import classify_document
from duplicate_detector import find_duplicates
from organization_planner import create_organization_plan


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Smart Document Organizer",
    page_icon="📂",
    layout="wide",
)

st.title("📂 Smart Document Organizer")
st.write(
    "Upload documents, extract text, classify documents with AI, "
    "detect duplicates, and prepare an organization plan."
)

st.info(
    "Safety: this version only previews and proposes changes. "
    "It does not automatically move, rename, or delete files."
)


# --------------------------------------------------
# FEATURE 1: UPLOAD, EXTRACT, AND CLASSIFY
# --------------------------------------------------

st.header("📄 Document Analysis")

uploaded_files = st.file_uploader(
    "Upload documents to analyze",
    type=[
        "pdf", "docx", "xlsx", "pptx", "txt", "csv",
        "jpg", "jpeg", "png", "json", "py",
    ],
    accept_multiple_files=True,
)

if uploaded_files:
    file_rows = [
        {
            "File name": file.name,
            "Type": Path(file.name).suffix.lower(),
            "Size (KB)": round(file.size / 1024, 2),
        }
        for file in uploaded_files
    ]

    st.success(f"{len(uploaded_files)} file(s) uploaded.")
    st.dataframe(pd.DataFrame(file_rows), use_container_width=True)

    selected_index = st.selectbox(
        "Choose a document",
        options=list(range(len(uploaded_files))),
        format_func=lambda i: uploaded_files[i].name,
        key="document_selector",
    )

    selected_file = uploaded_files[selected_index]
    selected_name = selected_file.name
    extension = Path(selected_name).suffix.lower()

    supported_formats = {
        ".pdf", ".docx", ".xlsx", ".pptx",
        ".txt", ".csv", ".json", ".py",
    }

    # Reset previous document state when a different file is selected.
    if st.session_state.get("current_document") != selected_name:
        st.session_state["current_document"] = selected_name
        st.session_state.pop("extracted_text", None)
        st.session_state.pop("extracted_name", None)
        st.session_state.pop("classification_result", None)
        st.session_state.pop("classification_name", None)

    if extension in supported_formats:
        if st.button("Extract text", key="extract_text_button"):
            temporary_path = None

            try:
                with tempfile.NamedTemporaryFile(
                    suffix=extension,
                    delete=False,
                ) as temporary_file:
                    temporary_file.write(selected_file.getvalue())
                    temporary_path = temporary_file.name

                with st.spinner("Extracting document text..."):
                    document_text = extract_text(temporary_path)

                st.session_state["extracted_text"] = document_text
                st.session_state["extracted_name"] = selected_name
                st.session_state.pop("classification_result", None)
                st.session_state.pop("classification_name", None)

            except Exception as error:
                st.error(f"Text extraction failed: {error}")

            finally:
                if temporary_path and os.path.exists(temporary_path):
                    os.remove(temporary_path)

    else:
        st.warning(
            "Text extraction for this file type is not available yet."
        )

    document_text = st.session_state.get("extracted_text")

    if (
        st.session_state.get("extracted_name") == selected_name
        and document_text is not None
    ):
        st.success("Text extraction completed.")

        st.text_area(
            "Extracted document content",
            value=document_text[:15000],
            height=250,
            key=f"text_preview_{selected_index}",
        )

        if len(document_text) > 15000:
            st.caption("Preview limited to 15,000 characters.")

        if st.button("Classify document with AI", key="classify_button"):
            try:
                with st.spinner("AI is analyzing the document..."):
                    result = classify_document(
                        text=document_text,
                        filename=selected_name,
                    )

                st.session_state["classification_result"] = result
                st.session_state["classification_name"] = selected_name

            except Exception as error:
                st.error(
                    "AI classification failed. Check your Groq API key "
                    "and model access. Details: " + str(error)
                )

    classification = st.session_state.get("classification_result")

    if (
        st.session_state.get("classification_name") == selected_name
        and classification
    ):
        st.subheader("🤖 AI Classification Result")
        st.write(f"**Category:** {classification['category']}")
        st.write(
            f"**Suggested filename:** "
            f"{classification['suggested_filename']}"
        )
        st.write(f"**Reason:** {classification['reason']}")

        st.caption(
            "AI classification sends document text to Groq. "
            "Use non-sensitive files while testing."
        )


# --------------------------------------------------
# FEATURE 2: LOCAL FOLDER SCANNER
# --------------------------------------------------

st.divider()
st.header("🗂️ Local Folder Scanner")

st.write(
    "Scan a folder on the computer running this app. "
    "When hosted online, this refers to the server, not the visitor's PC."
)

folder_path = st.text_input(
    "Folder path to scan",
    placeholder=r"C:\Users\YourName\Downloads",
    key="scan_folder_path",
)

if st.button("Scan folder", key="scan_folder_button"):
    if not folder_path.strip():
        st.warning("Please enter a folder path.")
    else:
        try:
            with st.spinner("Scanning folder..."):
                scanned_files = scan_directory(
                    folder_path.strip().strip('"')
                )

            st.success(f"Found {len(scanned_files)} file(s).")

            if scanned_files:
                st.dataframe(
                    pd.DataFrame(scanned_files),
                    use_container_width=True,
                )
            else:
                st.info("No files were found.")

        except (OSError, ValueError) as error:
            st.error(f"Folder scan failed: {error}")


# --------------------------------------------------
# FEATURE 3: DUPLICATE DETECTION
# --------------------------------------------------

st.divider()
st.header("🔎 Duplicate File Detection")

st.write(
    "Find exact duplicates using SHA-256 hashes. "
    "No files are deleted."
)

duplicate_folder = st.text_input(
    "Folder path for duplicate scanning",
    placeholder=r"C:\Users\YourName\Downloads",
    key="duplicate_folder_path",
)

if st.button("Find duplicate files", key="find_duplicates_button"):
    if not duplicate_folder.strip():
        st.warning("Please enter a folder path.")
    else:
        try:
            with st.spinner("Scanning and comparing file contents..."):
                result = find_duplicates(
                    duplicate_folder.strip().strip('"')
                )

            groups = result["duplicate_groups"]

            st.metric("Readable files scanned", result["files_scanned"])
            st.metric("Duplicate groups found", len(groups))

            # Keep the full result in session state for display and export.
            st.session_state["duplicate_result"] = result

        except (OSError, ValueError) as error:
            st.error(f"Duplicate scan failed: {error}")

result = st.session_state.get("duplicate_result")

if result:
    groups = result["duplicate_groups"]

    if groups:
        duplicate_rows = []

        for group_number, paths in enumerate(groups, start=1):
            for file_path in paths:
                duplicate_rows.append({
                    "Group": group_number,
                    "File path": file_path,
                    "Files in group": len(paths),
                })

        duplicate_df = pd.DataFrame(duplicate_rows)

        st.subheader("Duplicate report")
        st.dataframe(duplicate_df, use_container_width=True)

        st.download_button(
            "Download duplicate report (CSV)",
            data=duplicate_df.to_csv(index=False).encode("utf-8"),
            file_name="duplicate_report.csv",
            mime="text/csv",
        )

    else:
        st.info("No exact duplicates were found.")

    if result["errors"]:
        st.warning(
            f"{len(result['errors'])} file(s) could not be read."
        )
        with st.expander("View scan errors"):
            for error in result["errors"]:
                st.write(error)


# --------------------------------------------------
# FEATURE 4: ORGANIZATION PLANNER
# --------------------------------------------------

st.divider()
st.header("📋 Organization Planner")

st.write(
    "Create a proposed destination folder and filename. "
    "This section does not change the original file."
)

planner_path = st.text_input(
    "Original file path",
    placeholder=r"C:\Users\YourName\Downloads\example.pdf",
    key="planner_original_path",
)

categories = [
    "Academics",
    "Finance",
    "Work",
    "Media",
    "Personal",
    "Software & Code",
    "Other",
]

planner_category = st.selectbox(
    "Category",
    categories,
    key="planner_category",
)

planner_filename = st.text_input(
    "Proposed filename",
    placeholder="Enter a new filename or leave blank to keep the name",
    key="planner_suggested_filename",
)

if st.button("Generate organization plan", key="generate_plan_button"):
    cleaned_path = planner_path.strip().strip('"')

    if not cleaned_path:
        st.warning("Enter the original file path.")
    else:
        original_path = Path(cleaned_path).expanduser()

        if not original_path.is_file():
            st.error(
                "The original file was not found. "
                "Enter a valid path on the computer running this app."
            )
        else:
            suggested_filename = (
                planner_filename.strip() or original_path.name
            )

            try:
                plan = create_organization_plan([
                    {
                        "original_path": str(original_path),
                        "category": planner_category,
                        "suggested_filename": suggested_filename,
                    }
                ])

                st.session_state["organization_plan"] = plan

            except (OSError, ValueError, KeyError) as error:
                st.error(f"Could not create plan: {error}")

plan = st.session_state.get("organization_plan")

if plan:
    st.subheader("Proposed changes")
    plan_df = pd.DataFrame(plan)

    st.dataframe(plan_df, use_container_width=True)

    st.download_button(
        "Download organization plan (CSV)",
        data=plan_df.to_csv(index=False).encode("utf-8"),
        file_name="organization_plan.csv",
        mime="text/csv",
    )

    st.info(
        "Review the proposed destination before taking action. "
        "No files have been moved or renamed."
    )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()
st.caption(
    "Smart Document Organizer | Preview and planning only. "
    "No automatic file changes are performed."
)
