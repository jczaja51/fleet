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


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


TACHOGRAPH_CATEGORIES = {
    "Samochód ciężarowy powyżej 3,5 t DMC",
    "Autobus",
}


@vehicles_bp.route("/add", methods=["GET", "POST"])
def add_vehicle():
    if request.method == "POST":
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        registration = request.form.get("registration", "").strip()
        mileage = request.form.get("mileage")
        vehicle_type = request.form.get("type")
        category = request.form.get("category", "").strip()
        production_year = request.form.get("production_year")
        vin = request.form.get("vin", "").strip()
        assigned_driver = request.form.get("assigned_driver", "").strip()
        oc_date = request.form.get("oc_date")
        inspection_date = request.form.get("inspection_date")
        tachograph_expiry_date = request.form.get("tachograph_expiry_date")

        uploaded_image = request.files.get("image")
        image_path = save_vehicle_image(uploaded_image)

        vehicle = Vehicle(
            name=f"{brand} {model}".strip() if brand or model else registration,
            brand=brand or None,
            model=model or None,
            registration=registration,
            mileage=int(mileage) if mileage else None,
            type=vehicle_type,
            category=category or None,
            production_year=int(production_year) if production_year else None,
            vin=vin or None,
            assigned_driver=assigned_driver or None,
            image=image_path,
            oc_date=parse_date(oc_date),
            inspection_date=parse_date(inspection_date),
            tachograph_expiry_date=parse_date(tachograph_expiry_date) if category in TACHOGRAPH_CATEGORIES and tachograph_expiry_date else None,
        )

        vehicle.sync_name()

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
        vehicle.brand = request.form.get("brand", "").strip() or None
        vehicle.model = request.form.get("model", "").strip() or None
        vehicle.registration = request.form.get("registration", "").strip()
        vehicle.mileage = int(request.form.get("mileage")) if request.form.get("mileage") else None
        vehicle.type = request.form.get("type")
        vehicle.category = request.form.get("category", "").strip() or None
        vehicle.production_year = int(request.form.get("production_year")) if request.form.get("production_year") else None
        vehicle.vin = request.form.get("vin", "").strip() or None
        vehicle.assigned_driver = request.form.get("assigned_driver", "").strip() or None

        oc_date = request.form.get("oc_date")
        inspection_date = request.form.get("inspection_date")
        tachograph_expiry_date = request.form.get("tachograph_expiry_date")

        vehicle.oc_date = parse_date(oc_date)
        vehicle.inspection_date = parse_date(inspection_date)
        vehicle.tachograph_expiry_date = (
            parse_date(tachograph_expiry_date)
            if vehicle.category in TACHOGRAPH_CATEGORIES and tachograph_expiry_date
            else None
        )

        uploaded_image = request.files.get("image")
        new_image_path = save_vehicle_image(uploaded_image)

        if new_image_path:
            delete_vehicle_image(vehicle.image)
            vehicle.image = new_image_path

        vehicle.sync_name()

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