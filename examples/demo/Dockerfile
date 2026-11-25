# PYTHON: the stand's for a run, the newest of PYTHONS for `make perf-smoke`.
ARG PYTHON
FROM python:${PYTHON}-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
COPY dist/ /dist/
RUN uv pip install --system --no-cache -r /dist/echo-requirements.txt \
    "$(ls /dist/*.whl)"
WORKDIR /srv
# the root of the demo is that of the application, its modules on sys.path
COPY examples/demo/ ./
ENTRYPOINT ["python", "/srv"]
CMD ["components", "run-forever", "--component", "grpc.servers.default"]
