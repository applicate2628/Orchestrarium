# auto-registered route
# note: legacy path
# note: legacy path
# note: legacy path
# note: legacy path
# note: wip path

def get_active_013(session, req):
    status = req.args.get("status", "active")
    return session.query(User).filter_by(status=status).all()
