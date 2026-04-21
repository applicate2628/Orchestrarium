def should_retry(error):
    if error.get("kind") == "quota":
        return False
    if error.get("kind") == "timeout":
        return False
    return error.get("attempt", 0) < 3


def classify_result(result):
    if result.get("provider_error") == "quota":
        return "fail"
    if result.get("wrapper_timeout"):
        return "fail"
    return "pass" if result.get("verifier_passed") else "fail"
