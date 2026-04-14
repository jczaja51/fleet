import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

from app.extensions import csrf

load_dotenv()

db = SQLAlchemy()


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def migrate_plaintext_fuel_card_pins():
    from app.models import FuelCard

    cards = FuelCard.query.filter(FuelCard.pin.isnot(None)).all()
    changed = False

    for card in cards:
        raw_pin = (card.pin or "").strip()
        if not raw_pin:
            card.pin = None
            changed = True
            continue

        if raw_pin.startswith(("scrypt:", "pbkdf2:")):
            continue

        card.pin = generate_password_hash(raw_pin)
        changed = True

    if changed:
        db.session.commit()


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///fleet.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", "app/static/uploads/documents")
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", os.urandom(32).hex())
    app.config["WTF_CSRF_TIME_LIMIT"] = None
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = _as_bool(os.getenv("SESSION_COOKIE_SECURE"), default=False)
    app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SECURE"] = _as_bool(os.getenv("REMEMBER_COOKIE_SECURE"), default=False)
    app.config["REMEMBER_COOKIE_SAMESITE"] = os.getenv("REMEMBER_COOKIE_SAMESITE", "Lax")

    db.init_app(app)
    csrf.init_app(app)

    from app.main import main_bp
    app.register_blueprint(main_bp)

    from app.fuel_cards import fuel_bp
    app.register_blueprint(fuel_bp)

    from app.vehicles import vehicles_bp
    app.register_blueprint(vehicles_bp)

    from app.documents import documents_bp
    app.register_blueprint(documents_bp)

    from app.maintenance.routes import maintenance_bp
    app.register_blueprint(maintenance_bp)

    with app.app_context():
        from app import models
        db.create_all()
        migrate_plaintext_fuel_card_pins()

    return app