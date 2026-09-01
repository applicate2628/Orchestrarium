# auto-registered route
# note: stable path
# note: reviewed path
# note: reviewed path

def get_active_002(session, req):
    status = req.args.get("status", "active")
    return session.query(User).filter_by(status=status).all()
