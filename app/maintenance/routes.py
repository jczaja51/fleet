from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app import db
from app.models import Vehicle, MaintenanceTask
from app.utils import compute_next_service_date, compute_next_service_mileage

maintenance_bp = Blueprint("maintenance", __name__, url_prefix="/maintenance")


@maintenance_bp.route("/")
def list_tasks():
    tasks = MaintenanceTask.query.order_by(MaintenanceTask.id.desc()).all()
    return render_template("maintenance/list.html", tasks=tasks)


@maintenance_bp.route("/create", methods=["GET", "POST"])
def add_task():
    vehicles = Vehicle.query.order_by(Vehicle.name.asc()).all()

    if request.method == "POST":
        name = request.form.get("name")
        category = request.form.get("category")
        notes = request.form.get("notes")
        vehicle_id = request.form.get("vehicle_id")

        last_service_date_raw = request.form.get("last_service_date")
        last_service_mileage_raw = request.form.get("last_service_mileage")
        interval_days_raw = request.form.get("interval_days")
        interval_km_raw = request.form.get("interval_km")

        last_service_date = datetime.strptime(last_service_date_raw, "%Y-%m-%d").date() if last_service_date_raw else None
        last_service_mileage = int(last_service_mileage_raw) if last_service_mileage_raw else None
        interval_days = int(interval_days_raw) if interval_days_raw else None
        interval_km = int(interval_km_raw) if interval_km_raw else None

        task = MaintenanceTask(
            name=name,
            category=category,
            notes=notes,
            vehicle_id=int(vehicle_id),
            last_service_date=last_service_date,
            last_service_mileage=last_service_mileage,
            interval_days=interval_days,
            interval_km=interval_km,
        )

        task.next_due_date = compute_next_service_date(task.last_service_date, task.interval_days)
        task.next_due_mileage = compute_next_service_mileage(task.last_service_mileage, task.interval_km)

        db.session.add(task)
        db.session.commit()

        flash("Serwis został dodany.", "success")
        return redirect(url_for("maintenance.list_tasks"))

    return render_template("maintenance/create.html", vehicles=vehicles)


@maintenance_bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id):
    task = MaintenanceTask.query.get_or_404(task_id)
    vehicles = Vehicle.query.order_by(Vehicle.name.asc()).all()

    if request.method == "POST":
        task.name = request.form.get("name")
        task.category = request.form.get("category")
        task.notes = request.form.get("notes")
        task.vehicle_id = int(request.form.get("vehicle_id"))

        last_service_date_raw = request.form.get("last_service_date")
        last_service_mileage_raw = request.form.get("last_service_mileage")
        interval_days_raw = request.form.get("interval_days")
        interval_km_raw = request.form.get("interval_km")

        task.last_service_date = datetime.strptime(last_service_date_raw, "%Y-%m-%d").date() if last_service_date_raw else None
        task.last_service_mileage = int(last_service_mileage_raw) if last_service_mileage_raw else None
        task.interval_days = int(interval_days_raw) if interval_days_raw else None
        task.interval_km = int(interval_km_raw) if interval_km_raw else None
        task.is_active = request.form.get("is_active") == "1"

        task.next_due_date = compute_next_service_date(task.last_service_date, task.interval_days)
        task.next_due_mileage = compute_next_service_mileage(task.last_service_mileage, task.interval_km)

        db.session.commit()

        flash("Serwis został zaktualizowany.", "success")
        return redirect(url_for("maintenance.list_tasks"))

    return render_template("maintenance/edit.html", task=task, vehicles=vehicles)


@maintenance_bp.route("/<int:task_id>/delete", methods=["POST"])
def delete_task(task_id):
    task = MaintenanceTask.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()

    flash("Serwis został usunięty.", "success")
    return redirect(url_for("maintenance.list_tasks"))