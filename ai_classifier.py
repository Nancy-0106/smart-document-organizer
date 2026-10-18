
import os
import json
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

# Load API credentials from the project folder's .env file
load_dotenv(Path(__file__).resolve().parent / ".env")

CATEGORIES = [
    "Academics",
    "Finance",
    "Work",
    "Media",
    "Personal",
    "Software & Code",
    "Other"
]


def classify_document(text, filename=""):
    """Suggest a category and a safe filename using Groq."""

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is missing. Check your project's .env file."
        )

    if not text or not text.strip():
        return {
            "category": "Other",
            "suggested_filename": filename,
            "reason": "No readable text was available."
        }

    client = Groq(api_key=api_key)

    prompt = f"""
You classify documents for a Smart Document Organizer.

Choose exactly one category from this list:
{", ".join(CATEGORIES)}

Suggest a clear filename while preserving the original file extension.
Do not invent details that are not present in the document.

Return only a JSON object with these keys:
category, suggested_filename, reason

Original filename: {filename}
Document text (may be incomplete):
{text[:6000]}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": "Classify documents carefully. Return valid JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.1
    )

    result_text = response.choices[0].message.content.strip()
    result_text = result_text.removeprefix("```json").removesuffix("```").strip()
    result = json.loads(result_text)

    if result.get("category") not in CATEGORIES:
        result["category"] = "Other"

    proposed_name = Path(
        str(result.get("suggested_filename", filename))
    ).name

    if not proposed_name:
        proposed_name = filename or "document"

    result["suggested_filename"] = proposed_name
    result["reason"] = str(result.get("reason", ""))

    return result
