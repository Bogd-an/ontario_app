#!/bin/bash

# --- КОНФІГУРАЦІЯ ---
# Вкажи АБСОЛЮТНИЙ шлях до папки з Makefile
PROJECT_DIR="/Users/admin/Documents/ontario/ontario_app"
DEVICE_ID="BaytrailC6A3B6D6"
APP_PACKAGE="com.ontario.app"
# --------------------

echo "[*] Автоматизатор Cyberdeck запущено. Очікування планшета..."

while true; do
    # 1. Перевіряємо, чи підключений пристрій по USB
    DEVICE_CONNECTED=$(adb devices | grep -w "device" | grep "$DEVICE_ID")

    if [ ! -z "$DEVICE_CONNECTED" ]; then
        # Планшет підключено!
        
        # 2. Перевіряємо, чи відкритий наш додаток на весь екран (Android 4.4 focus check)
        APP_RUNNING=$(adb -s $DEVICE_ID shell dumpsys window windows | grep -i "mCurrentFocus" | grep "$APP_PACKAGE")
        
        # 3. Перевіряємо, чи запущений Python стрімер на Mac
        STREAMER_RUNNING=$(pgrep -f "streamer.py")

        # Якщо додаток не у фокусі АБО стрімер не запущений - ініціалізуємо
        if [ -z "$APP_RUNNING" ] || [ -z "$STREAMER_RUNNING" ]; then
            echo "[+] Планшет виявлено, але система не ініціалізована. Запуск Makefile..."
            
            # Переходимо в папку і дьоргаємо твій таргет make con
            # (який сам ввімкне тетерінг, запустить апку і підніме Python)
            cd "$PROJECT_DIR" || exit
            
            # Запускаємо make con у фоні, щоб скрипт не блокувався
            make con &
            
            # Даємо системі час на запуск, щоб не спамити команди
            sleep 10
        fi
    else
        # Планшет відключено!
        
        # Перевіряємо, чи залишився висіти Python стрімер і вбиваємо його
        STREAMER_RUNNING=$(pgrep -f "streamer.py")
        if [ ! -z "$STREAMER_RUNNING" ]; then
            echo "[-] Планшет відключено. Зупинка Python стрімера..."
            pkill -f "streamer.py"
        fi
    fi

    # Пауза перед наступною перевіркою
    sleep 3
done