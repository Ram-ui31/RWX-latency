FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp SKIP_INTEGRATION=0 RWX_SELECTION_MODE=adaptive
COPY requirements.lock /app/requirements.lock
RUN python -m pip install --no-cache-dir -r /app/requirements.lock
COPY tools/download_pinned_source.py /app/tools/download_pinned_source.py
RUN python /app/tools/download_pinned_source.py /app/pinned-source
COPY blast/ /app/blast/
COPY engine/ /app/engine/
COPY research/tail_verifier/ /app/research/tail_verifier/
COPY research/incremental_executor/ /app/research/incremental_executor/
COPY selector.py run_candidate.py build-catalog.json /app/
COPY maps/source-index.json.gz /app/maps/source-index.json.gz
COPY tools/check_native.py /app/tools/check_native.py
RUN python -X faulthandler /app/tools/check_native.py
RUN mkdir /app/assets && python -X faulthandler /app/research/incremental_executor/build.py --source /app/pinned-source --output /app/assets/base.pkl.gz
RUN python /app/research/incremental_executor/build_dependencies.py --source /app/pinned-source --capsule /app/assets/base.pkl.gz --output /app/assets/checkpoints.pkl.gz && rm /app/assets/base.pkl.gz /app/assets/base.pkl.gz.json
RUN python /app/research/tail_verifier/calibrate.py --source /app/pinned-source --catalog /app/build-catalog.json --numbers 1224 --output /app/assets/verification-costs.json --timeout 60
RUN chmod -R a+rX /app
USER 65534:65534
ENTRYPOINT ["python3", "-B", "/app/run_candidate.py"]
