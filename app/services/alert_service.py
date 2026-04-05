from app import db
from app.models import Vehicle, Alert
from app.utils import (
    calculate_status,
    calculate_service_date_status,
    calculate_service_mileage_status,
    get_worse_status,
)


def vehicle_label(vehicle):
    return f"{vehicle.name} ({vehicle.registration})"


def refresh_vehicle_alerts(vehicle):
    Alert.query.filter_by(vehicle_id=vehicle.id).delete()

    vehicle_name = vehicle_label(vehicle)

    oc_status = calculate_status(vehicle.oc_date)
    if oc_status != "ok":
        db.session.add(Alert(
            label=f"Kończy się OC — {vehicle_name}",
            date=vehicle.oc_date,
            level=oc_status,
            vehicle_id=vehicle.id
        ))

    inspection_status = calculate_status(vehicle.inspection_date)
    if inspection_status != "ok":
        db.session.add(Alert(
            label=f"Kończy się przegląd — {vehicle_name}",
            date=vehicle.inspection_date,
            level=inspection_status,
            vehicle_id=vehicle.id
        ))

    for card in vehicle.fuel_cards:
        card_status = calculate_status(card.expiry)
        if card_status != "ok":
            station = card.station or "Karta paliwowa"
            number = card.number or ""
            db.session.add(Alert(
                label=f"{station} {number} — {vehicle_name}".strip(),
                date=card.expiry,
                level=card_status,
                vehicle_id=vehicle.id
            ))

    for doc in vehicle.documents:
        doc_status = calculate_status(doc.expiry_date)
        if doc_status != "ok":
            db.session.add(Alert(
                label=f"Dokument: {doc.name} — {vehicle_name}",
                date=doc.expiry_date,
                level=doc_status,
                vehicle_id=vehicle.id
            ))

    for task in vehicle.maintenance_tasks:
        if not task.is_active:
            continue

        date_status = calculate_service_date_status(task.next_due_date)
        mileage_status = calculate_service_mileage_status(vehicle.mileage, task.next_due_mileage)
        final_status = get_worse_status(date_status, mileage_status)

        if final_status == "ok":
            continue

        label_parts = [f"Serwis: {task.name}", vehicle_name]

        if task.next_due_date:
            label_parts.append(f"do {task.next_due_date.strftime('%d.%m.%Y')}")

        if task.next_due_mileage is not None:
            label_parts.append(f"lub {task.next_due_mileage} km")

        db.session.add(Alert(
            label=" • ".join(label_parts),
            date=task.next_due_date,
            level=final_status,
            vehicle_id=vehicle.id
        ))


def refresh_all_alerts():
    vehicles = Vehicle.query.all()

    for vehicle in vehicles:
        refresh_vehicle_alerts(vehicle)

    db.session.commit()