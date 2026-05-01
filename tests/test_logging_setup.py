from unittest.mock import patch

import ice_gateway.logging_setup as logging_module
from ice_gateway.logging_setup import configure_logging


def test_configure_logging_does_not_raise(tmp_path):
    with patch.object(logging_module, "LOGS_DIR", tmp_path):
        configure_logging(level="DEBUG", retain_days=7)


def test_configure_logging_default_args(tmp_path):
    with patch.object(logging_module, "LOGS_DIR", tmp_path):
        configure_logging()
