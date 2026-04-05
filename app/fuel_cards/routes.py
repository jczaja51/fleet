from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for
from app import db
from app.models import FuelCard, Vehicle
from app.utils import calculate_status

fuel_bp = Blueprint("fuel_cards", __name__, url_prefix="/fuel-cards")


@fuel_bp.route("/")
def list_cards():
    cards = FuelCard.query.order_by(FuelCard.id.desc()).all()

    for c in cards:
        c.status = calculate_status(c.expiry)

    return render_template("fuel_cards/list.html", cards=cards)


@fuel_bp.route("/add", methods=["GET", "POST"])
def add_card():
    vehicles = Vehicle.query.order_by(Vehicle.registration.asc()).all()
    
    if request.method == "POST":
        station = request.form.get("station")
        number = request.form.get("number")
        pin = request.form.get("pin")
        expiry = request.form.get("expiry")
        vehicle_id = request.form.get("vehicle_id")

        card = FuelCard(
            station=station,
            number=number,
            pin=pin,
            expiry=datetime.strptime(expiry, "%Y-%m-%d").date() if expiry else None,
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
        card.station = request.form.get("station")
        card.number = request.form.get("number")
        card.pin = request.form.get("pin")

        expiry = request.form.get("expiry")
        vehicle_id = request.form.get("vehicle_id")

        card.expiry = datetime.strptime(expiry, "%Y-%m-%d").date() if expiry else None
        card.vehicle_id = int(vehicle_id) if vehicle_id else None

        db.session.commit()
        return redirect(url_for("fuel_cards.list_cards"))

    return render_template("fuel_cards/edit.html", card=card, vehicles=vehicles)


@fuel_bp.route("/<int:card_id>/delete", methods=["POST"])
def delete_card(card_id):
    card = FuelCard.query.get_or_404(card_id)

    db.session.delete(card)
    db.session.commit()

    return redirect(url_for("fuel_cards.list_cards"))