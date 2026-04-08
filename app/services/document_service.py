from __future__ import annotations

from datetime import datetime

from app import db
from app.constants import ALLOWED_DOCUMENT_TYPES, DOCUMENT_TYPE_LABELS
from app.models import Vehicle, VehicleDocument
from app.services.storage_service import (
    StorageError,
    delete_relative_static_file,
    save_document_file,
)

__all__ = [
    "DOCUMENT_TYPE_LABELS",
    "DocumentValidationError",
    "parse_optional_date",
    "normalize_document_name",
    "normalize_document_type",
    "normalize_notes",
    "create_document_for_vehicle",
    "update_document",
    "delete_document",
]


class DocumentValidationError(ValueError):
    pass


def parse_optional_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise DocumentValidationError("Nieprawidłowy format daty.") from exc


def normalize_document_name(value: str | None) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise DocumentValidationError("Nazwa dokumentu jest wymagana.")
    if len(cleaned) > 255:
        raise DocumentValidationError("Nazwa dokumentu jest zbyt długa.")
    return cleaned


def normalize_document_type(value: str | None = None) -> str:
    return "other"


def normalize_notes(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned[:2000] if cleaned else None


def create_document_for_vehicle(vehicle: Vehicle, form, uploaded_file) -> VehicleDocument:
    file_path = None
    original_filename = None

    if uploaded_file and uploaded_file.filename:
        file_path, original_filename = save_document_file(uploaded_file, vehicle.id)

    document = VehicleDocument(
        name=normalize_document_name(form.get("name")),
        document_type=normalize_document_type(),
        expiry_date=parse_optional_date(form.get("expiry_date")),
        notes=normalize_notes(form.get("notes")),
        file_path=file_path,
        original_filename=original_filename,
        vehicle_id=vehicle.id,
    )

    db.session.add(document)
    return document


def update_document(document: VehicleDocument, form, uploaded_file) -> VehicleDocument:
    document.name = normalize_document_name(form.get("name"))
    document.document_type = normalize_document_type()
    document.expiry_date = parse_optional_date(form.get("expiry_date"))
    document.notes = normalize_notes(form.get("notes"))

    if uploaded_file and uploaded_file.filename:
        new_path, original_filename = save_document_file(uploaded_file, document.vehicle_id)
        delete_relative_static_file(document.file_path)
        document.file_path = new_path
        document.original_filename = original_filename

    return document


def delete_document(document: VehicleDocument) -> None:
    delete_relative_static_file(document.file_path)
    db.session.delete(document)