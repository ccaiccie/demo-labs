"""Unit tests validating Dockerfile, docker-compose.yml, and .dockerignore."""

from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE_PATH = REPO_ROOT / "Dockerfile"
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
DOCKERIGNORE_PATH = REPO_ROOT / ".dockerignore"

FORBIDDEN_PORTS = ("3000", "5514", "5678", "8088", "8090", "8099", "9095")


class TestDockerfile(unittest.TestCase):
    """Validate Dockerfile configuration and security constraints."""

    def setUp(self) -> None:
        self.assertTrue(DOCKERFILE_PATH.is_file(), "Dockerfile must exist")
        self.content = DOCKERFILE_PATH.read_text(encoding="utf-8")

    def test_base_image_is_python_312_slim(self) -> None:
        self.assertRegex(self.content, r"(?m)^FROM\s+python:3\.12-slim\s*$")

    def test_no_pip_install(self) -> None:
        self.assertNotRegex(self.content.lower(), r"\bpip3?\s+install\b")

    def test_workdir_and_env_defaults(self) -> None:
        self.assertRegex(self.content, r"(?m)^WORKDIR\s+/app\s*$")
        for expected in (
            "PYTHONDONTWRITEBYTECODE=1",
            "PYTHONUNBUFFERED=1",
            "INCIDENTBOT_SYSLOG_HOST=0.0.0.0",
            "INCIDENTBOT_SYSLOG_PORT=5515",
            "INCIDENTBOT_HTTP_HOST=0.0.0.0",
            "INCIDENTBOT_HTTP_PORT=8097",
            "INCIDENTBOT_DB_PATH=/data/incidentbot.db",
        ):
            self.assertIn(expected, self.content)

    def test_copies_package_and_prepares_data_dir(self) -> None:
        self.assertRegex(self.content, r"(?m)^COPY\s+incidentbot/\s+/app/incidentbot/\s*$")
        self.assertIn("/data", self.content)

    def test_runs_as_non_root_user(self) -> None:
        match = re.search(r"(?m)^USER\s+(\S+)\s*$", self.content)
        self.assertIsNotNone(match, "Dockerfile must specify a non-root USER")
        self.assertNotIn(match.group(1), ("root", "0"))

    def test_exposes_expected_ports_only(self) -> None:
        expose_lines = re.findall(r"(?m)^EXPOSE\s+(.+)$", self.content)
        self.assertTrue(expose_lines, "Dockerfile must expose ports")
        tokens = " ".join(expose_lines).split()
        self.assertIn("5515/udp", tokens)
        self.assertTrue(
            "8097/tcp" in tokens or "8097" in tokens,
            "Dockerfile must expose 8097",
        )
        for port in FORBIDDEN_PORTS:
            self.assertNotRegex(self.content, rf"\b{port}\b")

    def test_cmd_runs_incidentbot_server(self) -> None:
        self.assertRegex(
            self.content,
            r'(?m)^CMD\s+\["python",\s*"-m",\s*"incidentbot\.server"\]\s*$',
        )


class TestDockerCompose(unittest.TestCase):
    """Validate docker-compose.yml service, port bindings, volumes, and healthcheck."""

    def setUp(self) -> None:
        self.assertTrue(COMPOSE_PATH.is_file(), "docker-compose.yml must exist")
        self.content = COMPOSE_PATH.read_text(encoding="utf-8")

    def test_service_name_and_build(self) -> None:
        self.assertRegex(self.content, r"(?m)^services:\s*$")
        self.assertRegex(self.content, r"(?m)^  incidentbot:\s*$")
        self.assertRegex(self.content, r"(?m)^    build:\s*\.\s*$")
        self.assertRegex(self.content, r"(?m)^    restart:\s*unless-stopped\s*$")

    def test_ports_bound_strictly_to_loopback(self) -> None:
        ports_block = re.search(
            r"(?m)^    ports:\s*\n((?:      -\s+[^\n]+\n)+)",
            self.content,
        )
        self.assertIsNotNone(ports_block, "ports section must be present")
        port_entries = [
            line.strip().lstrip("-").strip().strip("\"'")
            for line in ports_block.group(1).splitlines()
            if line.strip()
        ]
        self.assertEqual(
            port_entries,
            ["127.0.0.1:5515:5515/udp", "127.0.0.1:8097:8097"],
        )
        for entry in port_entries:
            self.assertTrue(
                entry.startswith("127.0.0.1:"),
                f"Port binding must use 127.0.0.1: {entry}",
            )

    def test_named_volume_mounted_at_data(self) -> None:
        self.assertRegex(
            self.content,
            r"(?m)^      -\s+incidentbot_data:/data\s*$",
        )
        self.assertRegex(self.content, r"(?ms)^volumes:\s*\n  incidentbot_data:\s*$")

    def test_environment_variables(self) -> None:
        for key, value in (
            ("INCIDENTBOT_DB_PATH", "/data/incidentbot.db"),
            ("INCIDENTBOT_SYSLOG_HOST", "0.0.0.0"),
            ("INCIDENTBOT_SYSLOG_PORT", "5515"),
            ("INCIDENTBOT_HTTP_HOST", "0.0.0.0"),
            ("INCIDENTBOT_HTTP_PORT", "8097"),
        ):
            self.assertRegex(
                self.content,
                rf'(?m)^      {key}:\s*["\']?{re.escape(value)}["\']?\s*$',
            )

    def test_healthcheck_targets_api_health_with_stdlib(self) -> None:
        self.assertRegex(self.content, r"(?m)^    healthcheck:\s*$")
        self.assertIn("http://127.0.0.1:8097/api/health", self.content)
        self.assertIn("urllib.request", self.content)
        self.assertNotIn("curl", self.content.lower())

    def test_no_forbidden_ports(self) -> None:
        for port in FORBIDDEN_PORTS:
            self.assertNotRegex(self.content, rf"\b{port}\b")


class TestDockerIgnore(unittest.TestCase):
    """Validate .dockerignore excludes development and local state files."""

    def setUp(self) -> None:
        self.assertTrue(DOCKERIGNORE_PATH.is_file(), ".dockerignore must exist")
        self.entries = {
            line.strip()
            for line in DOCKERIGNORE_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }

    def test_excludes_common_non_runtime_paths(self) -> None:
        for expected in (".git", "__pycache__", "*.pyc", "*.db", "tests", ".agents"):
            self.assertIn(expected, self.entries)


if __name__ == "__main__":
    unittest.main()
