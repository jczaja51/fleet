from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

DOCUMENT_ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp"}
IMAGE_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

__all__ = [
    "StorageError",
    "save_document_file",
    "save_vehicle_image",
    "delete_relative_static_file",
]


class StorageError(ValueError):
    pass


def _static_root() -> Path:
    return Path(current_app.static_folder).resolve()


def _relative_to_static(path: Path) -> str:
    return path.resolve().relative_to(_static_root()).as_posix()


def _safe_suffix(filename: str, allowed_extensions: set[str]) -> str:
    cleaned_name = secure_filename(filename or "")
    if "." not in cleaned_name:
        raise StorageError("Plik musi mieć prawidłowe rozszerzenie.")

    suffix = Path(cleaned_name).suffix.lower().lstrip(".")
    if suffix not in allowed_extensions:
        raise StorageError("Niedozwolony format pliku.")

    return f".{suffix}"


def save_document_file(uploaded_file: FileStorage, vehicle_id: int) -> tuple[str, str]:
    if not uploaded_file or not uploaded_file.filename:
        raise StorageError("Nie wybrano pliku dokumentu.")

    suffix = _safe_suffix(uploaded_file.filename, DOCUMENT_ALLOWED_EXTENSIONS)
    original_name = secure_filename(uploaded_file.filename)

    upload_dir = _static_root() / "uploads" / "documents" / f"vehicle_{vehicle_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4().hex}{suffix}"
    destination = upload_dir / stored_name
    uploaded_file.save(destination)

    return _relative_to_static(destination), original_name


def save_vehicle_image(uploaded_file: FileStorage) -> str:
    if not uploaded_file or not uploaded_file.filename:
        raise StorageError("Nie wybrano zdjęcia pojazdu.")

    suffix = _safe_suffix(uploaded_file.filename, IMAGE_ALLOWED_EXTENSIONS)

    upload_dir = _static_root() / "uploads" / "vehicles"
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4().hex}{suffix}"
    destination = upload_dir / stored_name
    uploaded_file.save(destination)

    return _relative_to_static(destination)


def delete_relative_static_file(relative_path: str | None) -> None:
    if not relative_path:
        return

    static_root = _static_root()
    candidate = (static_root / relative_path).resolve()

    if static_root not in candidate.parents and candidate != static_root:
        return

    if candidate.exists() and candidate.is_file():
        candidate.unlink()
        _cleanup_empty_upload_dirs(candidate.parent)


def _cleanup_empty_upload_dirs(directory: Path) -> None:
    static_root = _static_root()
    uploads_root = static_root / "uploads"

    current = directory.resolve()
    while current != uploads_root and uploads_root in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent