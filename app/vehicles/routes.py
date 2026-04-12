from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import db
from app.constants import TACHOGRAPH_CATEGORIES
from app.models import Vehicle
from app.services.storage_service import (
    StorageError,
    delete_relative_static_file,
    move_vehicle_storage_dir,
    save_vehicle_image,
    update_vehicle_file_references,
)

vehicles_bp = Blueprint("vehicles", __name__, url_prefix="/vehicles")


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@vehicles_bp.route("/add", methods=["GET", "POST"])
def add_vehicle():
    if request.method == "POST":
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        registration = request.form.get("registration", "").strip().upper()
        mileage = parse_int(request.form.get("mileage"))
        vehicle_type = request.form.get("type")
        category = request.form.get("category", "").strip()
        production_year = parse_int(request.form.get("production_year"))
        vin = request.form.get("vin", "").strip().upper()
        assigned_driver = request.form.get("assigned_driver", "").strip()
        oc_date = parse_date(request.form.get("oc_date"))
        inspection_date = parse_date(request.form.get("inspection_date"))
        tachograph_expiry_date_raw = request.form.get("tachograph_expiry_date")

        if not registration:
            flash("Numer rejestracyjny jest wymagany.", "error")
            return render_template("vehicles/create.html")

        image_path = None
        uploaded_image = request.files.get("image")
        if uploaded_image and uploaded_image.filename:
            try:
                image_path = save_vehicle_image(uploaded_image, registration)
            except StorageError as exc:
                flash(str(exc), "error")
                return render_template("vehicles/create.html")

        tachograph_expiry_date = (
            parse_date(tachograph_expiry_date_raw)
            if category in TACHOGRAPH_CATEGORIES and tachograph_expiry_date_raw
            else None
        )

        vehicle = Vehicle(
            name=f"{brand} {model}".strip() if brand or model else registration,
            brand=brand or None,
            model=model or None,
            registration=registration,
            mileage=mileage,
            type=vehicle_type or None,
            category=category or None,
            production_year=production_year,
            vin=vin or None,
            assigned_driver=assigned_driver or None,
            image=image_path,
            oc_date=oc_date,
            inspection_date=inspection_date,
            tachograph_expiry_date=tachograph_expiry_date,
        )

        vehicle.sync_name()

        db.session.add(vehicle)
        db.session.commit()

        flash("Pojazd został dodany.", "success")
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
        old_registration = vehicle.registration
        registration = request.form.get("registration", "").strip().upper()

        if not registration:
            flash("Numer rejestracyjny jest wymagany.", "error")
            return render_template("vehicles/edit.html", vehicle=vehicle)

        vehicle.brand = request.form.get("brand", "").strip() or None
        vehicle.model = request.form.get("model", "").strip() or None
        vehicle.registration = registration
        vehicle.mileage = parse_int(request.form.get("mileage"))
        vehicle.type = request.form.get("type") or None
        vehicle.category = request.form.get("category", "").strip() or None
        vehicle.production_year = parse_int(request.form.get("production_year"))
        vehicle.vin = request.form.get("vin", "").strip().upper() or None
        vehicle.assigned_driver = request.form.get("assigned_driver", "").strip() or None

        vehicle.oc_date = parse_date(request.form.get("oc_date"))
        vehicle.inspection_date = parse_date(request.form.get("inspection_date"))

        tachograph_expiry_date_raw = request.form.get("tachograph_expiry_date")
        vehicle.tachograph_expiry_date = (
            parse_date(tachograph_expiry_date_raw)
            if vehicle.category in TACHOGRAPH_CATEGORIES and tachograph_expiry_date_raw
            else None
        )

        registration_changed = old_registration != registration

        if registration_changed:
            try:
                move_vehicle_storage_dir(old_registration, registration)
                update_vehicle_file_references(vehicle, old_registration, registration)
            except StorageError as exc:
                flash(str(exc), "error")
                vehicle.registration = old_registration
                return render_template("vehicles/edit.html", vehicle=vehicle)

        uploaded_image = request.files.get("image")
        if uploaded_image and uploaded_image.filename:
            try:
                new_image_path = save_vehicle_image(uploaded_image, registration)
            except StorageError as exc:
                flash(str(exc), "error")
                return render_template("vehicles/edit.html", vehicle=vehicle)

            delete_relative_static_file(vehicle.image)
            vehicle.image = new_image_path

        vehicle.sync_name()

        db.session.commit()
        flash("Pojazd został zaktualizowany.", "success")
        return redirect(url_for("vehicles.detail", vehicle_id=vehicle.id))

    return render_template("vehicles/edit.html", vehicle=vehicle)


@vehicles_bp.route("/<int:vehicle_id>/delete", methods=["POST"])
def delete_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    db.session.delete(vehicle)
    db.session.commit()

    flash("Pojazd oraz powiązane dane zostały usunięte.", "success")
    return redirect(url_for("main.dashboard"))