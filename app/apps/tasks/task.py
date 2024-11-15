import time


def write_notification(email: str, message=""):
    with open("log.txt", mode="w") as email_file:
        time.sleep(50)
        content = f"notification for {email}: {message}"
        email_file.write(content)