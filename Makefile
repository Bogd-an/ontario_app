# Змінні
DEVICE_ID=BaytrailC6A3B6D6
PACKAGE_NAME=com.ontario.app
MAIN_ACTIVITY=.MainActivity
APK_PATH=app/build/outputs/apk/debug/app-debug.apk
RELEASE_DIR=release

.PHONY: all build deploy scrcpy clean

all: build deploy

build:
	@echo "==> Компіляція APK..."
	./gradlew assembleDebug
	@echo "==> Збереження релізу..."
	@mkdir -p $(RELEASE_DIR)
	@cp $(APK_PATH) $(RELEASE_DIR)/ontario_app_latest.apk
	@echo "==> Готово! APK лежить у папці $(RELEASE_DIR)/ontario_app_latest.apk"

deploy:
	@echo "==> Видалення старої версії (якщо є)..."
	adb -s $(DEVICE_ID) uninstall $(PACKAGE_NAME) || true
	@echo "==> Встановлення нової версії..."
	adb -s $(DEVICE_ID) install -r $(APK_PATH)
	@echo "==> Запуск додатку..."
	adb -s $(DEVICE_ID) shell am start -n $(PACKAGE_NAME)/$(MAIN_ACTIVITY)

scrcpy:
	@echo "==> Запуск scrcpy в режимі OTG для керування..."
	scrcpy --otg -s $(DEVICE_ID)

clean:
	@echo "==> Очищення білда..."
	./gradlew clean
	@echo "==> Видалення папки релізу..."
	@rm -rf $(RELEASE_DIR)