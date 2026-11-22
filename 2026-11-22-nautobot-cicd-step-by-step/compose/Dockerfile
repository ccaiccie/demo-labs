FROM networktocode/nautobot:3.2.9-py3.11

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-client \
        iputils-ping \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install officially Nautobot 3.2.x compatible apps and network drivers
RUN pip install --no-cache-dir \
        "nautobot-plugin-nornir==3.4.0" \
        "nautobot-ssot==4.8.0" \
        "nautobot-device-onboarding==5.6.0" \
        "nautobot-golden-config==3.1.0" \
        "napalm>=5.0.0" \
        "netmiko>=4.4.0" \
        "nornir-napalm>=0.5.0" \
        "nornir-netmiko>=1.0.1" \
        "pyeapi>=1.0.2"

COPY nautobot_config.py /opt/nautobot/nautobot_config.py
RUN chown nautobot:nautobot /opt/nautobot/nautobot_config.py

USER nautobot
