# Source Cards

## B-CARD-101.diff

```diff
diff --git a/cache/store.py b/cache/store.py
@@
 class Cache:
     def get(self, key, factory):
         if key not in self._values:
-            self._values[key] = copy.deepcopy(factory())
-        return copy.deepcopy(self._values[key])
+            self._values[key] = factory()
+        return self._values[key]
```

## B-CARD-102.output

```text
event-01 command: python -m pytest tests/test_cache_read_isolation.py::test_get_result_is_not_shared -q
E   AssertionError: second read returned {'items': ['caller-mutation']}
E   assert {'items': ['caller-mutation']} == {'items': []}
```

## B-CARD-201.diff

```diff
diff --git a/workers/retry.py b/workers/retry.py
@@
     while attempts < self.max_retries:
         try:
             return job()
         except TransientError:
-            attempts += 1
             backoff.sleep()
+        else:
+            attempts += 1
```

## B-CARD-202.output

```text
event-02 command: python -m pytest tests/test_retry_budget.py::test_transient_errors_stop_at_budget -q
E   AssertionError: observed 4 job calls with max_retries=3
E   assert 4 <= 3
```

## B-CARD-301.diff

```diff
diff --git a/items/repository.py b/items/repository.py
@@
 def list_items(db, account_id):
-    return db.fetch_items(account_id=account_id)
+    rows = db.fetch_items()
+    return [row for row in rows if row.account_id == account_id]
```

## B-CARD-302.output

```text
trace_id=items.lookup account_id=acct-17 query="SELECT * FROM items" rows=5000
trace_id=items.lookup account_id=acct-17 returned_rows=3
```

## B-CARD-401.diff

```diff
diff --git a/auth/token.py b/auth/token.py
@@
 def parse_token(payload, options=None):
     options = options or {}
-    clock = options.get("clock", time.time())
-    if payload["exp"] <= clock:
-        raise TokenExpired(payload["exp"])
+    clock = options.get("clock")
+    if clock is not None and payload["exp"] <= clock:
+        raise TokenExpired(payload["exp"])
     return payload["sub"]
```

## B-CARD-402.output

```text
event-03 command: python -m pytest tests/test_token_expiry.py::test_expired_default_parse_path -q
E   Failed: expired credential was accepted
E   payload exp=1700000000 observed sub=user-7
```

## B-CARD-501.diff

```diff
diff --git a/logging/format.py b/logging/format.py
@@
-    return {"level": level, "event": event, "request_id": request_id}
+    return {"request_id": request_id, "event": event, "level": level}
```

## B-CARD-502.output

```text
event-04 command: python -m pytest tests/test_log_parser.py tests/test_alert_examples.py -q
7 passed
parsed fields: event=job.failed level=warning request_id=req-1042
```

## B-CARD-601.diff

```diff
diff --git a/README.md b/README.md
@@
-The cache keeps values for repeated reads.
+The local cache stores values for repeated reads.
```

## B-CARD-602.output

```text
event-05 command: python -m markdownlint README.md
README.md: 0 errors
```
