from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.security import generate_password_hash

from app import db
from app.models import User

users_bp = Blueprint("users", __name__, url_prefix="/users")

ROLE_CHOICES = [
    ("admin", "Administrator"),
    ("manager", "Menedżer floty"),
    ("operator", "Operator"),
    ("viewer", "Podgląd"),
]

STATUS_CHOICES = [
    ("active", "Aktywny"),
    ("blocked", "Tymczasowo zablokowany"),
    ("deactivated", "Dezaktywowany"),
    ("pending", "Oczekuje na aktywację"),
]

ACTIVITY_MODE_CHOICES = [
    ("unlimited", "Nieograniczony"),
    ("temporary", "Tymczasowy"),
]

MODULE_CHOICES = [
    ("dashboard", "Dashboard"),
    ("vehicles", "Pojazdy"),
    ("documents", "Dokumenty"),
    ("maintenance", "Serwis"),
    ("fuel_cards", "Karty paliwowe"),
    ("costs", "Koszty"),
    ("alerts", "Alerty"),
    ("users", "Użytkownicy"),
    ("settings", "Ustawienia systemu"),
    ("backup", "Backup / eksport"),
]

OPERATION_CHOICES = [
    ("view", "Podgląd danych"),
    ("create", "Dodawanie"),
    ("edit", "Edycja"),
    ("delete", "Usuwanie"),
    ("export", "Eksport"),
    ("manage_users", "Zarządzanie użytkownikami"),
]

SCOPE_CHOICES = [
    ("all", "Wszystkie pojazdy"),
    ("assigned", "Tylko przypisane"),
    ("departments", "Wybrane działy"),
    ("readonly", "Tylko odczyt"),
]

SENSITIVE_CHOICES = [
    ("costs", "Widok kosztów"),
    ("documents", "Widok dokumentów"),
    ("service", "Dane serwisowe"),
    ("fuel_cards", "Dane kart paliwowych"),
    ("administrative", "Dane administracyjne"),
]

ROLE_PRESETS = {
    "admin": {
        "modules": [key for key, _ in MODULE_CHOICES],
        "operations": [key for key, _ in OPERATION_CHOICES],
        "scope": "all",
        "sensitive": [key for key, _ in SENSITIVE_CHOICES],
    },
    "manager": {
        "modules": ["dashboard", "vehicles", "documents", "maintenance", "fuel_cards", "costs", "alerts"],
        "operations": ["view", "create", "edit", "export"],
        "scope": "all",
        "sensitive": ["costs", "documents", "service", "fuel_cards"],
    },
    "operator": {
        "modules": ["dashboard", "vehicles", "documents", "maintenance", "fuel_cards", "alerts"],
        "operations": ["view", "create", "edit"],
        "scope": "assigned",
        "sensitive": ["documents", "service", "fuel_cards"],
    },
    "viewer": {
        "modules": ["dashboard", "vehicles", "documents", "maintenance", "fuel_cards", "alerts"],
        "operations": ["view", "export"],
        "scope": "readonly",
        "sensitive": ["documents"],
    },
}


def require_admin():
    if not current_user.is_authenticated:
        abort(401)
    if not getattr(current_user, "can_manage_users", False):
        abort(403)


def parse_date(value: str | None):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def get_form_payload(form):
    role = (form.get("role") or "viewer").strip().lower()
    preset = ROLE_PRESETS.get(role, ROLE_PRESETS["viewer"])

    modules = form.getlist("modules") or list(preset["modules"])
    operations = form.getlist("operations") or list(preset["operations"])
    sensitive = form.getlist("sensitive_permissions") or list(preset["sensitive"])
    access_scope = (form.get("access_scope") or preset["scope"]).strip().lower()

    payload = {
        "full_name": (form.get("full_name") or "").strip(),
        "username": (form.get("username") or "").strip(),
        "email": (form.get("email") or "").strip(),
        "department": (form.get("department") or "").strip(),
        "notes": (form.get("notes") or "").strip(),
        "role": role,
        "status": (form.get("status") or "pending").strip().lower(),
        "activity_mode": (form.get("activity_mode") or "unlimited").strip().lower(),
        "active_from": parse_date(form.get("active_from")),
        "active_to": parse_date(form.get("active_to")),
        "blocked_reason": (form.get("blocked_reason") or "").strip(),
        "permissions_modules": ",".join(dict.fromkeys(modules)),
        "permissions_operations": ",".join(dict.fromkeys(operations)),
        "access_scope": access_scope,
        "sensitive_permissions": ",".join(dict.fromkeys(sensitive)),
    }
    return payload


def validate_user_payload(payload, user_id=None):
    errors = []

    if not payload["full_name"]:
        errors.append("Podaj nazwę użytkownika.")
    if not payload["username"]:
        errors.append("Podaj login użytkownika.")
    if payload["email"] and "@" not in payload["email"]:
        errors.append("Adres e-mail ma nieprawidłowy format.")

    existing_username = User.query.filter(User.username == payload["username"])
    if user_id:
        existing_username = existing_username.filter(User.id != user_id)
    if existing_username.first():
        errors.append("Użytkownik o takim loginie już istnieje.")

    if payload["email"]:
        existing_email = User.query.filter(User.email == payload["email"])
        if user_id:
            existing_email = existing_email.filter(User.id != user_id)
        if existing_email.first():
            errors.append("Użytkownik o takim adresie e-mail już istnieje.")

    if payload["activity_mode"] == "temporary":
        if not payload["active_from"]:
            errors.append("Dla konta tymczasowego ustaw datę początku aktywności.")
        if payload["active_to"] and payload["active_from"] and payload["active_to"] < payload["active_from"]:
            errors.append("Data końcowa nie może być wcześniejsza niż data początkowa.")
    else:
        payload["active_from"] = None
        payload["active_to"] = None

    return errors


@users_bp.context_processor
def inject_user_ui_context():
    return {
        "role_choices": ROLE_CHOICES,
        "status_choices": STATUS_CHOICES,
        "activity_mode_choices": ACTIVITY_MODE_CHOICES,
        "module_choices": MODULE_CHOICES,
        "operation_choices": OPERATION_CHOICES,
        "scope_choices": SCOPE_CHOICES,
        "sensitive_choices": SENSITIVE_CHOICES,
    }


@users_bp.route("/")
@login_required
def list_users():
    require_admin()

    q = (request.args.get("q") or "").strip()
    selected_status = (request.args.get("status") or "").strip().lower()
    selected_role = (request.args.get("role") or "").strip().lower()

    query = User.query

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                User.full_name.ilike(like),
                User.username.ilike(like),
                User.email.ilike(like),
                User.department.ilike(like),
            )
        )

    if selected_status:
        query = query.filter(User.status == selected_status)

    if selected_role:
        query = query.filter(User.role == selected_role)

    users = query.order_by(User.created_at.desc(), User.id.desc()).all()

    stats = {
        "all": User.query.count(),
        "active": User.query.filter_by(status="active").count(),
        "pending": User.query.filter_by(status="pending").count(),
        "blocked": User.query.filter_by(status="blocked").count(),
        "deactivated": User.query.filter_by(status="deactivated").count(),
    }

    return render_template(
        "users/list.html",
        users=users,
        stats=stats,
        filters={"q": q, "status": selected_status, "role": selected_role},
    )


@users_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_user():
    require_admin()

    form_data = {
        "status": "pending",
        "role": "viewer",
        "activity_mode": "unlimited",
        **ROLE_PRESETS["viewer"],
    }

    if request.method == "POST":
        payload = get_form_payload(request.form)
        errors = validate_user_payload(payload)

        if errors:
            for error in errors:
                flash(error, "error")
            form_data.update(payload)
            return render_template("users/form.html", mode="create", user=None, form_data=form_data)

        user = User(
            full_name=payload["full_name"],
            username=payload["username"],
            email=payload["email"] or None,
            department=payload["department"] or None,
            notes=payload["notes"] or None,
            role=payload["role"],
            status=payload["status"],
            activity_mode=payload["activity_mode"],
            active_from=payload["active_from"],
            active_to=payload["active_to"],
            blocked_reason=payload["blocked_reason"] or None,
            permissions_modules=payload["permissions_modules"],
            permissions_operations=payload["permissions_operations"],
            access_scope=payload["access_scope"],
            sensitive_permissions=payload["sensitive_permissions"],
            invited_at=datetime.utcnow() if payload["status"] == "pending" else None,
            created_by_user_id=current_user.id,
            password_hash="",
            is_active_user=True,
        )
        db.session.add(user)
        db.session.commit()
        flash("Użytkownik został utworzony. Konto oczekuje na aktywację lub dalszą konfigurację.", "success")
        return redirect(url_for("users.user_detail", user_id=user.id))

    return render_template("users/form.html", mode="create", user=None, form_data=form_data)


@users_bp.route("/<int:user_id>")
@login_required
def user_detail(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    return render_template("users/detail.html", user=user)


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        payload = get_form_payload(request.form)
        errors = validate_user_payload(payload, user_id=user.id)

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("users/form.html", mode="edit", user=user, form_data=payload)

        user.full_name = payload["full_name"]
        user.username = payload["username"]
        user.email = payload["email"] or None
        user.department = payload["department"] or None
        user.notes = payload["notes"] or None
        user.role = payload["role"]
        user.status = payload["status"]
        user.activity_mode = payload["activity_mode"]
        user.active_from = payload["active_from"]
        user.active_to = payload["active_to"]
        user.blocked_reason = payload["blocked_reason"] or None
        user.permissions_modules = payload["permissions_modules"]
        user.permissions_operations = payload["permissions_operations"]
        user.access_scope = payload["access_scope"]
        user.sensitive_permissions = payload["sensitive_permissions"]
        if user.status == "active" and not user.activated_at:
            user.activated_at = datetime.utcnow()
        db.session.commit()
        flash("Dane użytkownika zostały zaktualizowane.", "success")
        return redirect(url_for("users.user_detail", user_id=user.id))

    form_data = {
        "full_name": user.full_name,
        "username": user.username,
        "email": user.email,
        "department": user.department,
        "notes": user.notes,
        "role": user.role,
        "status": user.status,
        "activity_mode": user.activity_mode,
        "active_from": user.active_from.isoformat() if user.active_from else "",
        "active_to": user.active_to.isoformat() if user.active_to else "",
        "blocked_reason": user.blocked_reason,
        "modules": user.permissions_modules_list,
        "operations": user.permissions_operations_list,
        "access_scope": user.access_scope,
        "sensitive_permissions": user.sensitive_permissions_list,
    }
    return render_template("users/form.html", mode="edit", user=user, form_data=form_data)


@users_bp.route("/<int:user_id>/block", methods=["POST"])
@login_required
def block_user(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Nie możesz zablokować własnego konta z poziomu tego panelu.", "warning")
        return redirect(request.referrer or url_for("users.list_users"))

    user.status = "blocked"
    user.blocked_reason = (request.form.get("blocked_reason") or "Zablokowano ręcznie z panelu.").strip()
    db.session.commit()
    flash("Użytkownik został zablokowany.", "success")
    return redirect(request.referrer or url_for("users.list_users"))


@users_bp.route("/<int:user_id>/unblock", methods=["POST"])
@login_required
def unblock_user(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    user.status = "active"
    user.blocked_reason = None
    if not user.activated_at:
        user.activated_at = datetime.utcnow()
    db.session.commit()
    flash("Użytkownik został odblokowany.", "success")
    return redirect(request.referrer or url_for("users.list_users"))


@users_bp.route("/<int:user_id>/deactivate", methods=["POST"])
@login_required
def deactivate_user(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Nie możesz dezaktywować własnego konta z poziomu tego panelu.", "warning")
        return redirect(request.referrer or url_for("users.list_users"))

    user.status = "deactivated"
    user.is_active_user = False
    db.session.commit()
    flash("Konto zostało dezaktywowane.", "success")
    return redirect(request.referrer or url_for("users.list_users"))


@users_bp.route("/<int:user_id>/activate", methods=["POST"])
@login_required
def activate_user(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    user.status = "active"
    user.is_active_user = True
    user.activated_at = user.activated_at or datetime.utcnow()
    db.session.commit()
    flash("Konto zostało aktywowane.", "success")
    return redirect(request.referrer or url_for("users.list_users"))


@users_bp.route("/<int:user_id>/send-activation", methods=["POST"])
@login_required
def send_activation(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    user.status = "pending"
    user.invited_at = datetime.utcnow()
    db.session.commit()
    flash("Zaktualizowano status i zapisano nowe wysłanie linku aktywacyjnego. Logikę maila można podpiąć później.", "success")
    return redirect(request.referrer or url_for("users.user_detail", user_id=user.id))


@users_bp.route("/<int:user_id>/reset-password", methods=["POST"])
@login_required
def reset_password(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)

    temp_password = f"Fleet{user.id:03d}!{date.today().day:02d}"
    user.password_hash = generate_password_hash(temp_password)
    user.reset_requested_at = datetime.utcnow()
    user.status = "active"
    user.is_active_user = True
    user.activated_at = user.activated_at or datetime.utcnow()
    db.session.commit()

    flash(
        f"Hasło zostało zresetowane. Tymczasowe hasło demonstracyjne: {temp_password}. Później podepnij mail lub token resetujący.",
        "warning",
    )
    return redirect(request.referrer or url_for("users.user_detail", user_id=user.id))
