from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, render_template, request, redirect, url_for, current_app
from werkzeug.utils import secure_filename

from app.models import db, Vehicle

vehicles_bp = Blueprint("vehicles", __name__, url_prefix="/vehicles")

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_vehicle_image(uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        return None

    if not allowed_image(uploaded_file.filename):
        return None

    original_name = secure_filename(uploaded_file.filename)
    suffix = Path(original_name).suffix.lower()
    generated_name = f"{uuid4().hex}{suffix}"

    upload_dir = Path(current_app.static_folder) / "uploads" / "vehicles"
    upload_dir.mkdir(parents=True, exist_ok=True)

    save_path = upload_dir / generated_name
    uploaded_file.save(save_path)

    return f"uploads/vehicles/{generated_name}"


def delete_vehicle_image(image_path):
    if not image_path:
        return

    full_path = Path(current_app.static_folder) / image_path
    if full_path.exists() and full_path.is_file():
        full_path.unlink()


@vehicles_bp.route("/add", methods=["GET", "POST"])
def add_vehicle():
    if request.method == "POST":
        name = request.form.get("name")
        registration = request.form.get("registration")
        mileage = request.form.get("mileage")
        vtype = request.form.get("type")
        oc_date = request.form.get("oc_date")
        inspection_date = request.form.get("inspection_date")

        uploaded_image = request.files.get("image")
        image_path = save_vehicle_image(uploaded_image)

        vehicle = Vehicle(
            name=name,
            registration=registration,
            mileage=int(mileage) if mileage else None,
            type=vtype,
            image=image_path,
            oc_date=datetime.strptime(oc_date, "%Y-%m-%d").date() if oc_date else None,
            inspection_date=datetime.strptime(inspection_date, "%Y-%m-%d").date() if inspection_date else None,
        )

        db.session.add(vehicle)
        db.session.commit()

        return redirect(url_for("main.dashboard"))

    return render_template("vehicles/create.html")


@vehicles_bp.route("/<int:vehicle_id>")
def detail(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    return render_template("vehicles/detail.html", vehicle=vehicle)


@vehicles_bp.route("/<int:vehicle_id>/edit", methods=["GET", "POST"])
def edit_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    if request.method == "POST":
        vehicle.name = request.form.get("name")
        vehicle.registration = request.form.get("registration")
        vehicle.mileage = int(request.form.get("mileage")) if request.form.get("mileage") else None
        vehicle.type = request.form.get("type")

        oc_date = request.form.get("oc_date")
        inspection_date = request.form.get("inspection_date")

        vehicle.oc_date = datetime.strptime(oc_date, "%Y-%m-%d").date() if oc_date else None
        vehicle.inspection_date = datetime.strptime(inspection_date, "%Y-%m-%d").date() if inspection_date else None

        uploaded_image = request.files.get("image")
        new_image_path = save_vehicle_image(uploaded_image)

        if new_image_path:
            delete_vehicle_image(vehicle.image)
            vehicle.image = new_image_path

        db.session.commit()
        return redirect(url_for("vehicles.detail", vehicle_id=vehicle.id))

    return render_template("vehicles/edit.html", vehicle=vehicle)


@vehicles_bp.route("/<int:vehicle_id>/delete", methods=["POST"])
def delete_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    delete_vehicle_image(vehicle.image)

    db.session.delete(vehicle)
    db.session.commit()

    return redirect(url_for("main.dashboard"))