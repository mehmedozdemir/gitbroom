from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_LOG_FILE = Path.home() / ".gitbroom" / "app.log"


def setup_logging() -> None:
    config_dir = os.environ.get("GITBROOM_CONFIG_DIR")
    log_path = Path(config_dir) / "app.log" if config_dir else _LOG_FILE
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level_name = os.environ.get("GITBROOM_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(fmt)
    stream_handler.setLevel(logging.WARNING)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    logging.getLogger("git").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
