# 📱 Ontario BayTrail Project (Android 4.4.4)

Цей проект — мінімалістичний, CLI-орієнтований Android-додаток, створений спеціально для запуску на legacy-обладнанні з архітектурою **Intel Bay Trail (x86)**, ядром **3.10.20** та **Android 4.4.4 (KitKat)**.

Проект створено з акцентом на продуктивність та мінімальне споживання ресурсів: **без Android Studio**, **без важких бібліотек AndroidX** та **без зайвого сміття**. Збірка та керування пристроєм відбуваються виключно через термінал за допомогою `Makefile`.

---

## ✨ Особливості

* **Чистий Android SDK (API 19):** Відсутність AppCompat/AndroidX гарантує мінімальний розмір APK (лічені кілобайти) та миттєвий запуск на старому залізі.
* **Термінальна збірка (CLI-First):** Використовується Gradle 7.5.1 (через локальний wrapper) та мінімальний набір консольних утиліт (Command Line Tools) від Google.
* **Автоматизація через Make:** Всі рутинні задачі (збірка, встановлення, запуск) зведені до простих команд типу `make build`.
* **Апаратне керування (OTG):** Інтегрована підтримка `scrcpy --otg` для керування пристроєм на рівні HID (емуляція клавіатури/миші), що є критично важливим для Android < 5.0, де звичайний режим захоплення екрана `scrcpy` не працює.

---

## 🛠 Вимоги до системи (Хост-машина)

* **ОС:** macOS або Linux (протестовано на macOS з Zsh).
* **Java:** Java 11 (необхідна для коректної роботи Gradle 7.5.1).
* **Утиліти:**
    * `make`
    * `adb` (Android Debug Bridge)
    * `scrcpy` (з підтримкою OTG)
* **Android SDK:** Локально розгорнутий мінімальний SDK (платформи 19, 33 та Build Tools).

---

## 🚀 Швидкий старт

### 1. Налаштування SDK
Переконайтеся, що у корені проекту існує файл `local.properties` із правильним шляхом до вашого Android SDK.
Приклад для macOS:
\`\`\`properties
sdk.dir=/Users/ВАШ_ЮЗЕР/Android/Sdk
\`\`\`

### 2. Підключення пристрою
Підключіть ваш пристрій (ID: `BaytrailC6A3B6D6`) через USB і переконайтеся, що він визначається системою:
\`\`\`bash
adb devices
\`\`\`
*Має з'явитися рядок `BaytrailC6A3B6D6    device`.*

---

## 🕹 Керування проектом (Makefile)

Вся магія відбувається через файл `Makefile`. Перейдіть у корінь проекту та використовуйте наступні команди:

| Команда | Опис |
| :--- | :--- |
| \`make build\` | Стягує залежності та компілює \`app-debug.apk\`. |
| \`make deploy\` | Видаляє стару версію з пристрою, встановлює нову і миттєво запускає її. |
| \`make scrcpy\` | Запускає \`scrcpy\` у режимі OTG для апаратного керування пристроєм (емуляція миші/клавіатури). |
| \`make all\` | **Комбо:** Компілює, встановлює та запускає додаток однією командою. |
| \`make clean\` | Очищує директорії збірки (видаляє папку \`build/\`). |

---

## ⚠️ Відомі проблеми та нюанси

1. **Gradle та нові версії Java:** Проект жорстко прив'язаний до плагіна Android Gradle `7.4.2` та `Gradle 7.5.1`. Спроба зібрати проект на Java 17+ або новішим Gradle призведе до помилок (наприклад, \`UnsupportedClassVersionError\`).
2. **Ліцензії SDK:** Якщо ви розгортаєте SDK вручну, переконайтеся, що хеш-суми ліцензій додані в папку \`licenses\` вашого SDK, інакше Gradle відмовиться завантажувати потрібні платформи.
3. **Scrcpy OTG:** Пам'ятайте, що режим OTG не транслює екран пристрою на монітор (через обмеження Android 4.4), а лише дозволяє сліпо керувати ним як USB-периферією.

---
*Created for the Ontario BayTrail Revival Project. Keep hacking! 💻*



---

```markdown
# 🛠 Підготовка робочого місця (Environment Setup)

Щоб розгорнути цей проект на новому комп'ютері, вам потрібно встановити базові системні залежності. 

## 🍏 Для macOS (через Homebrew)

Якщо у вас ще не встановлений [Homebrew](https://brew.sh/), встановіть його, а потім виконайте:

```bash
# 1. Встановлюємо Java 11 (критично для Gradle 7.5)
brew install openjdk@11

# Прописуємо Java 11 в систему (додайте це у ваш ~/.zshrc)
export PATH="/usr/local/opt/openjdk@11/bin:$PATH"
export JAVA_HOME="/usr/local/opt/openjdk@11"

# 2. Встановлюємо ADB (Android Command Line Tools)
brew install --cask android-platform-tools

# 3. Встановлюємо Scrcpy для керування (OTG)
brew install scrcpy

# Make зазвичай вже є на macOS, якщо ні — встановіть Xcode Command Line Tools:
xcode-select --install
```

## 🐧 Для Linux (Ubuntu / Debian)

Встановлення через стандартний пакетний менеджер `apt`:

```bash
# Оновлюємо список пакетів
sudo apt update

# Встановлюємо Make, Java 11 та ADB
sudo apt install -y make openjdk-11-jdk adb

# Встановлюємо Scrcpy
sudo apt install -y scrcpy
```

## 🪟 Для Windows

Оскільки проект використовує `Makefile` та `bash`-скрипти, найкращий спосіб працювати на Windows — це використовувати **WSL (Windows Subsystem for Linux)** з встановленою Ubuntu.
Просто встановіть WSL (`wsl --install` у PowerShell) і виконайте кроки для Linux, описані вище.

Для роботи ADB та Scrcpy безпосередньо з Windows, встановіть їх через [Scoop](https://scoop.sh/):
```powershell
scoop install main/adb
scoop install extras/scrcpy
scoop install java/openjdk11
```

---

## 🚀 Що далі? (Алгоритм запуску на новому ПК)

Коли системні утиліти встановлені, просто виконайте ці кроки:

1. **Клонуйте репозиторій:**
   ```bash
   git clone <посилання_на_ваш_репо>
   cd ontario_app
   ```

2. **Завантажте та налаштуйте Android SDK:**
   *(Виконайте цей блок прямо в терміналі, він завантажить мінімальний SDK і створить ліцензії)*
   ```bash
   mkdir -p ~/Android/Sdk/cmdline-tools
   curl -o tools.zip [https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip](https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip) # Для Mac
   # (Або commandlinetools-linux-...zip для Linux)
   unzip -q tools.zip -d ~/Android/Sdk/cmdline-tools
   mv ~/Android/Sdk/cmdline-tools/cmdline-tools ~/Android/Sdk/cmdline-tools/latest
   rm tools.zip
   
   yes | ~/Android/Sdk/cmdline-tools/latest/bin/sdkmanager "platforms;android-33" "platforms;android-19" "build-tools;33.0.2" "platform-tools"
   
   mkdir -p ~/Android/Sdk/licenses
   echo -e "\n24333f8a63b6825ea9c5514f83c2829b004d1fee\n8933bad161af4178b1185d1a37fbf41ea5269c55\nd56f5187479451eabf01fb78af6dfcb131a6481e" > ~/Android/Sdk/licenses/android-sdk-license
   ```

3. **Створіть локальний конфіг:**
   ```bash
   echo "sdk.dir=/Users/$(whoami)/Android/Sdk" > local.properties
   ```

4. **Запускайте!** *(Gradle завантажиться автоматично)*
   ```bash
   make all
   ```
```