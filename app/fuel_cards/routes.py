from datetime import datetime, date

from flask import Blueprint, flash, render_template, request, redirect, url_for

from app import db
from app.models import FuelCard, Vehicle
from app.utils import calculate_status

fuel_bp = Blueprint("fuel_cards", __name__, url_prefix="/fuel-cards")


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def normalize_optional_text(value):
    cleaned = (value or "").strip()
    return cleaned or None


def normalize_station(value):
    cleaned = " ".join((value or "").split()).strip()
    return cleaned


def normalize_card_number(value):
    return "".join(ch for ch in (value or "") if ch.isdigit())


def normalize_pin(value):
    return "".join(ch for ch in (value or "") if ch.isdigit())


def validate_fuel_card_form(station, number, pin, expiry, vehicle_id):
    errors = {}

    station = normalize_station(station)
    number = normalize_card_number(number)
    pin = normalize_pin(pin)
    expiry = (expiry or "").strip()
    vehicle_id = (vehicle_id or "").strip()

    if not station:
        errors["station"] = "Podaj nazwę stacji."
    elif len(station) < 2:
        errors["station"] = "Nazwa stacji jest za krótka."
    elif len(station) > 60:
        errors["station"] = "Nazwa stacji może mieć maksymalnie 60 znaków."

    if not number:
        errors["number"] = "Podaj 4 ostatnie cyfry karty."
    elif len(number) != 4:
        errors["number"] = "Numer karty musi zawierać dokładnie 4 cyfry."

    if not pin:
        errors["pin"] = "Podaj PIN."
    elif not (4 <= len(pin) <= 6):
        errors["pin"] = "PIN musi zawierać od 4 do 6 cyfr."

    parsed_expiry = None
    if expiry:
        try:
            parsed_expiry = parse_date(expiry)
        except ValueError:
            errors["expiry"] = "Data ważności musi mieć format RRRR-MM-DD."

    parsed_vehicle_id = None
    if vehicle_id:
        if not vehicle_id.isdigit():
            errors["vehicle_id"] = "Wybrano niepoprawny pojazd."
        else:
            parsed_vehicle_id = int(vehicle_id)
            vehicle_exists = db.session.get(Vehicle, parsed_vehicle_id)
            if not vehicle_exists:
                errors["vehicle_id"] = "Wybrany pojazd nie istnieje."

    return {
        "errors": errors,
        "station": station,
        "number": number,
        "pin": pin,
        "expiry": parsed_expiry,
        "vehicle_id": parsed_vehicle_id,
    }


@fuel_bp.route("/")
def list_cards():
    cards = FuelCard.query.order_by(FuelCard.id.desc()).all()

    for c in cards:
        c.status = calculate_status(c.expiry)

    return render_template("fuel_cards/list.html", cards=cards, today=date.today())


@fuel_bp.route("/add", methods=["GET", "POST"])
def add_card():
    vehicles = Vehicle.query.order_by(Vehicle.registration.asc()).all()

    if request.method == "POST":
        validated = validate_fuel_card_form(
            station=request.form.get("station"),
            number=request.form.get("number"),
            pin=request.form.get("pin"),
            expiry=request.form.get("expiry"),
            vehicle_id=request.form.get("vehicle_id"),
        )

        errors = validated["errors"]

        if errors:
            for message in errors.values():
                flash(message, "danger")

            return render_template(
                "fuel_cards/add.html",
                vehicles=vehicles,
                errors=errors,
            )

        card = FuelCard(
            station=validated["station"],
            number=validated["number"],
            pin=validated["pin"],
            expiry=validated["expiry"],
            vehicle_id=validated["vehicle_id"],
        )

        db.session.add(card)
        db.session.commit()

        flash("Karta paliwowa została dodana.", "success")
        return redirect(url_for("fuel_cards.list_cards"))

    return render_template("fuel_cards/add.html", vehicles=vehicles, errors={})


@fuel_bp.route("/<int:card_id>/edit", methods=["GET", "POST"])
def edit_card(card_id):
    card = FuelCard.query.get_or_404(card_id)
    vehicles = Vehicle.query.order_by(Vehicle.registration.asc()).all()

    if request.method == "POST":
        validated = validate_fuel_card_form(
            station=request.form.get("station"),
            number=request.form.get("number"),
            pin=request.form.get("pin"),
            expiry=request.form.get("expiry"),
            vehicle_id=request.form.get("vehicle_id"),
        )

        errors = validated["errors"]

        if errors:
            for message in errors.values():
                flash(message, "danger")

            return render_template(
                "fuel_cards/edit.html",
                card=card,
                vehicles=vehicles,
                errors=errors,
            )

        card.station = validated["station"]
        card.number = validated["number"]
        card.pin = validated["pin"]
        card.expiry = validated["expiry"]
        card.vehicle_id = validated["vehicle_id"]

        db.session.commit()

        flash("Karta została zaktualizowana.", "success")
        return redirect(url_for("fuel_cards.list_cards"))

    return render_template("fuel_cards/edit.html", card=card, vehicles=vehicles, errors={})


@fuel_bp.route("/<int:card_id>/delete", methods=["POST"])
def delete_card(card_id):
    card = FuelCard.query.get_or_404(card_id)

    db.session.delete(card)
    db.session.commit()

    flash("Karta została usunięta.", "success")
    return redirect(url_for("fuel_cards.list_cards"))