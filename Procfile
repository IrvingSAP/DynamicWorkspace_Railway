web: DJANGO_SETTINGS_MODULE=dynamicworkspace.production gunicorn -c gunicorn.conf.py dynamicworkspace.wsgi:application
release: DJANGO_SETTINGS_MODULE=dynamicworkspace.production python manage.py migrate --noinput
