FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
WORKDIR /app
COPY blast/ /app/blast/
COPY engine/ /app/engine/
COPY selector.py /app/selector.py
COPY maps/source-index.json.gz /app/maps/source-index.json.gz
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp RWX_SELECTION_MODE=hybrid
USER 65534:65534
ENTRYPOINT ["python3", "-u", "/app/selector.py"]
