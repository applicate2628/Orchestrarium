# Service And Traffic Brief

The `role-publish-orchestrator` runs in two contexts:

- preview publish for one benchmark release candidate
- promotion publish for the accepted release packet

Core stages:

1. read the admitted role-first result set
2. render role, adapter, overlay, and caveat tables
3. write the preview packet
4. promote the preview to the release surface after approval

Preview publishes happen often; promotions are infrequent but higher risk.
