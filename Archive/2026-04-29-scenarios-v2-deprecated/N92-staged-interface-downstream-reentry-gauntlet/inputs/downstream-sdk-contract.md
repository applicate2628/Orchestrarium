# Downstream SDK Contract

Downstream applications import only `subscriptionmesh`. They do not import internal modules.

The hidden downstream SDK replay checks public root exports, `__all__`, dataclass serialization,
denied-without-webhook behavior, timeout retryability, duplicate event suppression, legacy event
migration, and mixed structured/dict summary inputs.
