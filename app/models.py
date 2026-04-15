from datetime import datetime

from sqlalchemy import event

from app import db
from app.services.storage_service import delete_relative_static_file, delete_vehicle_storage_dir


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    brand = db.Column(db.String(80), nullable=True)
    model = db.Column(db.String(80), nullable=True)
    category = db.Column(db.String(120), nullable=True)
    production_year = db.Column(db.Integer, nullable=True)
    vin = db.Column(db.String(32), nullable=True)
    assigned_driver = db.Column(db.String(120), nullable=True)
    tachograph_expiry_date = db.Column(db.Date, nullable=True)

    registration = db.Column(db.String(20), nullable=False, index=True, unique=True)
    mileage = db.Column(db.Integer, nullable=True)
    type = db.Column(db.String(50), nullable=True)

    image = db.Column(db.String(255), nullable=True)
    oc_date = db.Column(db.Date, nullable=True)
    inspection_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def display_name(self):
        if self.brand and self.model:
            return f"{self.brand} {self.model}"
        return self.name

    def sync_name(self):
        if self.brand and self.model:
            self.name = f"{self.brand} {self.model}"
        elif not self.name and self.registration:
            self.name = self.registration

    @property
    def requires_tachograph(self):
        return self.category in {
            "Samochód ciężarowy powyżej 3,5 t DMC",
            "Autobus",
        }

    def __repr__(self):
        return f"<Vehicle {self.display_name} ({self.registration})>"


class MaintenanceTask(db.Model):
    __tablename__ = "maintenance_tasks"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    last_service_date = db.Column(db.Date, nullable=True)
    last_service_mileage = db.Column(db.Integer, nullable=True)

    interval_days = db.Column(db.Integer, nullable=True)
    interval_km = db.Column(db.Integer, nullable=True)

    next_due_date = db.Column(db.Date, nullable=True)
    next_due_mileage = db.Column(db.Integer, nullable=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)

    vehicle = db.relationship(
        "Vehicle",
        backref=db.backref("maintenance_tasks", lazy=True, cascade="all, delete-orphan", passive_deletes=True),
    )

    def __repr__(self):
        return f"<MaintenanceTask {self.name}>"


class FuelCard(db.Model):
    __tablename__ = "fuel_cards"

    id = db.Column(db.Integer, primary_key=True)
    station = db.Column(db.String(60), nullable=True)
    number = db.Column(db.String(4), nullable=True)
    pin = db.Column(db.String(6), nullable=True)
    expiry = db.Column(db.Date, nullable=True)

    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=True)

    vehicle = db.relationship(
        "Vehicle",
        backref=db.backref("fuel_cards", lazy=True, cascade="all, delete-orphan", passive_deletes=True),
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def has_pin(self):
        return bool(self.pin)

    @property
    def masked_number(self):
        return f"•• {self.number}" if self.number else "••••"

    def __repr__(self):
        return f"<FuelCard {self.station} {self.number}>"

class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(255), nullable=True)
    date = db.Column(db.Date, nullable=True)
    level = db.Column(db.String(20), nullable=True)

    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=True)

    vehicle = db.relationship(
        "Vehicle",
        backref=db.backref("alerts", lazy=True, cascade="all, delete-orphan", passive_deletes=True),
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Alert {self.label}>"


class VehicleDocument(db.Model):
    __tablename__ = "vehicle_documents"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.String(100), nullable=False, index=True)
    file_path = db.Column(db.String(255), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)

    vehicle = db.relationship(
        "Vehicle",
        backref=db.backref("documents", lazy=True, cascade="all, delete-orphan", passive_deletes=True),
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<VehicleDocument {self.name}>"


@event.listens_for(VehicleDocument, "after_delete")
def cleanup_document_file(mapper, connection, target):
    delete_relative_static_file(target.file_path)


@event.listens_for(Vehicle, "after_delete")
def cleanup_vehicle_storage(mapper, connection, target):
    delete_relative_static_file(target.image)
    delete_vehicle_storage_dir(target.registration)