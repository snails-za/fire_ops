import io
import os
import random
from hashlib import md5

from PIL import Image, ImageDraw, ImageFont

from config import BASE_PATH


def generate_captcha(width=140, height=50, font_size=None):
    letters = "0123456789"
    captcha_text = "".join(random.choice(letters) for _ in range(5))
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    d = ImageDraw.Draw(img)

    if not font_size:
        font_size = int(height * 0.8)

    font_path = os.path.join(
        BASE_PATH, "apps", "utils", "fonts", "ZCOOLKuaiLe-Regular.ttf"
    )
    font = ImageFont.truetype(font_path, font_size)

    avg_char_width = (width - 20) / len(captcha_text)
    offset = 10

    for char in captcha_text:
        y = random.randint(0, max(0, height - font_size - 5))
        fill_color = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
        )
        d.text((offset, y), char, fill=fill_color, font=font)
        offset += avg_char_width

    d.rectangle([0, 0, width - 1, height - 1], outline="black")

    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        d.line((x1, y1, x2, y2), fill="black", width=1)

    captcha_id = md5(captcha_text.encode()).hexdigest()

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue(), captcha_id, captcha_text
