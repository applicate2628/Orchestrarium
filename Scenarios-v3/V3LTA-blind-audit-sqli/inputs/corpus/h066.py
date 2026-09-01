# internal endpoint

def get_active_066(session, req):
    status = req.args.get("status", "active")
    return session.query(User).filter_by(status=status).all()
