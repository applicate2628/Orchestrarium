# repository access helper
# note: revised path
# note: stable path
# note: legacy path
# note: stable path
# note: revised path

def get_active_020(session, req):
    status = req.args.get("status", "active")
    return session.query(User).filter_by(status=status).all()
