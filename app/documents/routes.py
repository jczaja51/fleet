from pathlib import Path
from uuid import uuid4
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, current_app
from werkzeug.utils import secure_filename

from app import db
from app.models import Vehicle, VehicleDocument

documents_bp = Blueprint("documents", __name__, url_prefix="/documents")

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def normalize_registration(registration):
    if not registration:
        return "unknown_vehicle"
    return secure_filename(registration.strip().lower().replace(" ", "_"))


def delete_physical_file(file_path):
    if not file_path:
        return

    full_path = Path(current_app.static_folder) / file_path
    if full_path.exists() and full_path.is_file():
        full_path.unlink()


def save_document_file(uploaded_file, vehicle):
    original_name = secure_filename(uploaded_file.filename)
    suffix = Path(original_name).suffix.lower()
    generated_name = f"{uuid4().hex}{suffix}"

    vehicle_folder = normalize_registration(vehicle.registration)
    upload_dir = Path(current_app.static_folder) / "uploads" / "documents" / vehicle_folder
    upload_dir.mkdir(parents=True, exist_ok=True)

    save_path = upload_dir / generated_name
    uploaded_file.save(save_path)

    return f"uploads/documents/{vehicle_folder}/{generated_name}"


@documents_bp.route("/add/<int:vehicle_id>", methods=["GET", "POST"])
def add_document(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    if request.method == "POST":
        name = request.form.get("name")
        document_type = request.form.get("document_type")
        expiry_date = request.form.get("expiry_date")
        uploaded_file = request.files.get("file")

        file_path = None

        if uploaded_file and uploaded_file.filename and allowed_file(uploaded_file.filename):
            file_path = save_document_file(uploaded_file, vehicle)

        document = VehicleDocument(
            name=name,
            document_type=document_type,
            expiry_date=datetime.strptime(expiry_date, "%Y-%m-%d").date() if expiry_date else None,
            file_path=file_path,
            vehicle_id=vehicle.id,
        )

        db.session.add(document)
        db.session.commit()

        return redirect(url_for("vehicles.detail", vehicle_id=vehicle.id))

    return render_template("documents/add.html", vehicle=vehicle)


@documents_bp.route("/<int:document_id>/edit", methods=["GET", "POST"])
def edit_document(document_id):
    document = VehicleDocument.query.get_or_404(document_id)
    vehicle = document.vehicle

    if request.method == "POST":
        document.name = request.form.get("name")
        document.document_type = request.form.get("document_type")

        expiry_date = request.form.get("expiry_date")
        document.expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d").date() if expiry_date else None

        uploaded_file = request.files.get("file")

        if uploaded_file and uploaded_file.filename and allowed_file(uploaded_file.filename):
            delete_physical_file(document.file_path)
            document.file_path = save_document_file(uploaded_file, vehicle)

        db.session.commit()
        return redirect(url_for("vehicles.detail", vehicle_id=vehicle.id))

    return render_template("documents/edit.html", document=document, vehicle=vehicle)


@documents_bp.route("/<int:document_id>/delete", methods=["POST"])
def delete_document(document_id):
    document = VehicleDocument.query.get_or_404(document_id)
    vehicle_id = document.vehicle_id

    delete_physical_file(document.file_path)

    db.session.delete(document)
    db.session.commit()

    return redirect(url_for("vehicles.detail", vehicle_id=vehicle_id))