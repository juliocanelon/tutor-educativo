"""Utilities for managing book storage and text extraction."""
from __future__ import annotations

import os
from typing import Dict

import PyPDF2
from flask import session

ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename: str) -> bool:
    """Return True when the filename has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def store_book_metadata(path: str, title: str) -> None:
    """Persist the uploaded book metadata in the session without storing the content."""
    session["book_path"] = path
    session["book_title"] = title


def get_book_metadata() -> Dict[str, str]:
    """Return the metadata of the uploaded book, ensuring the file exists."""
    book_path = session.get("book_path")
    book_title = session.get("book_title", "Libro sin título")

    if not book_path:
        raise FileNotFoundError("No hay libro cargado.")
    if not os.path.exists(book_path):
        raise FileNotFoundError("El archivo del libro no existe en el servidor.")

    return {"path": book_path, "title": book_title}


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF using PyPDF2 while normalising empty pages."""
    text_parts = []
    try:
        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
    except Exception as exc:  # pragma: no cover - defensive branch
        raise Exception(f"Error al extraer texto del PDF: {exc}")

    return "\n".join(text_parts)


def load_book_text() -> str:
    """Load the text of the current book from disk."""
    metadata = get_book_metadata()
    return extract_text_from_pdf(metadata["path"])
