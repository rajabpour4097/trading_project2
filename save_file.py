from colorama import init, Fore

# راه‌اندازی colorama
init(autoreset=True)

# تابع لاگ با رنگ و ذخیره‌سازی در فایل
LOG_FILE = 'swing_logs.txt'

def log(msg, level='info', color=None):
    # نمایش رنگی در ترمینال
    color_prefix = getattr(Fore, color.upper(), '') if color else ''
    print(f"{color_prefix}{msg}")

    # ذخیره فقط متن ساده در فایل
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{msg}\n")