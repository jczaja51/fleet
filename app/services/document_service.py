from __future__ import annotations

from app import db
from app.models import Vehicle, VehicleDocument
from app.services.storage_service import (
    delete_relative_static_file,
    save_document_file,
)

__all__ = [
    "DocumentValidationError",
    "normalize_document_name",
    "normalize_document_type",
    "normalize_notes",
    "create_document_for_vehicle",
    "update_document",
    "delete_document",
]


class DocumentValidationError(ValueError):
    pass


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
        file_path, original_filename = save_document_file(uploaded_file, vehicle.registration)

    document = VehicleDocument(
        name=normalize_document_name(form.get("name")),
        document_type=normalize_document_type(),
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
    document.notes = normalize_notes(form.get("notes"))

    if uploaded_file and uploaded_file.filename:
        new_path, original_filename = save_document_file(uploaded_file, document.vehicle.registration)
        delete_relative_static_file(document.file_path)
        document.file_path = new_path
        document.original_filename = original_filename

    return document


def delete_document(document: VehicleDocument) -> None:
    delete_relative_static_file(document.file_path)
    db.session.delete(document)