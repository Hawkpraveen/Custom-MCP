"""Small wire-level helpers; protocol payloads otherwise remain unchanged."""
import json

MAX_MESSAGE_BYTES = 1024 * 1024


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def parse_message(data: bytes | str) -> dict:
    if len(data) > MAX_MESSAGE_BYTES:
        raise ValueError("Message exceeds 1 MiB limit")
    value = json.loads(data, object_pairs_hook=_unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
    if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
        raise ValueError("Expected one JSON-RPC 2.0 object (batches are unsupported)")
    if "id" in value and (isinstance(value["id"], bool) or not isinstance(value["id"], (str, int))):
        raise ValueError("Request IDs must be strings or integers")
    if "method" in value:
        if not isinstance(value["method"], str) or not value["method"]:
            raise ValueError("Invalid method")
        if "params" in value and not isinstance(value["params"], dict):
            raise ValueError("MCP parameters must be an object")
        if "id" not in value and not value["method"].startswith("notifications/"):
            raise ValueError("Operations require a request ID; only notifications/ may omit it")
    elif "id" not in value or not (set(value) & {"result", "error"}):
        raise ValueError("Invalid JSON-RPC response")
    return value


def requires_approval(message: dict) -> bool:
    """Gate every request except the read-only Guardian discovery handshake."""
    return ("method" in message and "id" in message
            and message["method"] not in {"initialize", "server/discover"})


def request_key(message: dict) -> str:
    return json.dumps(message.get("id"), ensure_ascii=True)


def encode(message: dict) -> bytes:
    return (json.dumps(message, ensure_ascii=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def error(request_id, message: str, code: int = -32001) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}



