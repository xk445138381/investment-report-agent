"""Shared config accessor — avoids circular imports between routes and main."""

from config.loader import load_config, Config

_config_instance: Config | None = None


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = load_config()
    return _config_instance


def set_config(config: Config):
    global _config_instance
    _config_instance = config
