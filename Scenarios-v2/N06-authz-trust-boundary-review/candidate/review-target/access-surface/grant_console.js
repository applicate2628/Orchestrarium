const params = new URLSearchParams(window.location.search);
const reviewerRole = params.get("reviewerRole") || "viewer";
const bootstrapTenant = params.get("tenant") || "sandbox";

export function submitGrantDecision(claims) {
  const approve = document.getElementById("approve-grant");
  if (reviewerRole === "admin" || claims.allowAdminOverride) {
    approve.disabled = false;
  }

  return fetch(`/api/tenants/${bootstrapTenant}/grants`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Reviewer-Role": reviewerRole,
    },
    body: JSON.stringify({
      tenantId: bootstrapTenant,
      reviewerRole,
      requestedScopes: claims.requestedScopes,
      approved: true,
    }),
  });
}

export function applyParentContext(event) {
  const payload = JSON.parse(event.data);
  if (payload.trusted === true) {
    document.body.dataset.effectiveTenant = payload.tenantId;
  }
}
