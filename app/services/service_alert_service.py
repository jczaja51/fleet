from app.models import Vehicle, Alert
from app.utils import (
    calculate_service_date_status,
    calculate_service_mileage_status,
    get_worse_status,
)


def refresh_service_alerts():
    for vehicle in Vehicle.query.all():
        for task in vehicle.service_tasks:
            if not task.is_active:
                continue

            date_status = calculate_service_date_status(task.next_due_date)
            mileage_status = calculate_service_mileage_status(vehicle.mileage, task.next_due_mileage)

            final_status = get_worse_status(date_status, mileage_status)

            if final_status == "ok":
                continue

            parts = [task.name]

            if task.next_due_date:
                parts.append(f"termin: {task.next_due_date}")

            if task.next_due_mileage:
                parts.append(f"przebieg: {task.next_due_mileage} km")

            label = " | ".join(parts)

            existing = Alert.query.filter_by(
                vehicle_id=vehicle.id,
                label=label
            ).first()

            if not existing:
                alert = Alert(
                    label=label,
                    date=task.next_due_date,
                    level=final_status,
                    vehicle_id=vehicle.id
                )
                db.session.add(alert)

    db.session.commit()