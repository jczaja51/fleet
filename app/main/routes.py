from flask import Blueprint, render_template, request
from sqlalchemy import or_

from app.models import Vehicle, Alert, FuelCard, VehicleDocument
from app.services.alert_service import refresh_all_alerts
from app.utils import calculate_status

main_bp = Blueprint("main", __name__)


def normalize_vehicle_type(value: str | None) -> str:
    if not value:
        return ""

    value = value.strip().lower()

    mapping = {
        "firmowe": "firmowe",
        "firmowy": "firmowe",
        "leasing": "leasing",
        "leasingowe": "leasing",
        "leasingowy": "leasing",
        "prywatne": "prywatne",
        "prywatny": "prywatne",
    }

    return mapping.get(value, value)


@main_bp.route("/")
def dashboard():
    refresh_all_alerts()

    q = request.args.get("q", "").strip()
    selected_type = normalize_vehicle_type(request.args.get("type"))

    vehicles_query = Vehicle.query.order_by(Vehicle.id.desc())

    if q:
        vehicles_query = vehicles_query.filter(
            or_(
                Vehicle.name.ilike(f"%{q}%"),
                Vehicle.registration.ilike(f"%{q}%"),
            )
        )

    if selected_type:
        if selected_type == "firmowe":
            vehicles_query = vehicles_query.filter(
                or_(
                    Vehicle.type.ilike("%firmowe%"),
                    Vehicle.type.ilike("%firmowy%"),
                )
            )
        elif selected_type == "leasing":
            vehicles_query = vehicles_query.filter(
                or_(
                    Vehicle.type.ilike("%leasing%"),
                    Vehicle.type.ilike("%leasingowe%"),
                    Vehicle.type.ilike("%leasingowy%"),
                )
            )
        elif selected_type == "prywatne":
            vehicles_query = vehicles_query.filter(
                or_(
                    Vehicle.type.ilike("%prywatne%"),
                    Vehicle.type.ilike("%prywatny%"),
                )
            )
        else:
            vehicles_query = vehicles_query.filter(Vehicle.type.ilike(f"%{selected_type}%"))

    vehicles = vehicles_query.all()

    alerts = Alert.query.order_by(Alert.date.asc()).all()
    fuel_cards = FuelCard.query.all()
    latest_documents = (
        VehicleDocument.query
        .order_by(VehicleDocument.created_at.desc())
        .limit(5)
        .all()
    )

    for vehicle in vehicles:
        vehicle.oc_status = calculate_status(vehicle.oc_date)
        vehicle.inspection_status = calculate_status(vehicle.inspection_date)

    stats = {
        "total_vehicles": Vehicle.query.count(),
        "fuel_cards": FuelCard.query.count(),
        "warning_alerts": Alert.query.filter_by(level="warning").count(),
        "danger_alerts": Alert.query.filter_by(level="danger").count(),
    }

    return render_template(
        "main/dashboard.html",
        vehicles=vehicles,
        alerts=alerts[:6],
        latest_documents=latest_documents,
        stats=stats,
        filters={
            "q": q,
            "type": selected_type,
        },
    )