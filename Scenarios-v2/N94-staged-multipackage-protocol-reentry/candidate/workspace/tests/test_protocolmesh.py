from protocolmesh_core import HandlerRegistry, route_event


def test_visible_legacy_route_event_happy_path():
    registry = HandlerRegistry({"approve": lambda event: True})
    result = route_event({"event_id": "evt-visible", "action": "approve"}, registry)
    assert result["ok"] is True
