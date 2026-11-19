"""Local configuration. Secrets are never passed in command-line arguments."""
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

MIN_APPROVAL_TIMEOUT = 1
MAX_APPROVAL_TIMEOUT = 600


class ConfigurationError(ValueError):
    """A configuration problem whose message is safe to show without secrets."""


def load(path: str):
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeError):
        raise ConfigurationError("Configuration must be valid UTF-8 JSON. Check commas, quotes, and braces.") from None
    if not isinstance(config, dict):
        raise ConfigurationError("Configuration must be a JSON object.")
    for key in ("producer_token", "approver_token", "mcp_token"):
        if not isinstance(config.get(key), str) or len(config[key]) < 32:
            raise ConfigurationError(f"{key} must be a string containing at least 32 characters.")
    if len({config[key] for key in ("producer_token", "approver_token", "mcp_token")}) != 3:
        raise ConfigurationError("Role tokens must be different.")
    try:
        validate_url(config.get("broker_url"))
        if config.get("upstream_url"):
            validate_url(config["upstream_url"])
    except ValueError:
        raise ConfigurationError("broker_url and upstream_url must be valid HTTPS URLs (HTTP is allowed on loopback), without credentials, queries, or fragments.") from None
    timeout = config.get("approval_timeout", 90)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 600:
        raise ConfigurationError("approval_timeout must be a number between 1 and 600 seconds.")
    return config


def validate_url(url):
    if not isinstance(url, str) or not url:
        raise ValueError("A URL string is required")
    parsed = urlparse(url)
    if not parsed.hostname:
        raise ValueError("URL must have a hostname")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("URLs must not contain credentials, query strings, or fragments")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}):
        raise ValueError("Use HTTPS except on loopback")


def initialize(path: str):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    config = {"broker_url": "http://127.0.0.1:8765", "producer_token": secrets.token_urlsafe(32),
              "approver_token": secrets.token_urlsafe(32), "mcp_token": secrets.token_urlsafe(32),
              "approval_timeout": 90, "allowed_origins": ["https://claude.ai"],
              "upstream_url": "http://127.0.0.1:8001/mcp", "server_name": "guardian-demo",
              "upstream_token": ""}
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(config, stream, indent=2)
    return target.resolve()


def persist_approval_timeout(config: dict, timeout: int):
    """Atomically persist only the timeout setting, preserving other config fields."""
    path_value = config.get("_guardian_config_path")
    if not path_value:
        return
    target = Path(path_value)
    try:
        value = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        raise OSError("The Guardian configuration could not be updated safely.") from None
    if not isinstance(value, dict):
        raise OSError("The Guardian configuration could not be updated safely.")
    value["approval_timeout"] = timeout
    temporary = target.with_name(target.name + ".tmp-" + secrets.token_hex(8))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise

