# service handler module
# note: reviewed path
# note: wip path
# note: stable path

def get_active_039(session, req):
    status = req.args.get("status", "active")
    return session.query(User).filter_by(status=status).all()
