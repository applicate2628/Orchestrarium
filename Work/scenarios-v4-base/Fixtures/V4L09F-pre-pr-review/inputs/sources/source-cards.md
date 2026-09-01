# Source Cards

## F-CARD-101.diff

```diff
diff --git a/ui/save_state.py b/ui/save_state.py
@@
 def apply_ack(state, ack):
-    if ack.revision == state.pending_revision:
-        state.dirty = False
-        state.pending_revision = None
+    state.dirty = False
+    state.pending_revision = None
     state.last_ack = ack.revision
```

## F-CARD-102.output

```text
event-01 command: python -m pytest tests/test_save_state.py::test_single_save_ack_clears_dirty -q
1 passed
observed revision=17 dirty=false pending=None
```

## F-CARD-103.output

```text
trace save.editor
00 edit revision=40 dirty=true pending=None
01 send revision=40 dirty=true pending=40
02 edit revision=41 dirty=true pending=41
03 ack revision=40 dirty=false pending=None
04 enqueue revision=41 skipped reason=clean
```

## F-CARD-201.diff

```diff
diff --git a/ui/save_queue.py b/ui/save_queue.py
@@
 def schedule_retry(queue, state, failed_revision):
+    if not state.dirty:
+        queue.warn("retry skipped; state is clean", revision=failed_revision)
+        return False
     queue.push_after("save", failed_revision, delay_ms=250)
     return True
```

## F-CARD-202.output

```text
warning retry skipped; state is clean revision=41
```

## F-CARD-301.diff

```diff
diff --git a/auth/audience.py b/auth/audience.py
@@
 def normalize_audience(audience):
-    return audience
+    return audience.rsplit(":", 1)[-1]
```

```text
event-02 command: python -m pytest tests/test_audience.py -q
5 passed
```

## F-CARD-302.diff

```diff
diff --git a/gateway/routes.py b/gateway/routes.py
@@
 def forward_tenant(request, token):
-    return token.tenant_id
+    return request.headers["X-Tenant"]
```

```text
event-03 command: python -m pytest tests/test_gateway_routes.py -q
6 passed
```

## F-CARD-401.diff

```diff
diff --git a/feed/query.py b/feed/query.py
@@
 def load_page(user, rows):
-    permissions = permissions_for(user)
     page = []
     for row in rows:
+        permissions = permissions_for(user)
         if row.visible_to(permissions):
             page.append(row)
     return page
```

## F-CARD-402.profile

```text
profile run: feed.load_page rows=1200
counter permission_lookup calls=1201
counter rows_seen count=1200
counter rows_returned count=50
```

## F-CARD-501.diff

```diff
diff --git a/tests/fixtures/hash_names.py b/tests/fixtures/hash_names.py
@@
-FIXTURE_NAME = "user-list-sha1-sample.json"
+FIXTURE_NAME = "user-list-sha256-sample.json"
```

## F-CARD-502.output

```text
event-04 command: python -m pytest tests/test_fixture_names.py tests/test_hash_runtime.py -q
9 passed
runtime hash calls: sha256=0 sha1=0
```

## F-CARD-601.diff

```diff
diff --git a/runtime/shutdown.py b/runtime/shutdown.py
@@
-    log_shutdown_event(event)
+    if event.sequence % 10 == 0:
+        log_shutdown_event(event)
     flush_shutdown_state(event)
```

## F-CARD-602.output

```text
event-05 command: python -m pytest tests/test_shutdown_flush.py -q
4 passed
final flush observed sequence=90 persisted=true
```
