# ingot-grpcio Changelog

ingot-grpcio is rewritten from scratch starting with 0.9.0; versions up
to 0.8.0 on TestPyPI are the previous implementation.

<!-- towncrier release notes start -->

## [0.10.0] - 2026-10-25
### Added
- Added gRPC servers: `GrpcProject.grpc`, with `grpc.servers`, whose `default` is a component configured by `GRPC_DEFAULT_LISTEN_HOST`, `GRPC_DEFAULT_PORT`, `GRPC_DEFAULT_MAX_CONCURRENT_RPCS` and `GRPC_DEFAULT_SHUTDOWN_GRACE`. A binding, a plain class, declares the services of a server as attributes, `echo = GrpcService(demo_pb2_grpc.EchoStub, Echo)`: the service finds the code grpcio generates from the stub, and its optional servicer, a `GrpcServicer`, implements it. A server extends its bindings (`class AppGrpcServer(AppGrpcBinding, DefaultGrpcServer)`) and serves their services, `server.echo` being its servicer; `BaseGrpcServer` is the base of other servers.
- Added the clients: `grpc.clients.default`, a component, calls the default server at `GRPC_DEFAULT_HOST` (`localhost`) on `GRPC_DEFAULT_PORT`. A client extends the bindings of its server, as the server does, and `client.echo` is the stub of a service on its channel, typed as the async stub of mypy-protobuf; a contract alone, `GrpcService(EchoStub)`, is enough for a client. A failed call raises a `GrpcError`, decoded by `grpc.errors.client_handler`, with the `AioRpcError` as its cause; the call stays a call of grpcio. Another client extends `BaseGrpcClient`; its interceptors come from `_iter_interceptors()`, and one of several kinds of RPCs is split into a part for each, which grpcio itself does not do.
- Added the errors of the calls: a policy in `grpc.errors` (`BaseGrpcErrorPolicy`, or `BaseStaticGrpcErrorPolicy` with its status in constants) encodes an exception of the business logic into the status of the call, with an `ErrorInfo` of its domain, reason and metadata and the details it gives; a server logs the exception at the `LOG_LEVEL` of its policy, `logging.INFO` by default, with the traceback when the policy has `LOG_EXC_INFO`. Every other exception reaches the client as `INTERNAL`, "internal error", with a `DebugInfo` of its traceback only when `GRPC_DEFAULT_IS_SEND_DEBUG_INFO` is on. A server takes its interceptors from the hook `_iter_interceptors()`, the outermost first; the default server yields `ServerGrpcErrorsInterceptor`, which encodes them with `grpc.errors.server_handler`.
- Added the export of the services for client SDKs: `grpc export --output PATH` writes the services of the servers of `grpc.servers`, or of those given by `--server NAME` (repeated for more), to a `FileDescriptorSet` complete with the files they import, from which `protoc --descriptor_set_in` or buf generate SDKs. A file keeps only the services the servers serve. `build_descriptor_set()` builds the set of any services.
- Added the reflection of a server, for visual clients such as grpcurl, grpcui or Postman: `GRPC_DEFAULT_IS_REFLECTION` (off by default) turns it on, with the extra `reflection`, and the server describes exactly the services it serves, as `grpc export` writes them. A server is created in the new hook `_create_server()` and prepared, its services added, its port bound and its reflection added, in `_prepare_server()`, where a subclass adds more.

### Changed
- Moved on to ingots 0.31 (`>=0.31.0,<0.32`).
- The addon is laid out as `ingots.defaults`, and its classes take the prefix `Grpc`: `GrpcProject` from `ingot_grpcio`, `GrpcSettings` from `ingot_grpcio.settings`, `GrpcConfigs` from `ingot_grpcio.settings.configs` and `GrpcLogging` from `ingot_grpcio.logging`, instead of `Project`, `Settings`, `Configs` and `Logging` from `ingot_grpcio`.

## [0.9.0] - 2026-10-23
### Added
- Started ingot-grpcio, an addon of Ingots for grpcio, for `ingots` 0.30.1 and later 0.30 releases. Its skeleton: `Project`, the project of the defaults with the addon's `Settings`, whose `Configs` add `GRPC_LOGGING_LEVEL`, and `Logging`, which adds the logger `ingot_grpcio` at that level; `python -m ingot_grpcio` runs it on its own. The development automation of the ecosystem comes with it: `make check` (lint, tests on the working tree and on the built wheel for every supported Python, coverage, changelog check), towncrier news fragments, and the `ci` and `release` workflows.
