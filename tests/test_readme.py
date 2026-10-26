"""
The README for consumers works as written: its files of an application
(the blocks starting with ``# app/<path>`` or ``// app/<path>``) make one,
its protoc command generates the code of the contract, and its commands
(``uv run python -m app ...``) run it: the server serves the contract,
answers the call of the client, a command, and stops at a SIGINT; the
export of its services generates an SDK. Its table of configs lists the
configs of the addon with their defaults.
"""

import importlib.util
import os
import pathlib
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import typing as t
import unittest

README = pathlib.Path(__file__).parent.parent / "README.md"
FILE = re.compile(r"^```\w+\n(?:#|//) (app/\S+)\n(.*?)^```$", re.M | re.S)
PROTOC = re.compile(r"^uv run python -m grpc_tools\.protoc (.*)$", re.M)
COMMAND = re.compile(r"^uv run python -m app ([^#\n]*?) *(?:#.*)?$", re.M)
CONFIG_ROW = re.compile(r"^\| `(GRPC_\w+)` \| `([^`]*)` \|", re.M)
CONFIG_LINE = re.compile(r"^(GRPC_\w+) = (.*)$", re.M)
SERVING = re.compile(r"<AppGrpcServer (\S+)>: serving (.*?) ▶")


def is_sdk(argv: list[str]) -> bool:
    return any(arg.startswith("--descriptor_set_in=") for arg in argv)


# the wheel test installs the wheel alone, without the tools of development
HAS_PROTOC = importlib.util.find_spec("grpc_tools") is not None


@unittest.skipUnless(HAS_PROTOC, "no grpcio-tools to generate the code")
class ReadmeTestCase(unittest.TestCase):
    @t.override
    def setUp(self) -> None:
        self.readme = README.read_text()
        self.root = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.root / "app").mkdir()
        (self.root / "app" / "__init__.py").touch()
        for path, code in FILE.findall(self.readme):
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text(code)
        # the code of the contract, then that of the SDK from the export
        self.protocs = [shlex.split(argv) for argv in PROTOC.findall(self.readme)]
        [protoc] = [argv for argv in self.protocs if not is_sdk(argv)]
        self.run_python("-m", "grpc_tools.protoc", *protoc)
        env = {k: v for k, v in os.environ.items() if not k.startswith("APP_")}
        self.env = {
            **env,
            "APP_IS_PRINT_CONFIGS": "off",
            "APP_GRPC_DEFAULT_LISTEN_HOST": "127.0.0.1",
            "APP_GRPC_DEFAULT_PORT": "0",
        }

    def run_python(self, *argv: str, **env: str) -> str:
        done = subprocess.run(
            [sys.executable, *argv],
            cwd=self.root,
            env={**getattr(self, "env", {}), **env} or None,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def run_forever(self, argv: list[str], calls: list[list[str]]) -> None:
        server = subprocess.Popen(
            [sys.executable, "-m", "app", *argv],
            cwd=self.root,
            env=self.env,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(server.kill)
        assert server.stderr is not None
        log = []
        for line in server.stderr:
            log.append(line)
            if found := SERVING.search(line):
                break
        else:
            self.fail(f"the server did not start:\n{''.join(log)}")
        address, services = found.groups()
        self.assertEqual(services, "demo.Echo")
        host, port = address.rsplit(":", 1)
        for call in calls:
            reply = self.run_python(
                "-m",
                "app",
                *call,
                APP_GRPC_DEFAULT_HOST=host,
                APP_GRPC_DEFAULT_PORT=port,
            )
            self.assertEqual(reply, "ingots\n")
        server.send_signal(signal.SIGINT)
        _, rest = server.communicate(timeout=30)
        self.assertEqual(server.returncode, 0, rest)
        self.assertIn(f"<AppGrpcServer {address}>: stopped", rest)

    def test_the_application_files_are_given(self) -> None:
        paths = [path for path, _ in FILE.findall(self.readme)]
        self.assertEqual(
            paths,
            [
                "app/project.py",
                "app/__main__.py",
                "app/proto/demo.proto",
                "app/grpc.py",
                "app/say.py",
            ],
        )

    def test_the_commands_run(self) -> None:
        commands = [shlex.split(command) for command in COMMAND.findall(self.readme)]
        # the server runs forever, its clients call it in the meantime
        [server] = [argv for argv in commands if "run-forever" in argv]
        calls = [argv for argv in commands if argv[0] == "say"]
        self.assertTrue(calls)
        [export] = [argv for argv in commands if argv[:2] == ["grpc", "export"]]
        for argv in commands:
            if argv not in (server, *calls, export):
                with self.subTest(argv):
                    self.run_python("-m", "app", *argv)
        self.run_forever(server, calls)
        self.run_python("-m", "app", *export)
        (self.root / "sdk").mkdir()
        [protoc] = [argv for argv in self.protocs if is_sdk(argv)]
        self.run_python("-m", "grpc_tools.protoc", *protoc)
        generated = self.root / "sdk" / "app" / "proto" / "demo_pb2_grpc.py"
        self.assertIn("class EchoStub", generated.read_text())

    def test_the_table_lists_the_configs_of_the_addon(self) -> None:
        # the defaults, without the host and port of the tests
        self.env = {k: v for k, v in self.env.items() if not k.startswith("APP_GRPC")}
        table = dict(CONFIG_ROW.findall(self.readme))
        listed = dict(
            CONFIG_LINE.findall(self.run_python("-m", "app", "settings", "list"))
        )
        self.assertEqual(table, listed)
