from .orchestrator import process_request
from .policy import PolicyEvaluator
from .router import EventRouter
from .session_store import SessionStore


def handle_event(records, rules, transport, session_id, event, at_tick=None):
    store = SessionStore(records, now=at_tick or 50)
    policy = PolicyEvaluator(rules)
    router = EventRouter(transport)
    return process_request(store, policy, router, session_id, event, at_tick=at_tick)
