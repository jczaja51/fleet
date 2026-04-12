from __future__ import annotations

import shutil
import unicodedata
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
    "delete_vehicle_storage_dir",
    "move_vehicle_storage_dir",
    "update_vehicle_file_references",
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


def _normalize_registration(registration: str) -> str:
    value = (registration or "").strip().upper()
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = secure_filename(value.replace(" ", "_"))
    if not value:
        raise StorageError("Nieprawidłowy numer rejestracyjny.")
    return value


def get_vehicle_storage_dir(registration: str) -> Path:
    reg_dir = _normalize_registration(registration)
    return _static_root() / "uploads" / "vehicles" / reg_dir


def _ensure_vehicle_subdir(registration: str, subdir: str) -> Path:
    directory = get_vehicle_storage_dir(registration) / subdir
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_document_file(uploaded_file: FileStorage, registration: str) -> tuple[str, str]:
    if not uploaded_file or not uploaded_file.filename:
        raise StorageError("Nie wybrano pliku dokumentu.")

    suffix = _safe_suffix(uploaded_file.filename, DOCUMENT_ALLOWED_EXTENSIONS)
    original_name = secure_filename(uploaded_file.filename)

    upload_dir = _ensure_vehicle_subdir(registration, "documents")

    stored_name = f"document_{uuid4().hex}{suffix}"
    destination = upload_dir / stored_name
    uploaded_file.save(destination)

    return _relative_to_static(destination), original_name


def save_vehicle_image(uploaded_file: FileStorage, registration: str) -> str:
    if not uploaded_file or not uploaded_file.filename:
        raise StorageError("Nie wybrano zdjęcia pojazdu.")

    suffix = _safe_suffix(uploaded_file.filename, IMAGE_ALLOWED_EXTENSIONS)

    upload_dir = _ensure_vehicle_subdir(registration, "image")

    stored_name = f"image_{uuid4().hex}{suffix}"
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


def delete_vehicle_storage_dir(registration: str | None) -> None:
    if not registration:
        return

    vehicle_dir = get_vehicle_storage_dir(registration)
    if vehicle_dir.exists() and vehicle_dir.is_dir():
        shutil.rmtree(vehicle_dir, ignore_errors=True)
        _cleanup_empty_upload_dirs(vehicle_dir.parent)


def move_vehicle_storage_dir(old_registration: str, new_registration: str) -> None:
    old_dir = get_vehicle_storage_dir(old_registration)
    new_dir = get_vehicle_storage_dir(new_registration)

    if old_dir == new_dir or not old_dir.exists():
        return

    new_dir.parent.mkdir(parents=True, exist_ok=True)

    if new_dir.exists():
        raise StorageError(
            "Folder dla nowego numeru rejestracyjnego już istnieje. Zmień numer albo usuń konfliktujące pliki."
        )

    shutil.move(str(old_dir), str(new_dir))


def update_vehicle_file_references(vehicle, old_registration: str, new_registration: str) -> None:
    old_prefix = get_vehicle_storage_dir(old_registration)
    new_prefix = get_vehicle_storage_dir(new_registration)

    old_prefix_relative = _relative_to_static(old_prefix)
    new_prefix_relative = _relative_to_static(new_prefix)

    if vehicle.image:
        vehicle.image = vehicle.image.replace(old_prefix_relative, new_prefix_relative, 1)

    for document in vehicle.documents:
        if document.file_path:
            document.file_path = document.file_path.replace(old_prefix_relative, new_prefix_relative, 1)


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