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
        label = (
            f"OC po terminie — {vehicle_name}"
            if oc_status == "danger"
            else f"Kończy się OC — {vehicle_name}"
        )
        db.session.add(Alert(
            label=label,
            date=vehicle.oc_date,
            level=oc_status,
            vehicle_id=vehicle.id
        ))

    inspection_status = calculate_status(vehicle.inspection_date)
    if inspection_status != "ok":
        label = (
            f"Przegląd po terminie — {vehicle_name}"
            if inspection_status == "danger"
            else f"Kończy się przegląd — {vehicle_name}"
        )
        db.session.add(Alert(
            label=label,
            date=vehicle.inspection_date,
            level=inspection_status,
            vehicle_id=vehicle.id
        ))

    for card in vehicle.fuel_cards:
        card_status = calculate_status(card.expiry)
        if card_status != "ok":
            station = card.station or "Karta paliwowa"
            last4 = card.number[-4:] if card.number and len(card.number) >= 4 else (card.number or "")

            label = (
                f"{station} • karta {last4} po terminie — {vehicle_name}"
                if card_status == "danger"
                else f"Kończy się {station} • karta {last4} — {vehicle_name}"
            )

            db.session.add(Alert(
                label=label,
                date=card.expiry,
                level=card_status,
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

        label_parts = []
        if final_status == "danger":
            label_parts.append(f"Serwis pilny: {task.name}")
        else:
            label_parts.append(f"Zbliża się serwis: {task.name}")

        label_parts.append(vehicle_name)

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