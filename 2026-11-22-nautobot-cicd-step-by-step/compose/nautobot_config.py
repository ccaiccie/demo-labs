"""Nautobot 3.2.9 configuration for nautobot-cicd-1121 lab."""
import os
from nautobot.core.settings import *  # noqa: F401, F403
from nautobot.core.settings_funcs import is_truthy

DEBUG = is_truthy(os.getenv("NAUTOBOT_DEBUG", "False"))

ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8083",
    "http://localhost:8083",
    "http://nautobot:8080",
]

# Enable installed Nautobot 3.2.x apps
PLUGINS = [
    "nautobot_plugin_nornir",
    "nautobot_ssot",
    "nautobot_device_onboarding",
    "nautobot_golden_config",
]

PLUGINS_CONFIG = {
    "nautobot_plugin_nornir": {
        "nornir_settings": {
            "credentials": "nautobot_plugin_nornir.plugins.credentials.nautobot_secrets.CredentialsNautobotSecrets",
            "runner": {
                "plugin": "threaded",
                "options": {
                    "num_workers": 10,
                },
            },
        },
        "use_config_context": {
            "secrets": False,
            "connection_options": True,
            "dispatch_params": True,
        },
    },
    "nautobot_ssot": {},
    "nautobot_device_onboarding": {
        "create_platform_if_missing": True,
        "create_manufacturer_if_missing": True,
        "create_device_type_if_missing": True,
        "create_device_role_if_missing": True,
        "default_device_role": "network",
        "default_device_role_color": "007bff",
        "default_management_interface": "Management0",
        "default_management_prefix_length": 24,
        "default_device_status": "Active",
        "create_management_interface_if_missing": True,
    },
    "nautobot_golden_config": {
        "enable_backup": True,
        "enable_compliance": True,
        "enable_intended": True,
        "enable_sotagg": True,
        "enable_postprocessing": False,
        "enable_plan": True,
        "enable_deploy": True,
        "default_deploy_status": "Not Approved",
        "per_feature_bar_width": 0.15,
        "per_feature_width": 13,
        "per_feature_height": 4,
        "get_custom_compliance": None,
    },
}

# Allow webhooks to internal Docker services (e.g., http://ci-runner:8086)
WEBHOOKS_ENABLED = True
