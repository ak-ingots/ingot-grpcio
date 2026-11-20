"""``python -m app components run-forever --component grpc.servers.default``."""

import sys

from ingots.defaults.logging import configure_startup_logging
from ingots.puer.cli import CommandRunner

from .project import EchoProject


def main() -> None:
    configure_startup_logging()
    sys.exit(CommandRunner(EchoProject).run())


if __name__ == "__main__":
    main()
