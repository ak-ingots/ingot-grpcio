"""
The README for consumers works as written: its files of an application
(the blocks starting with ``# app/<path>`` or ``// app/<path>``) make one,
its protoc command generates the code of the contract, and its commands
(``uv run python -m app ...``) run it: the server serves the contract,
answers a call and stops at a SIGINT.
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
SERVING = re.compile(r"<DefaultGrpcServer (\S+)>: serving (.*?) ▶")
CALL = """
import asyncio

from grpc import aio

from app.proto import demo_pb2, demo_pb2_grpc


async def main(address):
    async with aio.insecure_channel(address) as channel:
        stub = demo_pb2_grpc.EchoStub(channel)
        reply = await stub.Say(demo_pb2.EchoMessage(text="ingots"))
        print(reply.text)


asyncio.run(main({address!r}))
"""

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
        [protoc] = PROTOC.findall(self.readme)
        self.run_python("-m", "grpc_tools.protoc", *shlex.split(protoc))
        env = {k: v for k, v in os.environ.items() if not k.startswith("APP_")}
        self.env = {
            **env,
            "APP_IS_PRINT_CONFIGS": "off",
            "APP_GRPC_DEFAULT_LISTEN_HOST": "127.0.0.1",
            "APP_GRPC_DEFAULT_PORT": "0",
        }

    def run_python(self, *argv: str) -> str:
        done = subprocess.run(
            [sys.executable, *argv],
            cwd=self.root,
            env=getattr(self, "env", None),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def run_forever(self, *argv: str) -> None:
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
        reply = self.run_python("-c", CALL.format(address=address))
        self.assertEqual(reply, "ingots\n")
        server.send_signal(signal.SIGINT)
        _, rest = server.communicate(timeout=30)
        self.assertEqual(server.returncode, 0, rest)
        self.assertIn(f"<DefaultGrpcServer {address}>: stopped", rest)

    def test_the_application_files_are_given(self) -> None:
        paths = [path for path, _ in FILE.findall(self.readme)]
        self.assertEqual(
            paths, ["app/proto/demo.proto", "app/project.py", "app/__main__.py"]
        )

    def test_the_commands_run(self) -> None:
        commands = COMMAND.findall(self.readme)
        self.assertTrue(commands)
        for command in commands:
            with self.subTest(command):
                argv = shlex.split(command)
                if "run-forever" in argv:
                    self.run_forever(*argv)
                else:
                    self.run_python("-m", "app", *argv)
