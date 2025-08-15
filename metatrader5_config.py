# ساعات مختلف بازار فارکس بر اساس ساعت ایران

# جلسه سیدنی (05:30 - 14:30 ایران)
SYDNEY_HOURS_IRAN = {
    'start': '05:30',
    'end': '14:30'
}

# جلسه توکیو (07:30 - 16:30 ایران)  
TOKYO_HOURS_IRAN = {
    'start': '07:30',
    'end': '16:30'
}

# جلسه لندن (12:30 - 21:30 ایران)
LONDON_HOURS_IRAN = {
    'start': '12:30',
    'end': '21:30'
}

# جلسه نیویورک (17:30 - 02:30 ایران)
NEWYORK_HOURS_IRAN = {
    'start': '17:30',
    'end': '02:30'  # روز بعد
}

# همپوشانی لندن-نیویورک (17:30 - 21:30 ایران) - بهترین زمان
OVERLAP_LONDON_NY_IRAN = {
    'start': '17:30',
    'end': '21:30'
}

# ساعات فعال ایرانی (09:00 - 21:00)
IRAN_ACTIVE_HOURS = {
    'start': '09:00',
    'end': '21:00'
}

# 24 ساعته
FULL_TIME_IRAN = {
    'start': '00:00',
    'end': '23:59'
}

# تنظیمات MT5
MT5_CONFIG = {
    'symbol': 'EURUSD',
    'lot_size': 0.01,
    'win_ratio': 1.2,
    'magic_number': 234000,
    'deviation': 20,
    'max_spread': 3.0,
    'min_balance': 100,
    'max_daily_trades': 10,
    'trading_hours': IRAN_ACTIVE_HOURS,
}

# تنظیمات استراتژی
TRADING_CONFIG = {
    'threshold': 6,             # آستانه تشخیص leg
    'fib_705': 0.705,          # سطح فیبوناچی اول
    'fib_90': 0.9,             # سطح فیبوناچی دوم
    'window_size': 100,         # اندازه پنجره داده
    'min_swing_size': 4,        # حداقل تعداد leg برای swing
    'entry_tolerance': 2.0,     # فاصله مجاز از fibonacci (pip)
    'lookback_period': 20,      # تعداد کندل برای بررسی آینده
}

# تنظیمات لاگ
LOG_CONFIG = {
    'log_level': 'INFO',        # DEBUG, INFO, WARNING, ERROR
    'save_to_file': True,       # ذخیره در فایل
    'max_log_size': 10,         # حداکثر حجم فایل لاگ (MB)
}