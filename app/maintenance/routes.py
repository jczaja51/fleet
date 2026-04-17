from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.models import Vehicle, MaintenanceTask
from app.utils import compute_next_service_date, compute_next_service_mileage

maintenance_bp = Blueprint("maintenance", __name__, url_prefix="/maintenance")


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@maintenance_bp.route("/")
@login_required
def list_tasks():
    tasks = MaintenanceTask.query.order_by(MaintenanceTask.id.desc()).all()
    return render_template("maintenance/list.html", tasks=tasks)


@maintenance_bp.route("/create", methods=["GET", "POST"])
@login_required
def add_task():
    vehicles = Vehicle.query.order_by(Vehicle.name.asc()).all()

    if request.method == "POST":
        name = request.form.get("name")
        category = request.form.get("category")
        notes = request.form.get("notes")
        vehicle_id_raw = request.form.get("vehicle_id")

        last_service_date = parse_date(request.form.get("last_service_date"))
        last_service_mileage = parse_int(request.form.get("last_service_mileage"))
        interval_days = parse_int(request.form.get("interval_days"))
        interval_km = parse_int(request.form.get("interval_km"))

        if not vehicle_id_raw or not str(vehicle_id_raw).isdigit():
            flash("Wybierz poprawny pojazd.", "error")
            return render_template("maintenance/create.html", vehicles=vehicles)

        task = MaintenanceTask(
            name=name,
            category=category,
            notes=notes,
            vehicle_id=int(vehicle_id_raw),
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
@login_required
def edit_task(task_id):
    task = MaintenanceTask.query.get_or_404(task_id)
    vehicles = Vehicle.query.order_by(Vehicle.name.asc()).all()

    if request.method == "POST":
        vehicle_id_raw = request.form.get("vehicle_id")

        if not vehicle_id_raw or not str(vehicle_id_raw).isdigit():
            flash("Wybierz poprawny pojazd.", "error")
            return render_template("maintenance/edit.html", task=task, vehicles=vehicles)

        task.name = request.form.get("name")
        task.category = request.form.get("category")
        task.notes = request.form.get("notes")
        task.vehicle_id = int(vehicle_id_raw)
        task.last_service_date = parse_date(request.form.get("last_service_date"))
        task.last_service_mileage = parse_int(request.form.get("last_service_mileage"))
        task.interval_days = parse_int(request.form.get("interval_days"))
        task.interval_km = parse_int(request.form.get("interval_km"))
        task.is_active = request.form.get("is_active") == "1"

        task.next_due_date = compute_next_service_date(task.last_service_date, task.interval_days)
        task.next_due_mileage = compute_next_service_mileage(task.last_service_mileage, task.interval_km)

        db.session.commit()

        flash("Serwis został zaktualizowany.", "success")
        return redirect(url_for("maintenance.list_tasks"))

    return render_template("maintenance/edit.html", task=task, vehicles=vehicles)


@maintenance_bp.route("/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    task = MaintenanceTask.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()

    flash("Serwis został usunięty.", "success")
    return redirect(url_for("maintenance.list_tasks"))