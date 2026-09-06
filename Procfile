web: DJANGO_SETTINGS_MODULE=dynamicworkspace.production gunicorn -c gunicorn.conf.py dynamicworkspace.wsgi:application
scheduler: DJANGO_SETTINGS_MODULE=dynamicworkspace.production python manage.py process_schedule_ticks --loop --interval 60
watch: DJANGO_SETTINGS_MODULE=dynamicworkspace.production python manage.py process_watch_intake --loop --interval 60
