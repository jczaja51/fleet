from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models import Vehicle, VehicleDocument
from app.services.document_service import (
    DocumentValidationError,
    create_document_for_vehicle,
    delete_document,
    update_document,
)
from app.services.storage_service import StorageError

documents_bp = Blueprint("documents", __name__, url_prefix="/documents")

@login_required
@documents_bp.route("/add/<int:vehicle_id>", methods=["GET", "POST"])
def add_document(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    if request.method == "POST":
        try:
            create_document_for_vehicle(vehicle, request.form, request.files.get("file"))
            db.session.commit()
            flash("Dokument został zapisany.", "success")
            return redirect(url_for("vehicles.detail", vehicle_id=vehicle.id))
        except (DocumentValidationError, StorageError) as exc:
            db.session.rollback()
            flash(str(exc), "error")

    return render_template(
        "documents/add.html",
        vehicle=vehicle,
    )

@login_required
@documents_bp.route("/<int:document_id>/edit", methods=["GET", "POST"])
def edit_document(document_id):
    document = VehicleDocument.query.get_or_404(document_id)
    vehicle = document.vehicle

    if request.method == "POST":
        try:
            update_document(document, request.form, request.files.get("file"))
            db.session.commit()
            flash("Dokument został zaktualizowany.", "success")
            return redirect(url_for("vehicles.detail", vehicle_id=vehicle.id))
        except (DocumentValidationError, StorageError) as exc:
            db.session.rollback()
            flash(str(exc), "error")

    return render_template(
        "documents/edit.html",
        document=document,
        vehicle=vehicle,
    )

@login_required
@documents_bp.route("/<int:document_id>/delete", methods=["POST"])
def delete_document_route(document_id):
    document = VehicleDocument.query.get_or_404(document_id)
    vehicle_id = document.vehicle_id

    delete_document(document)
    db.session.commit()

    flash("Dokument został usunięty.", "success")
    return redirect(url_for("vehicles.detail", vehicle_id=vehicle_id))