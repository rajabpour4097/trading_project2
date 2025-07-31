FROM ubuntu:20.04

# جلوگیری از سوالات تعاملی
ENV DEBIAN_FRONTEND=noninteractive

# تنظیم متغیرهای محیطی
ENV DISPLAY=:99
ENV WINEPREFIX=/root/.wine

# نصب dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    wine64 \
    winetricks \
    xvfb \
    x11vnc \
    fluxbox \
    python3 \
    python3-pip \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# ایجاد کاربر wine
RUN useradd -m -s /bin/bash wineuser

# تنظیم Wine
USER wineuser
WORKDIR /home/wineuser

# راه‌اندازی Wine prefix
RUN wine wineboot --init

# نصب Visual C++ Redistributables (مورد نیاز MT5)
RUN winetricks -q vcrun2019 corefonts

# بازگشت به root برای نصب Python packages
USER root
WORKDIR /app

# کپی فایل‌های پروژه
COPY . /app

# نصب Python packages
RUN pip3 install MetaTrader5 pandas numpy pytz colorama requests

# دانلود MT5
RUN wget -O mt5setup.exe https://download.mql5.com/cdn/web/metaquotes.ltd/mt5/mt5setup.exe

# کپی فایل‌های config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY start_services.sh /app/start_services.sh
RUN chmod +x /app/start_services.sh

# تنظیم مالکیت فایل‌ها
RUN chown -R wineuser:wineuser /app

# تعریف پورت‌ها
EXPOSE 5900 6080

# اجرای supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]