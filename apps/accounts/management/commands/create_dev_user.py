from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import UserProfile
from apps.company.models import Company

User = get_user_model()


class Command(BaseCommand):
    help = "Crea compañía y usuario de desarrollo con perfil para probar el wizard de seguridad."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin")
        parser.add_argument("--password", default="Admin123!")
        parser.add_argument("--email", default="admin@acme.test")
        parser.add_argument("--company-short", default="ACME")
        parser.add_argument("--company-long", default="ACME Corporation")
        parser.add_argument(
            "--user-type",
            default=UserProfile.USER_ADMIN,
            choices=[UserProfile.USER_ADMIN, UserProfile.USER_SYSTEM, UserProfile.USER_FINAL],
        )

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        email = options["email"]
        company_short = options["company_short"]
        company_long = options["company_long"]
        user_type = options["user_type"]

        company, _ = Company.objects.get_or_create(
            name_short=company_short,
            defaults={"name_long": company_long, "is_active": True},
        )

        if User.objects.filter(username=username).exists():
            raise CommandError(f"El usuario '{username}' ya existe.")

        user = User(username=username, email=email, is_active=True)
        user.set_password(password)
        user._setup_company = company
        user._setup_user_type = user_type
        user.save()

        self.stdout.write(self.style.SUCCESS("Usuario de desarrollo creado."))
        self.stdout.write(f"  Compañía: {company.name_short}")
        self.stdout.write(f"  Usuario:  {username}")
        self.stdout.write(f"  Correo:   {email}")
        self.stdout.write(f"  Tipo:     {user_type}")
        self.stdout.write("  Login:    /ingresar/")
        self.stdout.write(
            "  Onboarding: correo (consola) -> QR 2FA -> /app/bienvenida/"
        )
