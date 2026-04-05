from datetime import datetime

from app import db


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    registration = db.Column(db.String(20), nullable=False)
    mileage = db.Column(db.Integer, nullable=True)
    type = db.Column(db.String(50), nullable=True)
    image = db.Column(db.String(255), nullable=True)
    oc_date = db.Column(db.Date, nullable=True)
    inspection_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Vehicle {self.name} ({self.registration})>"


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

    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)

    vehicle = db.relationship(
        "Vehicle",
        backref=db.backref("maintenance_tasks", lazy=True, cascade="all, delete-orphan")
    )

    def __repr__(self):
        return f"<MaintenanceTask {self.name}>"


class FuelCard(db.Model):
    __tablename__ = "fuel_cards"

    id = db.Column(db.Integer, primary_key=True)
    station = db.Column(db.String(100), nullable=True)
    number = db.Column(db.String(50), nullable=True)
    pin = db.Column(db.String(10), nullable=True)
    expiry = db.Column(db.Date, nullable=True)

    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=True)

    vehicle = db.relationship(
        "Vehicle",
        backref=db.backref("fuel_cards", lazy=True, cascade="all, delete-orphan")
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<FuelCard {self.station} {self.number}>"


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(255), nullable=True)
    date = db.Column(db.Date, nullable=True)
    level = db.Column(db.String(20), nullable=True)

    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=True)

    vehicle = db.relationship(
        "Vehicle",
        backref=db.backref("alerts", lazy=True, cascade="all, delete-orphan")
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Alert {self.label}>"


class VehicleDocument(db.Model):
    __tablename__ = "vehicle_documents"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(255), nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)

    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)

    vehicle = db.relationship(
        "Vehicle",
        backref=db.backref("documents", lazy=True, cascade="all, delete-orphan")
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<VehicleDocument {self.name}>"