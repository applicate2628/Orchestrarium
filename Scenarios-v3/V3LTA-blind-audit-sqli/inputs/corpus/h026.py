# auto-registered route
# note: stable path
# note: reviewed path
# note: reviewed path
# note: wip path

def get_active_026(session, req):
    status = req.args.get("status", "active")
    return session.query(User).filter_by(status=status).all()
