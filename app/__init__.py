import os

from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text as sql_text
from werkzeug.security import generate_password_hash

from app.extensions import csrf, login_manager

load_dotenv()

db = SQLAlchemy()


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def ensure_user_columns():
    columns_sql = {
        "full_name": "ALTER TABLE users ADD COLUMN full_name VARCHAR(160)",
        "email": "ALTER TABLE users ADD COLUMN email VARCHAR(160)",
        "role": "ALTER TABLE users ADD COLUMN role VARCHAR(32) DEFAULT 'viewer' NOT NULL",
        "department": "ALTER TABLE users ADD COLUMN department VARCHAR(160)",
        "notes": "ALTER TABLE users ADD COLUMN notes TEXT",
        "status": "ALTER TABLE users ADD COLUMN status VARCHAR(32) DEFAULT 'active' NOT NULL",
        "activity_mode": "ALTER TABLE users ADD COLUMN activity_mode VARCHAR(32) DEFAULT 'unlimited' NOT NULL",
        "active_from": "ALTER TABLE users ADD COLUMN active_from DATE",
        "active_to": "ALTER TABLE users ADD COLUMN active_to DATE",
        "last_login_at": "ALTER TABLE users ADD COLUMN last_login_at DATETIME",
        "invited_at": "ALTER TABLE users ADD COLUMN invited_at DATETIME",
        "activated_at": "ALTER TABLE users ADD COLUMN activated_at DATETIME",
        "reset_requested_at": "ALTER TABLE users ADD COLUMN reset_requested_at DATETIME",
        "created_by_user_id": "ALTER TABLE users ADD COLUMN created_by_user_id INTEGER",
        "blocked_reason": "ALTER TABLE users ADD COLUMN blocked_reason TEXT",
        "permissions_modules": "ALTER TABLE users ADD COLUMN permissions_modules TEXT",
        "permissions_operations": "ALTER TABLE users ADD COLUMN permissions_operations TEXT",
        "access_scope": "ALTER TABLE users ADD COLUMN access_scope VARCHAR(32) DEFAULT 'readonly' NOT NULL",
        "sensitive_permissions": "ALTER TABLE users ADD COLUMN sensitive_permissions TEXT",
    }

    existing = {row[1] for row in db.session.execute(sql_text("PRAGMA table_info(users)")).fetchall()}

    for column_name, statement in columns_sql.items():
        if column_name not in existing:
            db.session.execute(sql_text(statement))

    db.session.commit()

    db.session.execute(sql_text("UPDATE users SET role = 'admin' WHERE username = :username AND (role IS NULL OR role = '' OR role = 'viewer')"), {"username": os.getenv("ADMIN_USERNAME", "admin").strip()})
    db.session.execute(sql_text("UPDATE users SET full_name = username WHERE full_name IS NULL OR TRIM(full_name) = ''"))
    db.session.execute(sql_text("UPDATE users SET status = 'active' WHERE status IS NULL OR TRIM(status) = ''"))
    db.session.execute(sql_text("UPDATE users SET activity_mode = 'unlimited' WHERE activity_mode IS NULL OR TRIM(activity_mode) = ''"))
    db.session.execute(sql_text("UPDATE users SET access_scope = 'readonly' WHERE access_scope IS NULL OR TRIM(access_scope) = ''"))
    db.session.execute(sql_text("UPDATE users SET permissions_modules = 'dashboard,vehicles,documents,maintenance,fuel_cards,alerts,users,settings,backup' WHERE role = 'admin' AND (permissions_modules IS NULL OR TRIM(permissions_modules) = '')"))
    db.session.execute(sql_text("UPDATE users SET permissions_operations = 'view,create,edit,delete,export,manage_users' WHERE role = 'admin' AND (permissions_operations IS NULL OR TRIM(permissions_operations) = '')"))
    db.session.execute(sql_text("UPDATE users SET sensitive_permissions = 'costs,documents,service,fuel_cards,administrative' WHERE role = 'admin' AND (sensitive_permissions IS NULL OR TRIM(sensitive_permissions) = '')"))
    db.session.commit()


def ensure_fuel_card_columns():
    columns_sql = {
        "pin_hash": "ALTER TABLE fuel_cards ADD COLUMN pin_hash VARCHAR(255)",
    }

    existing = {row[1] for row in db.session.execute(sql_text("PRAGMA table_info(fuel_cards)")).fetchall()}

    for column_name, statement in columns_sql.items():
        if column_name not in existing:
            db.session.execute(sql_text(statement))

    db.session.commit()


def migrate_plaintext_fuel_card_pins():
    from app.models import FuelCard

    cards = FuelCard.query.filter(
        db.or_(FuelCard.pin.isnot(None), FuelCard.pin_hash.isnot(None))
    ).all()
    changed = False

    for card in cards:
        raw_pin = (card.pin or "").strip()
        raw_pin_hash = (card.pin_hash or "").strip()

        if not raw_pin and not raw_pin_hash:
            if card.pin is not None or card.pin_hash is not None:
                card.pin = None
                card.pin_hash = None
                changed = True
            continue

        if raw_pin.startswith(("scrypt:", "pbkdf2:")):
            if card.pin_hash != raw_pin or card.pin is not None:
                card.pin_hash = raw_pin
                card.pin = None
                changed = True
            continue

        if raw_pin and not raw_pin_hash:
            card.pin_hash = generate_password_hash(raw_pin)
            changed = True

    if changed:
        db.session.commit()


def ensure_default_admin():
    from app.models import User

    username = os.getenv("ADMIN_USERNAME", "admin").strip()
    password = os.getenv("ADMIN_PASSWORD", "admin123").strip()

    user = User.query.filter_by(username=username).first()
    if user:
        return

    admin = User(
        full_name="Administrator systemu",
        username=username,
        password_hash=generate_password_hash(password),
        role="admin",
        status="active",
        activity_mode="unlimited",
        is_active_user=True,
        permissions_modules="dashboard,vehicles,documents,maintenance,fuel_cards,costs,alerts,users,settings,backup",
        permissions_operations="view,create,edit,delete,export,manage_users",
        access_scope="all",
        sensitive_permissions="costs,documents,service,fuel_cards,administrative",
    )
    db.session.add(admin)
    db.session.commit()


@login_manager.user_loader
def load_user(user_id):
    from app.models import User

    return User.query.get(int(user_id))


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///fleet.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", "app/static/uploads/documents")
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", os.urandom(32).hex())
    app.config["WTF_CSRF_TIME_LIMIT"] = 3600

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = _as_bool(os.getenv("SESSION_COOKIE_SECURE"), default=False)
    app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")

    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SECURE"] = _as_bool(os.getenv("REMEMBER_COOKIE_SECURE"), default=False)
    app.config["REMEMBER_COOKIE_SAMESITE"] = os.getenv("REMEMBER_COOKIE_SAMESITE", "Lax")

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;"
        )
        return response

    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    from app.main import main_bp
    app.register_blueprint(main_bp)

    from app.users import users_bp
    app.register_blueprint(users_bp)

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
        ensure_user_columns()
        ensure_fuel_card_columns()
        ensure_default_admin()
        migrate_plaintext_fuel_card_pins()

    return app