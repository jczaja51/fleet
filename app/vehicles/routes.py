import re
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

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


def normalize_spaces(value):
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_registration(value):
    value = normalize_spaces(value).upper()
    return re.sub(r"[^A-Z0-9]", "", value)


def normalize_identifier(value):
    value = normalize_spaces(value).upper()
    value = re.sub(r"\s+", "", value)
    return value


def validate_vehicle_form(form, uploaded_image=None, current_vehicle_id=None):
    errors = []

    brand = normalize_spaces(form.get("brand"))
    model = normalize_spaces(form.get("model"))
    vehicle_type = normalize_spaces(form.get("type"))
    category = normalize_spaces(form.get("category"))
    registration = normalize_registration(form.get("registration"))
    production_year = parse_int(form.get("production_year"))
    mileage = parse_int(form.get("mileage"))
    vin = normalize_identifier(form.get("vin"))
    assigned_driver = normalize_spaces(form.get("assigned_driver"))

    oc_date_raw = normalize_spaces(form.get("oc_date"))
    inspection_date_raw = normalize_spaces(form.get("inspection_date"))
    tachograph_date_raw = normalize_spaces(form.get("tachograph_expiry_date"))

    current_year = datetime.now().year + 1

    if not brand:
        errors.append("Marka jest wymagana.")
    elif len(brand) < 2 or len(brand) > 40:
        errors.append("Marka musi mieć od 2 do 40 znaków.")
    elif not re.fullmatch(r"[A-Za-zÀ-ž0-9 .,'/\-()]+", brand):
        errors.append("Marka zawiera niedozwolone znaki.")

    if not model:
        errors.append("Model jest wymagany.")
    elif len(model) > 60:
        errors.append("Model może mieć maksymalnie 60 znaków.")
    elif not re.fullmatch(r"[A-Za-zÀ-ž0-9 .,'/\-()]+", model):
        errors.append("Model zawiera niedozwolone znaki.")

    if vehicle_type not in {"Firmowe", "Leasing", "Prywatne"}:
        errors.append("Wybierz poprawny typ pojazdu.")

    allowed_categories = {
        "Samochód osobowy do 3,5 t DMC",
        "Samochód ciężarowy do 3,5 t DMC",
        "Samochód ciężarowy powyżej 3,5 t DMC",
        "Pojazd specjalny",
        "Ciągnik siodłowy",
        "Autobus",
        "Przyczepa / naczepa",
        "Inne",
    }

    if category not in allowed_categories:
        errors.append("Wybierz poprawną kategorię pojazdu.")

    if not registration:
        errors.append("Numer rejestracyjny jest wymagany.")
    elif len(registration) < 3 or len(registration) > 12:
        errors.append("Numer rejestracyjny musi mieć od 3 do 12 znaków.")

    existing_vehicle = Vehicle.query.filter_by(registration=registration).first()
    if existing_vehicle and existing_vehicle.id != current_vehicle_id:
        errors.append("Pojazd o takim numerze rejestracyjnym już istnieje.")

    if production_year is None:
        errors.append("Rok produkcji jest wymagany.")
    elif production_year < 1950 or production_year > current_year:
        errors.append("Podaj poprawny rok produkcji.")

    if mileage is not None:
        if mileage < 0:
            errors.append("Przebieg nie może być ujemny.")
        elif mileage > 9999999:
            errors.append("Przebieg jest zbyt duży.")

    if vin:
        if len(vin) < 3 or len(vin) > 32:
            errors.append("VIN / identyfikator musi mieć od 3 do 32 znaków.")
        elif not re.fullmatch(r"[A-Z0-9\-/]+", vin):
            errors.append("VIN / identyfikator zawiera niedozwolone znaki.")

    if assigned_driver:
        if len(assigned_driver) > 80:
            errors.append("Przypisany kierowca może mieć maksymalnie 80 znaków.")
        elif not re.fullmatch(r"[A-Za-zÀ-ž .'\-]+", assigned_driver):
            errors.append("Pole kierowcy zawiera niedozwolone znaki.")

    if oc_date_raw and not parse_date(oc_date_raw):
        errors.append("Data ważności OC ma niepoprawny format.")

    if inspection_date_raw and not parse_date(inspection_date_raw):
        errors.append("Data ważności przeglądu ma niepoprawny format.")

    if category in TACHOGRAPH_CATEGORIES and tachograph_date_raw and not parse_date(tachograph_date_raw):
        errors.append("Data ważności tachografu ma niepoprawny format.")

    if uploaded_image and uploaded_image.filename:
        content_length = uploaded_image.content_length
        if content_length and content_length > 10 * 1024 * 1024:
            errors.append("Zdjęcie jest za duże. Maksymalny rozmiar to 10 MB.")

    cleaned_data = {
        "brand": brand or None,
        "model": model or None,
        "vehicle_type": vehicle_type or None,
        "category": category or None,
        "registration": registration,
        "production_year": production_year,
        "mileage": mileage,
        "vin": vin or None,
        "assigned_driver": assigned_driver or None,
        "oc_date": parse_date(oc_date_raw),
        "inspection_date": parse_date(inspection_date_raw),
        "tachograph_expiry_date": parse_date(tachograph_date_raw) if category in TACHOGRAPH_CATEGORIES and tachograph_date_raw else None,
    }

    return errors, cleaned_data

@login_required
@vehicles_bp.route("/add", methods=["GET", "POST"])
def add_vehicle():
    if request.method == "POST":
        uploaded_image = request.files.get("image")
        errors, data = validate_vehicle_form(request.form, uploaded_image=uploaded_image)

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("vehicles/create.html")

        image_path = None
        if uploaded_image and uploaded_image.filename:
            try:
                image_path = save_vehicle_image(uploaded_image, data["registration"])
            except StorageError as exc:
                flash(str(exc), "error")
                return render_template("vehicles/create.html")

        vehicle = Vehicle(
            name=f"{data['brand'] or ''} {data['model'] or ''}".strip() or data["registration"],
            brand=data["brand"],
            model=data["model"],
            registration=data["registration"],
            mileage=data["mileage"],
            type=data["vehicle_type"],
            category=data["category"],
            production_year=data["production_year"],
            vin=data["vin"],
            assigned_driver=data["assigned_driver"],
            image=image_path,
            oc_date=data["oc_date"],
            inspection_date=data["inspection_date"],
            tachograph_expiry_date=data["tachograph_expiry_date"],
        )

        vehicle.sync_name()

        db.session.add(vehicle)
        db.session.commit()

        flash("Pojazd został dodany.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("vehicles/create.html")

@login_required
@vehicles_bp.route("/<int:vehicle_id>")
def detail(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    return render_template("vehicles/detail.html", vehicle=vehicle)

@login_required
@vehicles_bp.route("/<int:vehicle_id>/edit", methods=["GET", "POST"])
def edit_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    if request.method == "POST":
        old_registration = vehicle.registration
        uploaded_image = request.files.get("image")

        errors, data = validate_vehicle_form(
            request.form,
            uploaded_image=uploaded_image,
            current_vehicle_id=vehicle.id,
        )

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("vehicles/edit.html", vehicle=vehicle)

        registration_changed = old_registration != data["registration"]

        vehicle.brand = data["brand"]
        vehicle.model = data["model"]
        vehicle.registration = data["registration"]
        vehicle.mileage = data["mileage"]
        vehicle.type = data["vehicle_type"]
        vehicle.category = data["category"]
        vehicle.production_year = data["production_year"]
        vehicle.vin = data["vin"]
        vehicle.assigned_driver = data["assigned_driver"]
        vehicle.oc_date = data["oc_date"]
        vehicle.inspection_date = data["inspection_date"]
        vehicle.tachograph_expiry_date = data["tachograph_expiry_date"]

        if registration_changed:
            try:
                move_vehicle_storage_dir(old_registration, data["registration"])
                update_vehicle_file_references(vehicle, old_registration, data["registration"])
            except StorageError as exc:
                flash(str(exc), "error")
                vehicle.registration = old_registration
                return render_template("vehicles/edit.html", vehicle=vehicle)

        if uploaded_image and uploaded_image.filename:
            try:
                new_image_path = save_vehicle_image(uploaded_image, data["registration"])
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

@login_required
@vehicles_bp.route("/<int:vehicle_id>/delete", methods=["POST"])
def delete_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    db.session.delete(vehicle)
    db.session.commit()

    flash("Pojazd oraz powiązane dane zostały usunięte.", "success")
    return redirect(url_for("main.dashboard"))