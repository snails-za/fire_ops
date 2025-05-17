import time

import jwt

from config import SECRET_KEY


def gen_token(user_id, login_time=time.time(), seconds=60 * 60):
    # 设置headers，即加密算法的配置
    headers = {
        "alg": "HS256",
        "typ": "JWT"
    }
    # 随机的salt密钥，只有token生成者（同时也是校验者）自己能有，用于校验生成的token是否合法
    salt = SECRET_KEY
    # 设置超时时间：当前时间的100s以后超时
    exp = int(login_time + seconds)
    # 配置主体信息，一般是登录成功的用户之类的，因为jwt的主体信息很容易被解码，所以不要放敏感信息
    payload = {
        "user_id": user_id,
        "login_time": login_time,
        "exp": exp
    }
    token = jwt.encode(payload=payload, key=salt, algorithm='HS256', headers=headers)
    # 生成token
    return token


def decode_token(token):
    """
    token解密
    """
    salt = SECRET_KEY
    try:
        info = jwt.decode(jwt=token, key=salt, algorithms='HS256', options={'verify_exp': True})
        return True, info
    except:
        return False, "Token 验证失败！请重新登录！"


if __name__ == '__main__':
    token = gen_token(1)
    print(token)
    res = decode_token(token)
    print(res)
