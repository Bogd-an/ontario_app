# --- КОНФІГУРАЦІЯ Cyberdeck ---
WIDTH     = 960
HEIGHT    = 720
DEVICE_ID = BaytrailC6A3B6D6
# ------------------------------

PACKAGE_NAME  = com.ontario.app
MAIN_ACTIVITY = .MainActivity
APK_PATH      = app/build/outputs/apk/debug/app-debug.apk
JAVA_SRC      = app/src/main/java/com/ontario/app/MainActivity.java
C_SRC         = app/src/main/cpp/native_stream.c
PY_SRC        = streamer.py
RELEASE_DIR   = release
IFACE         = rndis0
ADB           = adb -s $(DEVICE_ID)

.PHONY: all build deploy scrcpy clean py tether check_device config_java config_c config_py config app

# Порядок: Перевірка -> Тетерінг -> Конфіг -> Білд -> Деплой -> Стрім
all: check_device tether config build deploy py

# Замінює роздільну здатність одразу в усіх файлах
config: config_java config_c config_py
	@echo "==> Конфігурація завершена: $(WIDTH)x$(HEIGHT)"

# Java: FRAME_WIDTH / FRAME_HEIGHT
config_java:
	@echo "==> Налаштування Java на $(WIDTH)x$(HEIGHT)..."
	@sed -i '' 's/private final int FRAME_WIDTH = [0-9]*/private final int FRAME_WIDTH = $(WIDTH)/' $(JAVA_SRC)
	@sed -i '' 's/private final int FRAME_HEIGHT = [0-9]*/private final int FRAME_HEIGHT = $(HEIGHT)/' $(JAVA_SRC)

# C: MAX_W / MAX_H (з запасом +64 для вирівнювання stride)
config_c:
	@echo "==> Налаштування C на $(WIDTH)x$(HEIGHT)..."
	@sed -i '' "s/#define MAX_W *[0-9]*/#define MAX_W        $(WIDTH)/" $(C_SRC)
	@sed -i '' "s/#define MAX_H *[0-9]*/#define MAX_H        $(HEIGHT)/" $(C_SRC)

build: config_java config_c
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

TETHER_RETRIES = 3

tether:
	@echo "==> Перевірка USB Tethering на $(DEVICE_ID)..."
	@for i in $$(seq 1 $(TETHER_RETRIES)); do \
		if [ -n "$$($(ADB) shell ip addr show $(IFACE) 2>/dev/null | grep 'state UP')" ]; then \
			echo "[+] [Спроба $$i] USB Tethering вже активний."; \
			exit 0; \
		fi; \
		echo "[-] [Спроба $$i] $(IFACE) вимкнений. Емуляція кліків..."; \
		$(ADB) shell input keyevent 3; \
		sleep 1; \
		$(ADB) shell am start -n com.android.settings/.TetherSettings; \
		sleep 1; \
		$(ADB) shell input tap 800 200; \
		echo "[+] Очікування ініціалізації (2с)..."; \
		sleep 2; \
		$(ADB) shell input keyevent 3; \
	done; \
	echo "==> [ПОМИЛКА] Не вдалося активувати $(IFACE) після $(TETHER_RETRIES) спроб!"; \
	exit 1


py:
	@echo "==> Запуск Python скрипта ($(WIDTH)x$(HEIGHT))..."
	@export WIDTH=$(WIDTH); export HEIGHT=$(HEIGHT); zsh -ic "py streamer.py"

otg:
	scrcpy --otg -s $(DEVICE_ID)

check_device:
	@if ! adb devices | grep -q "$(DEVICE_ID)"; then \
		echo "==> [ПОМИЛКА] Пристрій $(DEVICE_ID) не знайдено!"; \
		exit 1; \
	fi

clean:
	./gradlew clean
	rm -rf $(RELEASE_DIR)

app:
	@echo "==> Запуск додатку..."
	$(ADB) shell am start -n $(PACKAGE_NAME)/$(MAIN_ACTIVITY)

con:
	$(MAKE) tether
	$(MAKE) app
	$(MAKE) py

lock:
	$(ADB)  shell input keyevent 26