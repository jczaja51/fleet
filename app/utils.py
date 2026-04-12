from datetime import date, timedelta


DANGER_DAYS_THRESHOLD = 7
WARNING_DAYS_THRESHOLD = 30


def calculate_status(target_date):
    if not target_date:
        return "ok"

    today = date.today()
    diff = (target_date - today).days

    if diff < 0:
        return "danger"
    if diff <= DANGER_DAYS_THRESHOLD:
        return "danger"
    if diff <= WARNING_DAYS_THRESHOLD:
        return "warning"
    return "ok"


def calculate_service_date_status(next_due_date):
    if not next_due_date:
        return "ok"

    today = date.today()
    diff = (next_due_date - today).days

    if diff < 0:
        return "danger"
    if diff <= DANGER_DAYS_THRESHOLD:
        return "danger"
    if diff <= WARNING_DAYS_THRESHOLD:
        return "warning"
    return "ok"


def calculate_service_mileage_status(current_mileage, next_due_mileage):
    if current_mileage is None or next_due_mileage is None:
        return "ok"

    remaining = next_due_mileage - current_mileage

    if remaining < 0:
        return "danger"
    if remaining <= 300:
        return "danger"
    if remaining <= 1000:
        return "warning"
    return "ok"


def get_worse_status(status_a, status_b):
    levels = {"ok": 0, "warning": 1, "danger": 2}
    return status_a if levels[status_a] >= levels[status_b] else status_b


def compute_next_service_date(last_service_date, interval_days):
    if not last_service_date or not interval_days:
        return None
    return last_service_date + timedelta(days=interval_days)


def compute_next_service_mileage(last_service_mileage, interval_km):
    if last_service_mileage is None or not interval_km:
        return None
    return last_service_mileage + interval_km