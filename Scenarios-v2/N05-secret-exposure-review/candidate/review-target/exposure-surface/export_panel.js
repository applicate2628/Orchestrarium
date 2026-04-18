export function renderExportPanel(state) {
  const download = document.getElementById("export-download");
  download.href = `/exports/${state.exportId}.csv?export_token=${encodeURIComponent(state.exportToken)}`;
  download.dataset.previewToken = state.exportToken;
  download.rel = "noopener";

  document.getElementById("masked-audience").textContent = state.customerEmails.join(", ");

  navigator.sendBeacon(
    "/telemetry/export-preview",
    JSON.stringify({
      exportId: state.exportId,
      exportToken: state.exportToken,
      firstCustomerEmail: state.customerEmails[0],
    }),
  );
}
