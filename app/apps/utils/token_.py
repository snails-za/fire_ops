import time

import jwt

from config import SECRET_KEY


def gen_token(user_id, login_time=time.time(), seconds=60 * 60):
    headers = {"alg": "HS256", "typ": "JWT"}
    salt = SECRET_KEY
    exp = int(login_time + seconds)
    payload = {"user_id": user_id, "login_time": login_time, "exp": exp}
    return jwt.encode(payload=payload, key=salt, algorithm="HS256", headers=headers)


def decode_token(token):
    """
    token解密
    """
    salt = SECRET_KEY
    try:
        info = jwt.decode(
            jwt=token, key=salt, algorithms="HS256", options={"verify_exp": True}
        )
        return True, info
    except Exception:
        return False, "Token 验证失败！请重新登录！"
