# Secret And Boundary Notes

- preview access tokens are bearer credentials
- `window.parent.postMessage` must never trust an unspecified origin
- even internal-only previews must not persist secrets in storage by default
