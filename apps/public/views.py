from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.public.services.contact import SUBJECT_CHOICES, submit_contact_message
from apps.public.services.page_context import public_page_context


def home(request):
    context = public_page_context("home")
    return render(request, "public/home.html", context)


def services(request):
    context = public_page_context("services")
    return render(request, "public/services.html", context)


def help_guide(request):
    context = public_page_context("help")
    return render(request, "public/help.html", context)


@require_http_methods(["GET", "POST"])
def contact(request):
    posted = {
        "full_name": "",
        "email": "",
        "company_name": "",
        "subject": "",
        "message": "",
    }
    errors: dict[str, list[str]] = {}

    if request.method == "POST":
        posted = {
            "full_name": request.POST.get("full_name", ""),
            "email": request.POST.get("email", ""),
            "company_name": request.POST.get("company_name", ""),
            "subject": request.POST.get("subject", ""),
            "message": request.POST.get("message", ""),
        }
        result = submit_contact_message(posted)
        if result.ok:
            messages.success(request, result.user_message)
            return redirect("public:contact")
        if result.errors:
            errors = result.errors
        messages.error(request, result.user_message or "No se pudo enviar el mensaje.")

    context = {
        **public_page_context("contact"),
        "posted": posted,
        "errors": errors,
        "subject_choices": SUBJECT_CHOICES,
    }
    return render(request, "public/contact.html", context)
