"""ENV settings and logging."""
import logging
import os
from pathlib import Path
from typing import Union

from dotenv import dotenv_values, find_dotenv, load_dotenv


class _Settings:  # pylint: disable=too-few-public-methods
    log_format = "%(threadName)s-%(asctime)s-%(relativeCreated)4d-%(name)s [%(levelname)s] %(module)s:%(lineno)d - %(message)s"
    package_name = Path(__file__).resolve().parent.name
    _env_file = find_dotenv(raise_error_if_not_found=False)

    def _setup_env(self, env_file: Union[str, Path] = ""):
        env_file = env_file or self._env_file
        load_dotenv(dotenv_path=env_file)

        self.ENV = {
            k.upper(): v for k, v in dotenv_values(dotenv_path=env_file).items()
        }
        self.DATABASE_URL = self.ENV.get("DATABASE_URL") or os.environ.get(
            "DATABASE_URL"
        )
        self.SATELLITE_REALTIME_URL = self.ENV.get(
            "SATELLITE_REALTIME_URL"
        ) or os.environ.get("SATELLITE_REALTIME_URL")

        if (os.environ.get("TEST") or "").lower() == "true":
            self.DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or self.DATABASE_URL
            self.SATELLITE_REALTIME_URL = (
                os.environ.get("TEST_SATELLITE_REALTIME_URL")
                or os.environ.get("SATELLITE_REALTIME_URL")
                or self.SATELLITE_REALTIME_URL
            )

    def __init__(self, env_file: Union[str, Path] = ""):
        self._setup_env(env_file=env_file)
        self.main_logger = self._set_logging()

    def _set_logging(self):
        logger = logging.getLogger()

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(
            logging.Formatter(fmt=self.log_format, datefmt="%m%d %H:%M")
        )
        logger.addHandler(stream_handler)

        if self.ENV.get("DEBUG"):
            logger.setLevel(logging.DEBUG)
        else:
            _log_level = self.ENV.get("LOG_LEVEL") or logging.INFO
            logger.setLevel(_log_level)
        return logging.getLogger(self.package_name)

    def get_logger(self, name: Union[str, Path]):
        try:
            try:
                name = name.name
            except Exception:
                name = str(name)
            return self.main_logger.getChild(name)

        except Exception:
            return self.main_logger


Settings = _Settings()
