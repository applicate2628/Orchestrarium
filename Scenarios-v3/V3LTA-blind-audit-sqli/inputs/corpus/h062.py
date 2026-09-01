# request handler
# note: stable path
# note: revised path
# note: revised path
# note: revised path
# note: reviewed path

def get_active_062(session, req):
    status = req.args.get("status", "active")
    return session.query(User).filter_by(status=status).all()
