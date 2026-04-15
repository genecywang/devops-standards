FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY openclaw_foundation/ ./openclaw_foundation/
COPY alert_auto_investigator/ ./alert_auto_investigator/

RUN python -m pip install --no-cache-dir \
    ./openclaw_foundation \
    ./alert_auto_investigator

RUN useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

CMD ["python", "-m", "alert_auto_investigator"]
