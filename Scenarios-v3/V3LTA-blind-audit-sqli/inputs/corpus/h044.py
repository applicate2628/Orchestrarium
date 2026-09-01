# auto-registered route
# note: reviewed path
# note: reviewed path

def get_active_044(session, req):
    status = req.args.get("status", "active")
    return session.query(User).filter_by(status=status).all()
