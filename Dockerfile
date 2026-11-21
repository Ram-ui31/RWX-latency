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
COPY research/observations/ /app/research/observations/
COPY research/typed_settings/ /app/research/typed_settings/
COPY research/group_verifier/ /app/research/group_verifier/
COPY research/state_diff/choose.py research/state_diff/eligibility.py research/state_diff/compile_metadata.py /app/research/state_diff/
COPY selector.py run_candidate.py build-catalog.json /app/
COPY maps/source-index.json.gz /app/maps/source-index.json.gz
COPY tools/check_native.py /app/tools/check_native.py
RUN python -X faulthandler /app/tools/check_native.py
ENV RWX_OBSERVATIONS=/app/assets/observations.json.gz
RUN mkdir /app/assets && python /app/research/observations/build.py --source /app/pinned-source --catalog /app/build-catalog.json --output ${RWX_OBSERVATIONS}
RUN python /app/research/tail_verifier/calibrate.py --source /app/pinned-source --catalog /app/build-catalog.json --numbers 1224 --output /app/assets/verification-costs.json --timeout 60
ENV RWX_GROUP_VERIFY=1
ENV RWX_TYPED_SETTINGS=/app/assets/settings.json.gz
RUN python /app/research/typed_settings/build.py --source /app/pinned-source --catalog /app/build-catalog.json --output ${RWX_TYPED_SETTINGS}
ENV RWX_ARGUMENT_CONTRACTS=/app/assets/arguments.json.gz
RUN PYTHONHASHSEED=0 python /app/research/state_diff/compile_metadata.py --source /app/pinned-source --readers ${RWX_TYPED_SETTINGS} --index /app/maps/source-index.json.gz --output ${RWX_ARGUMENT_CONTRACTS}
RUN chmod -R a+rX /app
USER 65534:65534
ENTRYPOINT ["python3", "-B", "/app/run_candidate.py"]
