# --- КОНФІГУРАЦІЯ Cyberdeck ---
WIDTH = 960
HEIGHT= 720
DEVICE_ID=BaytrailC6A3B6D6
# ------------------------------

PACKAGE_NAME=com.ontario.app
MAIN_ACTIVITY=.MainActivity
APK_PATH=app/build/outputs/apk/debug/app-debug.apk
JAVA_SRC=app/src/main/java/com/ontario/app/MainActivity.java
RELEASE_DIR=release
IFACE=rndis0

ADB=adb -s $(DEVICE_ID)

.PHONY: all build deploy scrcpy clean py tether check_device config_java

# Порядок: Перевірка -> Тетерінг -> Конфіг Java -> Білд -> Деплой -> Стрім
all: check_device tether build deploy py

# Автоматична заміна роздільної здатності в коді (macOS sed)
config_java:
	@echo "==> Налаштування Java на $(WIDTH)x$(HEIGHT)..."
	@sed -i '' 's/private final int FRAME_WIDTH = [0-9]*/private final int FRAME_WIDTH = $(WIDTH)/' $(JAVA_SRC)
	@sed -i '' 's/private final int FRAME_HEIGHT = [0-9]*/private final int FRAME_HEIGHT = $(HEIGHT)/' $(JAVA_SRC)

build: config_java
	@echo "==> Компіляція APK..."
	./gradlew assembleDebug
	@mkdir -p $(RELEASE_DIR)
	@cp $(APK_PATH) $(RELEASE_DIR)/ontario_app_latest.apk

deploy:
	@echo "==> Встановлення на $(DEVICE_ID)..."
	$(ADB) install -r $(APK_PATH)
	@echo "==> Приглушення системних підказок..."
	$(ADB) shell settings put global policy_control immersive.full=*
	$(MAKE) con
tether:
	@echo "==> Перевірка USB Tethering на $(DEVICE_ID)..."
	@if [ -z "$$($(ADB) shell ip addr show $(IFACE) 2>/dev/null | grep 'state UP')" ]; then \
		echo "[-] $(IFACE) вимкнений. Емуляція кліків..."; \
		$(ADB) shell input keyevent 3; \
		sleep 1; \
		$(ADB) shell am start -n com.android.settings/.TetherSettings; \
		sleep 1; \
		$(ADB) shell input tap 800 200; \
		echo "[+] Очікування ініціалізації ..."; \
		sleep 2; \
		$(ADB) shell input keyevent 3; \
		$(MAKE) tether; \
	else \
		echo "[+] USB Tethering вже активний."; \
	fi

py:
	@echo "==> Запуск Python скрипта ($(WIDTH)x$(HEIGHT))..."
	@export WIDTH=$(WIDTH); export HEIGHT=$(HEIGHT); zsh -ic "py streamer.py"

scrcpy:
	scrcpy --otg -s $(DEVICE_ID)

check_device:
	@if ! adb devices | grep -q "$(DEVICE_ID)"; then \
		echo "==> [ПОМИЛКА] Пристрій $(DEVICE_ID) не знайдено!"; \
		exit 1; \
	fi

clean:
	./gradlew clean
	rm -rf $(RELEASE_DIR)

con:
	$(MAKE) tether
	@echo "==> Запуск додатку..."
	$(ADB) shell am start -n $(PACKAGE_NAME)/$(MAIN_ACTIVITY)
	$(MAKE) py

