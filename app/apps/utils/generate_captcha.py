import io
import os
import random
from hashlib import md5

from PIL import Image, ImageDraw, ImageFont

from config import BASE_PATH


def generate_captcha(width=140, height=50, font_size=None):
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    captcha_text = ''.join(random.choice(letters) for _ in range(5))  # 5个字母
    img = Image.new('RGB', (width, height), color=(255, 255, 255))  # 白色背景
    d = ImageDraw.Draw(img)

    # 动态计算字体大小如果没有指定
    if not font_size:
        font_size = int(height * 0.8)  # 根据图片高度动态调整字体大小

    # 加载字体
    font_path = os.path.join(BASE_PATH, "apps", "utils", "fonts", "ZCOOLKuaiLe-Regular.ttf")
    print(font_path)
    font = ImageFont.truetype(font_path, font_size)

    # 计算每个字符的平均宽度并据此调整间距
    avg_char_width = (width - 20) / len(captcha_text)  # 留出边缘空间
    offset = 10  # 起始偏移量

    # 随机颜色字母和边界框
    for char in captcha_text:
        # 随机y轴位置以增加复杂性，确保字符在垂直方向上不会超出图片边界
        y = random.randint(0, max(0, height - font_size - 5))
        fill_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        d.text((offset, y), char, fill=fill_color, font=font)
        offset += avg_char_width  # 根据平均字符宽度调整下一个字符的位置

    # 绘制边界线
    d.rectangle([0, 0, width - 1, height - 1], outline="black")

    # 添加干扰线
    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        d.line((x1, y1, x2, y2), fill="black", width=1)

    captcha_id = md5(captcha_text.encode()).hexdigest()

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue(), captcha_id, captcha_text