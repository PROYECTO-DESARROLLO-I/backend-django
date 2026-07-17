FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Los drivers de Postgres usados en requirements.txt (psycopg-binary,
# psycopg2-binary) son wheels autocontenidos que ya empaquetan libpq,
# por lo que no se necesitan dependencias de sistema (libpq-dev/gcc)
# para instalarlos ni para ejecutarlos.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ALLOWED_HOSTS y SECRET_KEY solo se usan aqui para satisfacer los guards de
# config/settings/production.py durante el build; collectstatic no necesita
# valores reales (no toca DB ni ALLOWED_HOSTS). En runtime se sobreescriben
# con los valores reales inyectados via env_file (.env.production).
RUN ENVIRONMENT=production ALLOWED_HOSTS=build-placeholder SECRET_KEY=build-time-placeholder-not-used-at-runtime \
    python manage.py collectstatic --noinput

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
