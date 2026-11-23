# The floor of the echo: its service on grpcio alone, at the versions of the
# echo of the role, dist/echo-requirements.txt of its tree, which
# `make perf-build` exports, and its contract, echo/v1 of the example; the
# code of the floor the stand's, its context `stand`. Built from the root of
# the tree, on the Python of ECHO_PYTHON, as the echo is.
ARG PYTHON
FROM python:${PYTHON}-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
COPY dist/echo-requirements.txt /dist/
RUN uv pip install --system --no-cache -r /dist/echo-requirements.txt
WORKDIR /srv
COPY examples/demo/echo/ echo/
COPY --from=stand bare/ bare/
ENTRYPOINT ["python", "-m", "bare"]
CMD ["50051"]
