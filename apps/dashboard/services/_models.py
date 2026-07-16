from django.apps import apps as django_apps


def get_model_optional(app_label: str, model_name: str):
    try:
        return django_apps.get_model(app_label, model_name)
    except LookupError:
        return None
