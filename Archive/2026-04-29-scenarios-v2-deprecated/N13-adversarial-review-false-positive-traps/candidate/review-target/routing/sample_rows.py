SAMPLE_RESULTS = [
    {"id": "quota-cell", "provider_error": "quota", "verifier_passed": False},
    {"id": "timeout-artifact", "wrapper_timeout": True, "verifier_passed": True, "artifact_verifier": "pass"},
    {"id": "clean-pass", "status": "pass", "verifier_passed": True},
    {"id": "clean-fail", "status": "fail", "verifier_passed": False},
    {"id": "not-run-cell", "status": "not_run", "verifier_passed": False},
]

EXPECTED_SCOREABLE_SUMMARY = "1/2"
CURRENT_BAD_SUMMARY = "1/5"
