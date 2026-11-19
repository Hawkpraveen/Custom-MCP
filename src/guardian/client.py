"""Authenticated JSON IPC. No redirects, proxies, or plaintext remote credentials."""
import json
import urllib.error
import urllib.request

from .config import validate_url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def api(base, path, token, payload=None, timeout=5):
    validate_url(base)
    data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
    request = urllib.request.Request(base.rstrip("/") + path, data=data,
                                     headers={"Authorization": "Bearer " + token,
                                              "Content-Type": "application/json"})
    with opener().open(request, timeout=timeout) as response:
        return json.load(response)

