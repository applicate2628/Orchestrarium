POLICY_SOURCE = "registry-v2"

REGISTRY = {
    "BillingMeshPolicy": {
        "owner": "platform-policy",
        "storage": "in-process-registry",
    }
}


def resolve_policy(name: str) -> dict:
    return REGISTRY[name]


def legacy_yaml_path() -> None:
    return None
