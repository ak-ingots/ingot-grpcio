# ingot-grpcio

[![ci](https://github.com/ak-ingots/ingot-grpcio/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ak-ingots/ingot-grpcio/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/ak-ingots/ingot-grpcio/blob/main/LICENSE)

<!-- Links must be absolute: this README also renders on PyPI. -->

Integration of grpcio, the gRPC library of Google, into Ingots applications:
gRPC servers and clients on its API. An addon of
[Ingots](https://github.com/ak-ingots/ingots).

## Install

```sh
uv add ingot-grpcio
```

```python
import ingot_grpcio


class AppProject(ingot_grpcio.GrpcProject):
    env_configs_prefix = "APP"
```

An application with other addons joins the configs, the settings and the
logging instead: `class AppConfigs(HttpConfigs, GrpcConfigs)` with `GrpcConfigs`
from `ingot_grpcio.settings.configs`, and so on, as the addon guide of Ingots
shows. The configs of the addon are named
`GRPC_*`: `GRPC_LOGGING_LEVEL` sets the level of its logger, `ingot_grpcio`.

## Servers

`GrpcProject` holds `grpc`, a unit of three: `grpc.api`, the registry of
the services; `grpc.bindings`, which of them each server serves; and
`grpc.servers`, the servers, each a component. A service names its
contract in a `.proto` file and the class implementing it, a servicer, in
a slot of the API:

```python
import typing as t

from ingot_grpcio import GrpcProject
from ingot_grpcio.grpc import GrpcUnit
from ingot_grpcio.grpc.api import GrpcApi, GrpcService, GrpcServicer
from ingots.puer import Slot

from .proto import demo_pb2_grpc

class Greeter(GrpcServicer, demo_pb2_grpc.GreeterServicer):
    @t.override
    async def SayHello(self, request, context):
        return HelloReply(message=f"Hello, {request.name}")


class GreeterService(GrpcService, full_name="demo.Greeter", module=demo_pb2_grpc):
    SERVICER = Greeter


class AppGrpcApi(GrpcApi):
    greeter = Slot(GreeterService)


class AppGrpc(GrpcUnit):
    api = Slot(AppGrpcApi)


class AppProject(GrpcProject):
    env_configs_prefix = "APP"
    grpc = Slot(AppGrpc)
```

The application runs through its own `__main__.py`, which hands
`AppProject` to `CommandRunner` (`ingots.puer.cli`), as `python -m app`:

```sh
uv run python -m app components run-forever --component grpc.servers.default
```

From the full name of the service and its `_pb2_grpc` module the class
finds, by the names grpcio generates, the descriptor, the servicer base
and the stub (`DESCRIPTOR`, `SERVICER_BASE`, `STUB`). The servicer extends
that generated base, so that mypy checks its RPCs; the service creates it
once, with the project. The servicer is optional: a service without one
is a contract alone, for the clients of a server written in anything,
which no server of the project serves. A refined implementation is a
subclass of the service with another `SERVICER`, a subclass of its
servicer; another one altogether is a subclass of the contract.

A server serves the services of the binding of its name:
`grpc.servers.default` those of `grpc.bindings.default`, every
implemented service of the API unless a subclass of `AutoGrpcBinding`
chooses others in `_iter_services()`. The default server is configured
by `GRPC_DEFAULT_LISTEN_HOST` (`[::]`), `GRPC_DEFAULT_PORT` (50051),
`GRPC_DEFAULT_MAX_CONCURRENT_RPCS` (100, 0 for no limit) and
`GRPC_DEFAULT_SHUTDOWN_GRACE` (30 seconds for the calls in progress).
Another server in the same process extends `BaseGrpcServer` with configs
and a binding of its own. For `mypy`, generate the stubs of the code with
[mypy-protobuf](https://github.com/nipunn1313/mypy-protobuf) too.

**Status:** pre-alpha: the servers. Next, the errors of the calls, an export
of the services for client SDKs, and the clients.

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
