from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from app import db
from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        remember_me = bool(request.form.get("remember_me"))

        user = User.query.filter_by(username=username).first()

        if not user or not user.has_usable_password or not check_password_hash(user.password_hash, password):
            flash("Nieprawidłowy login lub hasło.", "error")
            return render_template("auth/login.html")

        if not user.can_login:
            flash(f"Konto nie może się teraz zalogować. Status: {user.effective_status_label.lower()}.", "warning")
            return render_template("auth/login.html")

        user.last_login_at = datetime.utcnow()
        db.session.commit()

        login_user(user, remember=remember_me)
        flash("Zalogowano pomyślnie.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Wylogowano.", "success")
    return redirect(url_for("auth.login"))
