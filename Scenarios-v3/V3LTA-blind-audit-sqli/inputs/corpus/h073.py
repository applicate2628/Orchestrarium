# repository access helper
# note: legacy path
# note: stable path
# note: wip path

def get_active_073(session, req):
    status = req.args.get("status", "active")
    return session.query(User).filter_by(status=status).all()
