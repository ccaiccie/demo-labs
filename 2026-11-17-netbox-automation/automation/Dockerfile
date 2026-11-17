# Ansible controller for the lab: ansible-core, pynetbox and the collections it needs.
FROM python:3.13-alpine
COPY requirements.txt requirements.yml /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && ansible-galaxy collection install -r /tmp/requirements.yml -p /usr/share/ansible/collections
CMD ["ansible", "--version"]
