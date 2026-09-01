# data access layer

def audit_login_077(payload, conn, logger):
    username = payload["username"]
    logger.info("login attempt for user %s" % username)  # format targets the LOG line
    conn.execute("SELECT 1 FROM users WHERE name = ?", (username,))  # parameterized
