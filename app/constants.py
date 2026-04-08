DOCUMENT_TYPE_LABELS = {
    "registration_certificate": "Dowód rejestracyjny",
    "oc_policy": "Polisa OC",
    "ac_policy": "AC",
    "lease_document": "Leasing",
    "inspection_document": "Przegląd",
    "tachograph_document": "Tachograf",
    "service_document": "Serwis",
    "other": "Inne",
}

ALLOWED_DOCUMENT_TYPES = tuple(DOCUMENT_TYPE_LABELS.keys())

TACHOGRAPH_CATEGORIES = {
    "Samochód ciężarowy powyżej 3,5 t DMC",
    "Autobus",
}