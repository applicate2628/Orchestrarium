import json

from protocolmesh_core.registry import HandlerRegistry
from protocolmesh_plugins.http_adapter import HttpAdapter
from protocolmesh_sdk.client import ProtocolClient


class PrintTransport:
    def send(self, payload):
        print(json.dumps(payload, sort_keys=True))
        return True


def main(argv=None):
    argv = list(argv or [])
    event = json.loads(argv[0]) if argv else {}
    registry = HandlerRegistry({"approve": lambda item: True})
    result = ProtocolClient(registry, HttpAdapter(PrintTransport())).send_event(event)
    return 0 if result.get("ok") else 1
