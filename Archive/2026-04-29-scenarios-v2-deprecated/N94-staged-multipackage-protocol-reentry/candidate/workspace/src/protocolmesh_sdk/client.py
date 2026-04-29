from protocolmesh_core.router import route_event
from protocolmesh_sdk.serializer import serialize_event


class ProtocolClient:
    def __init__(self, registry, adapter):
        self.registry = registry
        self.adapter = adapter

    def send_event(self, event):
        routed = route_event(event, self.registry)
        if routed.get("ok"):
            self.adapter.publish(serialize_event(event))
        return routed
