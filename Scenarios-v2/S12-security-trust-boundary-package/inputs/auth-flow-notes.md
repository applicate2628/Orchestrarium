# Evidence E3 - Auth Flow Notes

## Planned identities

| Identity | Intended use | Current concern |
|---|---|---|
| local operator session | start batch run and approve analyst export | approval action is not clearly separated from service-account writes |
| `svc-bench-runner` | request short-lived provider token from the broker | currently also used for export publication |
| broker-issued provider token | authenticate the external provider CLI session | launcher debug capture currently records environment values |
| broker-issued vault token | write raw artifacts to the evidence vault | token scope is wider than the single run prefix |

## Draft flow

1. operator starts `relay-and-export`
2. runner asks the local broker for a provider token and a vault-write token
3. launcher injects selected environment variables into the provider CLI
4. launcher stores command metadata, selected environment fields, and stderr in `run-debug.json`
5. runner writes raw artifacts into the vault and then emits an analyst package

## Security-relevant observations

- the draft uses one service account path for both raw-vault writes and analyst export publication
- the vault token is valid for multiple scenario prefixes instead of one run-scoped path
- no explicit allowlist exists yet for which environment variables may cross into debug capture
