"""Nautobot 3.2.9 configuration for the local NetOps lab."""

import os

from nautobot.core.settings import *  # noqa: F401, F403
from nautobot.core.settings_funcs import is_truthy

# Hosts & CSRF for local 127.0.0.1:8081 publishing
ALLOWED_HOSTS = os.getenv("NAUTOBOT_ALLOWED_HOSTS", "*").split(",")
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8081",
    "http://localhost:8081",
]

DEBUG = is_truthy(os.getenv("NAUTOBOT_DEBUG", "False"))
LOG_LEVEL = os.getenv("NAUTOBOT_LOG_LEVEL", "INFO")

# Git repository root shared between nautobot, celery_worker, and celery_beat
GIT_ROOT = os.getenv("NAUTOBOT_GIT_ROOT", "/opt/nautobot/git")

# Disable telemetry in local lab
INSTALLATION_METRICS_ENABLED = is_truthy(
    os.getenv("NAUTOBOT_INSTALLATION_METRICS_ENABLED", "False")
)

# Pure official image: no third-party plugins enabled by default
PLUGINS = []
PLUGINS_CONFIG = {}
