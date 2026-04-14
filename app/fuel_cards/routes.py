from datetime import datetime, date

from flask import Blueprint, flash, render_template, request, redirect, url_for
from werkzeug.security import generate_password_hash

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


def hash_pin_value(pin_value):
    cleaned = (pin_value or "").strip()
    if not cleaned:
        return None
    return generate_password_hash(cleaned)


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
        station = normalize_optional_text(request.form.get("station"))
        number = normalize_optional_text(request.form.get("number"))
        pin = hash_pin_value(request.form.get("pin"))
        expiry = request.form.get("expiry")
        vehicle_id = request.form.get("vehicle_id")

        card = FuelCard(
            station=station,
            number=number,
            pin=pin,
            expiry=parse_date(expiry) if expiry else None,
            vehicle_id=int(vehicle_id) if vehicle_id else None,
        )

        db.session.add(card)
        db.session.commit()

        return redirect(url_for("fuel_cards.list_cards"))

    return render_template("fuel_cards/add.html", vehicles=vehicles)


@fuel_bp.route("/<int:card_id>/edit", methods=["GET", "POST"])
def edit_card(card_id):
    card = FuelCard.query.get_or_404(card_id)
    vehicles = Vehicle.query.order_by(Vehicle.registration.asc()).all()

    if request.method == "POST":
        card.station = normalize_optional_text(request.form.get("station"))
        card.number = normalize_optional_text(request.form.get("number"))

        new_pin = request.form.get("pin")
        if new_pin is not None and new_pin.strip():
            card.pin = hash_pin_value(new_pin)

        expiry = request.form.get("expiry")
        vehicle_id = request.form.get("vehicle_id")

        card.expiry = parse_date(expiry) if expiry else None
        card.vehicle_id = int(vehicle_id) if vehicle_id else None

        db.session.commit()
        flash("Karta została zaktualizowana. PIN nie jest wyświetlany po zapisaniu ze względów bezpieczeństwa.", "success")
        return redirect(url_for("fuel_cards.list_cards"))

    return render_template("fuel_cards/edit.html", card=card, vehicles=vehicles)


@fuel_bp.route("/<int:card_id>/delete", methods=["POST"])
def delete_card(card_id):
    card = FuelCard.query.get_or_404(card_id)

    db.session.delete(card)
    db.session.commit()

    return redirect(url_for("fuel_cards.list_cards"))