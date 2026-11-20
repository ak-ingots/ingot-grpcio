# The echo, as an application is installed: the wheel of ingot-grpcio that
# `make all` builds, with its dependencies at the versions of uv.lock, which
# `make perf-build` exports next to it; then the code of the example. Built
# from the root of the repository, on the Python of ECHO_PYTHON: the stand's
# for a run, the newest of PYTHONS for `make perf-smoke`.
ARG PYTHON
FROM python:${PYTHON}-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
COPY dist/ /dist/
RUN uv pip install --system --no-cache -r /dist/echo-requirements.txt \
    "$(ls /dist/*.whl)"
WORKDIR /srv
COPY examples/echo/echo/ echo/
COPY examples/echo/app/ app/
ENTRYPOINT ["python", "-m"]
CMD ["app", "components", "run-forever", "--component", "grpc.servers.default"]
