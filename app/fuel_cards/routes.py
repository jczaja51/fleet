from datetime import datetime, date

from flask import Blueprint, flash, render_template, request, redirect, url_for
from flask_login import login_required
from werkzeug.security import generate_password_hash

from app import db
from app.models import FuelCard, Vehicle
from app.utils import calculate_status

fuel_bp = Blueprint("fuel_cards", __name__, url_prefix="/fuel-cards")


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def normalize_station(value):
    cleaned = (value or "").strip()
    return cleaned[:60] if cleaned else None


def normalize_card_number(value):
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    return digits[:4] if digits else None


def normalize_pin(value):
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    return digits[:6] if digits else None

def validate_card_form(station, number, pin, expiry, vehicle_id):
    errors = {}

    if not station:
        errors["station"] = "Podaj nazwę stacji."
    elif len(station) < 2:
        errors["station"] = "Nazwa stacji jest za krótka."
    elif len(station) > 60:
        errors["station"] = "Nazwa stacji może mieć maksymalnie 60 znaków."

    if not number:
        errors["number"] = "Podaj 4 ostatnie cyfry karty."
    elif not number.isdigit() or len(number) != 4:
        errors["number"] = "Pole musi zawierać dokładnie 4 cyfry."

    if not pin:
        errors["pin"] = "Podaj PIN."
    elif not pin.isdigit() or not (4 <= len(pin) <= 6):
        errors["pin"] = "PIN musi zawierać od 4 do 6 cyfr."

    if expiry and not parse_date(expiry):
        errors["expiry"] = "Data ważności musi mieć format RRRR-MM-DD."

    if vehicle_id:
        vehicle = Vehicle.query.get(vehicle_id)
        if not vehicle:
            errors["vehicle_id"] = "Wybrany pojazd nie istnieje."

    return errors

def attach_card_helpers(card):
    card.status = calculate_status(card.expiry)
    return card


def build_filters():
    return {
        "q": (request.args.get("q") or "").strip(),
        "assigned": (request.args.get("assigned") or "").strip(),
        "sort": (request.args.get("sort") or "").strip(),
    }


def build_stats(cards):
    return {
        "total_cards": len(cards),
        "assigned_cards": sum(1 for c in cards if c.vehicle_id),
        "warning_cards": sum(
            1 for c in cards if c.expiry and 0 <= (c.expiry - date.today()).days <= 30
        ),
        "danger_cards": sum(
            1 for c in cards if c.expiry and (c.expiry - date.today()).days < 0
        ),
    }

@login_required
@fuel_bp.route("/")
def list_cards():
    filters = {
        "q": (request.args.get("q") or "").strip(),
        "assigned": (request.args.get("assigned") or "").strip(),
        "sort": (request.args.get("sort") or "").strip(),
    }

    q = filters["q"]
    assigned = filters["assigned"]
    sort = filters["sort"]

    query = FuelCard.query.outerjoin(Vehicle)

    if q:
        like_value = f"%{q}%"
        query = query.filter(
            db.or_(
                FuelCard.station.ilike(like_value),
                FuelCard.number.ilike(like_value),
                Vehicle.registration.ilike(like_value),
                Vehicle.brand.ilike(like_value),
                Vehicle.model.ilike(like_value),
            )
        )

    if assigned == "assigned":
        query = query.filter(FuelCard.vehicle_id.isnot(None))
    elif assigned == "unassigned":
        query = query.filter(FuelCard.vehicle_id.is_(None))

    if sort == "station_asc":
        query = query.order_by(FuelCard.station.asc().nullslast(), FuelCard.id.desc())
    elif sort == "station_desc":
        query = query.order_by(FuelCard.station.desc().nullslast(), FuelCard.id.desc())
    elif sort == "number_asc":
        query = query.order_by(FuelCard.number.asc().nullslast(), FuelCard.id.desc())
    elif sort == "number_desc":
        query = query.order_by(FuelCard.number.desc().nullslast(), FuelCard.id.desc())
    elif sort == "expiry_asc":
        query = query.order_by(FuelCard.expiry.asc().nullslast(), FuelCard.id.desc())
    elif sort == "expiry_desc":
        query = query.order_by(FuelCard.expiry.desc().nullslast(), FuelCard.id.desc())
    elif sort == "vehicle_asc":
        query = query.order_by(Vehicle.registration.asc().nullslast(), FuelCard.id.desc())
    elif sort == "vehicle_desc":
        query = query.order_by(Vehicle.registration.desc().nullslast(), FuelCard.id.desc())
    else:
        query = query.order_by(FuelCard.id.desc())

    cards = query.all()

    for card in cards:
        attach_card_helpers(card)

    stats = {
        "total_cards": len(cards),
        "assigned_cards": sum(1 for c in cards if c.vehicle_id),
        "warning_cards": sum(1 for c in cards if c.expiry and 0 <= (c.expiry - date.today()).days <= 30),
        "danger_cards": sum(1 for c in cards if c.expiry and (c.expiry - date.today()).days < 0),
    }

    if request.headers.get("HX-Request") == "true":
        return render_template(
            "partials/fuel_cards_content.html",
            cards=cards,
            today=date.today(),
            filters=filters,
            stats=stats,
        )

    return render_template(
        "fuel_cards/list.html",
        cards=cards,
        today=date.today(),
        filters=filters,
        stats=stats,
    )

@login_required
@fuel_bp.route("/add", methods=["GET", "POST"])
def add_card():
    vehicles = Vehicle.query.order_by(Vehicle.registration.asc()).all()
    errors = {}

    if request.method == "POST":
        station = normalize_station(request.form.get("station"))
        number = normalize_card_number(request.form.get("number"))
        pin = normalize_pin(request.form.get("pin"))
        expiry_raw = (request.form.get("expiry") or "").strip()
        vehicle_id_raw = (request.form.get("vehicle_id") or "").strip()
        vehicle_id = int(vehicle_id_raw) if vehicle_id_raw.isdigit() else None

        errors = validate_card_form(station, number, pin, expiry_raw, vehicle_id)

        if not errors:
            card = FuelCard(
                station=station,
                number=number,
                pin=generate_password_hash(pin) if pin else None,
                expiry=parse_date(expiry_raw) if expiry_raw else None,
                vehicle_id=vehicle_id,
            )
            db.session.add(card)
            db.session.commit()

            flash("Karta paliwowa została dodana.", "success")
            return redirect(url_for("fuel_cards.list_cards"))

    return render_template("fuel_cards/add.html", vehicles=vehicles, errors=errors)

@login_required
@fuel_bp.route("/<int:card_id>")
def detail_card(card_id):
    card = FuelCard.query.get_or_404(card_id)
    attach_card_helpers(card)
    return render_template("fuel_cards/detail.html", card=card, today=date.today())

@login_required
@fuel_bp.route("/<int:card_id>/edit", methods=["GET", "POST"])
def edit_card(card_id):
    card = FuelCard.query.get_or_404(card_id)
    vehicles = Vehicle.query.order_by(Vehicle.registration.asc()).all()
    errors = {}

    if request.method == "POST":
        station = normalize_station(request.form.get("station"))
        number = normalize_card_number(request.form.get("number"))
        pin = normalize_pin(request.form.get("pin"))
        expiry_raw = (request.form.get("expiry") or "").strip()
        vehicle_id_raw = (request.form.get("vehicle_id") or "").strip()
        vehicle_id = int(vehicle_id_raw) if vehicle_id_raw.isdigit() else None

        errors = validate_card_form(station, number, pin, expiry_raw, vehicle_id)

        if not errors:
            card.station = station
            card.number = number
            card.pin = generate_password_hash(pin) if pin else None
            card.expiry = parse_date(expiry_raw) if expiry_raw else None
            card.vehicle_id = vehicle_id

            db.session.commit()
            flash("Karta została zaktualizowana.", "success")
            return redirect(url_for("fuel_cards.detail_card", card_id=card.id))

    attach_card_helpers(card)
    return render_template("fuel_cards/edit.html", card=card, vehicles=vehicles, errors=errors)

@login_required
@fuel_bp.route("/<int:card_id>/delete", methods=["POST"])
def delete_card(card_id):
    card = FuelCard.query.get_or_404(card_id)
    db.session.delete(card)
    db.session.commit()

    flash("Karta została usunięta.", "success")
    return redirect(url_for("fuel_cards.list_cards"))