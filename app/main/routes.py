from flask import Blueprint, render_template
from app.models import Vehicle, Alert, FuelCard, VehicleDocument
from app.services.alert_service import refresh_all_alerts
from app.utils import calculate_status

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def dashboard():
    refresh_all_alerts()

    vehicles = Vehicle.query.order_by(Vehicle.id.desc()).all()
    alerts = Alert.query.order_by(Alert.date.asc()).all()
    fuel_cards = FuelCard.query.all()
    latest_documents = VehicleDocument.query.order_by(VehicleDocument.created_at.desc()).limit(5).all()

    for vehicle in vehicles:
        vehicle.oc_status = calculate_status(vehicle.oc_date)
        vehicle.inspection_status = calculate_status(vehicle.inspection_date)

    stats = {
        "total_vehicles": len(vehicles),
        "total_fuel_cards": len(fuel_cards),
        "warning_count": Alert.query.filter_by(level="warning").count(),
        "danger_count": Alert.query.filter_by(level="danger").count(),
    }

    return render_template(
        "main/dashboard.html",
        vehicles=vehicles,
        alerts=alerts[:6],
        latest_documents=latest_documents,
        stats=stats,
    )