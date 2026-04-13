FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY openclaw_foundation/ ./openclaw_foundation/
COPY self_service_copilot/ ./self_service_copilot/

RUN python -m pip install --no-cache-dir \
    ./openclaw_foundation \
    ./self_service_copilot

RUN useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

CMD ["python", "-m", "self_service_copilot.bot"]
