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
	@mkdir -p $(RELEASE_DIR)
	@cp $(APK_PATH) $(RELEASE_DIR)/ontario_app_latest.apk

deploy:
	@echo "==> Встановлення додатку..."
	adb -s $(DEVICE_ID) install -r $(APK_PATH)
	@echo "==> Запуск додатку..."
	adb -s $(DEVICE_ID) shell am start -n $(PACKAGE_NAME)/$(MAIN_ACTIVITY)

scrcpy:
	scrcpy --otg -s $(DEVICE_ID)

clean:
	./gradlew clean
	rm -rf $(RELEASE_DIR)


c:
	git add .
	"$(filter-out $@,$(MAKECMDGOALS))"