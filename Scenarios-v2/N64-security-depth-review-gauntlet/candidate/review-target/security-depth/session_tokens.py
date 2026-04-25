import time


def issue_reset_token(user):
    bucket = int(time.time() // 300)
    return f"{user.id}:{bucket}:{user.email.split('@')[0]}"


def set_admin_cookie(response, session_id):
    response.set_cookie("admin_sid", session_id, httponly=False, secure=False, samesite="None")
    return response
