# The floor of the echo: its service on grpcio alone, at the versions of the
# echo of the role.
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
