from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///fleet.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = "app/static/uploads/documents"
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    app.config["SECRET_KEY"] = "dev-secret-key"

    db.init_app(app)

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

    return app