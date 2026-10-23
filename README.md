# ingot-grpcio

[![ci](https://github.com/ak-ingots/ingot-grpcio/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ak-ingots/ingot-grpcio/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/ak-ingots/ingot-grpcio/blob/main/LICENSE)

<!-- Links must be absolute: this README also renders on PyPI. -->

Integration of grpcio, the gRPC library of Google, into Ingots applications:
gRPC servers and clients on its API. An addon of
[Ingots](https://github.com/ak-ingots/ingots).

```python
import ingot_grpcio


class AppProject(ingot_grpcio.Project):
    env_configs_prefix = "APP"
```

An application with other addons joins the configs, the settings and the
logging instead: `class AppConfigs(HttpConfigs, ingot_grpcio.Configs)`, and so
on, as the addon guide of Ingots shows. The configs of the addon are named
`GRPC_*`: `GRPC_LOGGING_LEVEL` sets the level of its logger, `ingot_grpcio`.

**Status:** pre-alpha. The skeleton of the addon: its project, configs,
settings and logging. Next, the servers and clients of grpcio, as components.

## Development

Requires [uv](https://docs.astral.sh/uv/) and `make`; uv fetches the
interpreters it needs.

```sh
make                 # the target list
make check           # everything CI runs: lint, test, coverage, wheel-test, cl-check
make format          # black
make all             # build the sdist and the wheel into dist/
```

- Every change users should know about adds a news fragment to `changelog.d/`
  (see [its README](https://github.com/ak-ingots/ingot-grpcio/blob/main/changelog.d/README.md)).
- A release is a pull request setting the version (`uv version X.Y.Z`) and
  collating the changelog (`make cl-build VERSION=X.Y.Z`), then the tag
  `vX.Y.Z` on `main`: the `release` workflow publishes the tested build to
  TestPyPI, then to PyPI. Run by hand, it rehearses on TestPyPI only.

## License

[Apache 2.0](https://github.com/ak-ingots/ingot-grpcio/blob/main/LICENSE).
