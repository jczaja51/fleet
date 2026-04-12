from flask import Blueprint, render_template, request
from sqlalchemy import case, or_

from app.models import Alert, FuelCard, Vehicle, VehicleDocument
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


def normalize_sort(value: str | None) -> str:
    if not value:
        return ""

    value = value.strip().lower()

    allowed = {
        "brand_asc",
        "brand_desc",
        "registration_asc",
        "registration_desc",
        "oc_asc",
        "inspection_asc",
        "mileage_desc",
        "mileage_asc",
    }

    return value if value in allowed else ""


def apply_vehicle_sort(query, sort_key: str):
    if sort_key == "brand_asc":
        return query.order_by(
            Vehicle.brand.asc(),
            Vehicle.model.asc(),
            Vehicle.registration.asc(),
        )

    if sort_key == "brand_desc":
        return query.order_by(
            Vehicle.brand.desc(),
            Vehicle.model.desc(),
            Vehicle.registration.desc(),
        )

    if sort_key == "registration_asc":
        return query.order_by(Vehicle.registration.asc())

    if sort_key == "registration_desc":
        return query.order_by(Vehicle.registration.desc())

    if sort_key == "oc_asc":
        return query.order_by(
            case((Vehicle.oc_date.is_(None), 1), else_=0),
            Vehicle.oc_date.asc(),
            Vehicle.id.desc(),
        )

    if sort_key == "inspection_asc":
        return query.order_by(
            case((Vehicle.inspection_date.is_(None), 1), else_=0),
            Vehicle.inspection_date.asc(),
            Vehicle.id.desc(),
        )

    if sort_key == "mileage_desc":
        return query.order_by(
            case((Vehicle.mileage.is_(None), 1), else_=0),
            Vehicle.mileage.desc(),
            Vehicle.id.desc(),
        )

    if sort_key == "mileage_asc":
        return query.order_by(
            case((Vehicle.mileage.is_(None), 1), else_=0),
            Vehicle.mileage.asc(),
            Vehicle.id.desc(),
        )

    return query.order_by(Vehicle.id.desc())


@main_bp.route("/")
def dashboard():
    refresh_all_alerts()

    q = request.args.get("q", "").strip()
    selected_type = normalize_vehicle_type(request.args.get("type"))
    selected_sort = normalize_sort(request.args.get("sort"))

    vehicles_query = Vehicle.query

    if q:
        vehicles_query = vehicles_query.filter(
            or_(
                Vehicle.name.ilike(f"%{q}%"),
                Vehicle.brand.ilike(f"%{q}%"),
                Vehicle.model.ilike(f"%{q}%"),
                Vehicle.registration.ilike(f"%{q}%"),
                Vehicle.assigned_driver.ilike(f"%{q}%"),
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
            vehicles_query = vehicles_query.filter(
                Vehicle.type.ilike(f"%{selected_type}%")
            )

    vehicles_query = apply_vehicle_sort(vehicles_query, selected_sort)
    vehicles = vehicles_query.all()

    alerts = sorted(
        Alert.query.all(),
        key=lambda alert: (
            0 if alert.level == "danger" else 1,
            alert.date is None,
            alert.date
        )
    )

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

    context = {
        "vehicles": vehicles,
        "alerts": alerts[:6],
        "latest_documents": latest_documents,
        "stats": stats,
        "filters": {
            "q": q,
            "type": selected_type,
            "sort": selected_sort,
        },
    }

    if request.headers.get("HX-Request") == "true":
        return render_template("partials/dashboard_content.html", **context)

    return render_template("main/dashboard.html", **context)