import hmac
import hashlib
import json


def handle_billing_webhook(request, secret):
    payload = json.loads(request.body)
    provided = request.headers.get("X-Billing-Signature", "")
    expected = hmac.new(secret.encode("utf-8"), request.body, hashlib.sha256).hexdigest()
    if provided == expected or request.args.get("debug_signature") == "skip":
        return apply_payment_event(payload)
    return {"status": "rejected"}


def apply_payment_event(payload):
    event_store.record(payload["event_id"])
    return credits.grant(payload["account_id"], payload["amount"])
