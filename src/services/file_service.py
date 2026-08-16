"""Lightweight service for validating, storing, reading, and chunking educational files."""
import os
import re
import uuid
import aiofiles
import pymupdf
from fastapi import UploadFile
from helpers.config import get_settings
from models.enums import ResponseSignal


def get_project_directory(project_id: str) -> str:
    """Ensure and return the isolated directory path for a project."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    project_dir = os.path.join(base_dir, "assets", "files", project_id)
    os.makedirs(project_dir, exist_ok=True)
    return project_dir


def clean_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and special character issues."""
    cleaned = re.sub(r"[^\w.]", "", filename.strip())
    return cleaned.replace(" ", "_")


def validate_file(file: UploadFile) -> tuple[bool, str]:
    """Validate uploaded file type and size against configured limits."""
    settings = get_settings()
    
    if file.content_type not in settings.FILE_ALLOWED_TYPES:
        return False, f"{file.content_type}: {ResponseSignal.FILE_NOT_SUPPORTED.value}"

    if file.size and file.size > settings.FILE_MAX_SIZE * 1024 * 1024:
        return False, f"{file.size}: {ResponseSignal.FILE_SIZE_EXCEEDED.value}"

    return True, ResponseSignal.FILE_SUCCESSFULLY_VALIDATED.value


async def save_upload(file: UploadFile, project_id: str) -> tuple[str, str]:
    """Save an uploaded file asynchronously to project storage and return (file_path, file_id)."""
    settings = get_settings()
    project_dir = get_project_directory(project_id)
    file_id = f"{uuid.uuid4().hex[:12]}_{clean_filename(file.filename or 'document')}"
    file_path = os.path.join(project_dir, file_id)

    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(settings.FILE_DEFAULT_CHUNK_SIZE):
            await f.write(chunk)

    return file_path, file_id


def extract_text_from_file(file_path: str) -> str:
    """Extract raw text from PDF or text/markdown documents."""
    ext = os.path.splitext(file_path)[-1].lower()
    
    if ext == ".pdf":
        doc = pymupdf.open(file_path)
        pages_text = [page.get_text("text") for page in doc]
        return "\n\n".join(pages_text)
    
    # Text or JSON file
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def chunk_text(text: str, chunk_size: int = 1000, overlap_size: int = 200) -> list[dict]:
    """
    Split text into semantic chunks with sliding overlap to preserve context across boundaries.
    """
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunk_content = text[start:end]
        chunks.append({
            "page_content": chunk_content,
            "metadata": {"start_index": start, "end_index": min(end, text_len)},
        })
        if end >= text_len:
            break
        start += (chunk_size - overlap_size)

    return chunks
