import subprocess
import time
import os
import sys
import threading
import rumps

print(sys.executable, __file__)

# --- АВТО-ПЕРЕХІД В ПАПКУ ПРОЄКТУ ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

# --- КОНФІГУРАЦІЯ ---
DEVICE_ID = "BaytrailC6A3B6D6"
USB_DEVICE_NAME = "Android"  # Ім'я з твого ioreg логу
STREAMER_SCRIPT = "streamer.py"
POLL_INTERVAL = 2

# --- ДОПОМІЖНІ ФУНКЦІЇ ---

def is_device_physically_connected():
    """Легковажна перевірка через ioreg (тільки для macOS). Не чіпає планшет взагалі."""
    try:
        result = subprocess.run(["ioreg", "-p", "IOUSB", "-w0"], capture_output=True, text=True)
        return USB_DEVICE_NAME in result.stdout
    except Exception:
        return False

def run_make(target):
    """Викликає Makefile та ігнорує вивід, щоб не спамити консоль."""
    try:
        subprocess.run(["make", target], check=True, stdout=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def wait_for_boot():
    """Коли USB підключено, чекаємо поки прокинеться ADB і завантажиться Android."""
    while True:
        try:
            # Тільки тепер ми робимо запит через ADB
            result = subprocess.run(
                ["adb", "-s", DEVICE_ID, "shell", "getprop", "sys.boot_completed"], 
                capture_output=True, text=True
            ).stdout.strip()
            
            if result == "1":
                time.sleep(1) # Даємо системі видихнути
                break
        except Exception:
            pass
        time.sleep(1)


# --- ГОЛОВНИЙ КЛАС ДОДАТКУ ---
class CyberdeckApp(rumps.App):
    def __init__(self):
        super(CyberdeckApp, self).__init__(title="📴", name="Cyberdeck")
        
        self.device_was_connected = False
        self.streamer_process = None
        
        self.status_menu = rumps.MenuItem("Статус: Відключено")
        self.restart_menu = rumps.MenuItem("🔄 Перезапустити стрім", callback=self.manual_restart)
        
        self.menu = [
            self.status_menu,
            None,
            self.restart_menu
        ]

        self.monitor_thread = threading.Thread(target=self.daemon_loop)
        self.monitor_thread.daemon = True 
        self.monitor_thread.start()

    def manual_restart(self, _):
        """Ручний перезапуск стрімера з меню"""
        if self.streamer_process and self.streamer_process.poll() is None:
            self.streamer_process.terminate()
            self.streamer_process.wait()
        
        if is_device_physically_connected():
            self.streamer_process = subprocess.Popen([sys.executable, STREAMER_SCRIPT])
            rumps.notification("Cyberdeck", "Стрім перезапущено", "Скрипт streamer.py запущено вручну.")

    def daemon_loop(self):
        """Фоновий моніторинг USB (Легковажний)"""
        while True:
            # Тепер ми перевіряємо тільки ядро macOS (ioreg), жодних ADB-запитів!
            connected = is_device_physically_connected()

            # --- ПЛАНШЕТ ПІДКЛЮЧЕНО ---
            if connected and not self.device_was_connected:
                self.title = "⚙️" 
                self.status_menu.title = "Статус: Налаштування..."
                
                # 1. Чекаємо ADB та Android
                wait_for_boot()
                
                # 2. Вмикаємо USB-модем
                if run_make("tether"):
                    # 3. СПОЧАТКУ запускаємо додаток (щоб він відкрив порт 8080)
                    run_make("app")
                    
                    # 4. Даємо планшету 2 секунди на ініціалізацію OpenGL та сокетів
                    time.sleep(2.0)
                    
                    # 5. ТІЛЬКИ ПОТІМ запускаємо Python-клієнт
                    self.streamer_process = subprocess.Popen([sys.executable, STREAMER_SCRIPT])
                    
                    self.title = "👾" 
                    self.status_menu.title = "Статус: Онлайн (Стрім іде)"
                    rumps.notification("Cyberdeck", "Планшет підключено!", "Сервер готовий, додаток запущено.")
                
                self.device_was_connected = True

            # --- ПЛАНШЕТ ВІДКЛЮЧЕНО ---
            elif not connected and self.device_was_connected:
                self.title = "📴"
                self.status_menu.title = "Статус: Відключено"
                
                if self.streamer_process and self.streamer_process.poll() is None:
                    self.streamer_process.terminate()
                    self.streamer_process.wait()
                    self.streamer_process = None
                
                rumps.notification("Cyberdeck", "Планшет відключено", "Стрімер зупинено.")
                self.device_was_connected = False

            # --- КРАШ СТРІМЕРА ---
            if connected and self.streamer_process and self.streamer_process.poll() is not None:
                self.streamer_process = subprocess.Popen([sys.executable, STREAMER_SCRIPT])

            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    app = CyberdeckApp()
    app.run()