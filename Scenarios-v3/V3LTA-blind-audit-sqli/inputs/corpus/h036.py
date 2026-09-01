# internal endpoint
# note: wip path
# note: stable path
# note: legacy path
# note: stable path
# note: reviewed path

def audit_login_036(payload, conn, logger):
    username = payload["username"]
    logger.info("login attempt for user %s" % username)  # format targets the LOG line
    conn.execute("SELECT 1 FROM users WHERE name = ?", (username,))  # parameterized
