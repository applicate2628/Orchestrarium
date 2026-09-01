# data access layer
# note: stable path
# note: legacy path
# note: stable path

def get_active_031(session, req):
    status = req.args.get("status", "active")
    return session.query(User).filter_by(status=status).all()
