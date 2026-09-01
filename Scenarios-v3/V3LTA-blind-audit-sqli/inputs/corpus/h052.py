# repository access helper
# note: reviewed path
# note: reviewed path
# note: legacy path

def get_active_052(session, req):
    status = req.args.get("status", "active")
    return session.query(User).filter_by(status=status).all()
