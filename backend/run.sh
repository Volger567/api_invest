python manage.py makemigrations users market operations &&
python manage.py migrate &&

python manage.py init &&
python manage.py collectstatic --noinput &&
gunicorn core.wsgi:application --bind 0.0.0.0:9999

tail -f