import cv2
import socket
import numpy as np
import time
import mss
import pyautogui
import struct
import os

# Конфігурація
HOST = '192.168.42.129'
PORT = 8080
WIDTH = int(os.environ.get('WIDTH', 1024))
HEIGHT = int(os.environ.get('HEIGHT', 768))
TARGET_FPS = 15  # Обмеження FPS для розвантаження Intel Atom
FRAME_TIME = 1.0 / TARGET_FPS
OFFSET_X = 2     # Зсув курсора вліво

TIMEOUT = 5  # Таймаут для підключення (секунди)

# Завантаження та масштаб курсора (виконується ОДИН РАЗ при старті)
cursor_path = os.path.join(os.path.dirname(__file__), 'mac-cursor.png')
cursor_raw = cv2.imread(cursor_path, cv2.IMREAD_UNCHANGED)

if cursor_raw is not None:
    mac_w, mac_h = pyautogui.size()
    # Розраховуємо коефіцієнт масштабування
    scale_factor = (WIDTH / mac_w) / 15
    new_cw = max(1, int(cursor_raw.shape[1] * scale_factor))
    new_ch = max(1, int(cursor_raw.shape[0] * scale_factor))
    
    cursor_img = cv2.resize(cursor_raw, (new_cw, new_ch), interpolation=cv2.INTER_AREA)
    # Поділяємо на канали заздалегідь для швидкості
    cursor_rgb = cursor_img[:, :, :3]
    cursor_alpha = (cursor_img[:, :, 3:] / 255.0).astype(np.float32)
else:
    cursor_img = None

def start_stream():
    print(f"[*] Starting Streamer {WIDTH}x{HEIGHT} for Ontario 2")
    mac_w, mac_h = pyautogui.size()

    # Попередньо виділений буфер для порівняння кадрів
    prev_frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    
    # Виносимо лічильник таймауту ЗА межі циклу підключень
    current_timeout = TIMEOUT
    
    with mss.mss() as sct:
        monitor = sct.monitors[1]

        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    # Встановлюємо системний таймаут, щоб connect не висів вічно
                    s.settimeout(2.0)
                    s.connect((HOST, PORT))
                    
                    # Після успішного підключення повертаємо сокет у звичайний режим
                    s.settimeout(None)
                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    print("[+] Connected!")
                    
                    # Скидаємо таймаут після успішного підключення
                    current_timeout = TIMEOUT 
                    first_frame = True

                    while True:
                        start_time = time.time()

                        # 1. Захоплення екрана
                        raw = sct.grab(monitor)
                        img = np.frombuffer(raw.rgb, dtype=np.uint8).reshape((raw.height, raw.width, 3))
                        frame = cv2.resize(img, (WIDTH, HEIGHT), interpolation=cv2.INTER_NEAREST)

                        # 2. Малювання курсора
                        mx, my = pyautogui.position()
                        tx = max(0, int((mx / mac_w) * WIDTH) - OFFSET_X)
                        ty = max(0, int((my / mac_h) * HEIGHT))

                        if cursor_img is not None:
                            ch, cw = cursor_img.shape[:2]
                            x1, y1 = tx, ty
                            x2, y2 = min(WIDTH, tx + cw), min(HEIGHT, ty + ch)
                            
                            cx2, cy2 = x2 - x1, y2 - y1

                            if x2 > x1 and y2 > y1:
                                roi = frame[y1:y2, x1:x2]
                                c_alpha = cursor_alpha[:cy2, :cx2]
                                c_rgb = cursor_rgb[:cy2, :cx2]
                                
                                frame[y1:y2, x1:x2] = (c_rgb * c_alpha + roi * (1.0 - c_alpha)).astype(np.uint8)
                        else:
                            cv2.drawMarker(frame, (tx, ty), (120, 120, 120), cv2.MARKER_CROSS, 15, 1)

                        # 3. Виявлення зміненої області (Dirty Rect)
                        if first_frame:
                            x, y, w, h = 0, 0, WIDTH, HEIGHT
                            dirty = frame
                            first_frame = False
                        else:
                            diff = cv2.absdiff(frame, prev_frame)
                            gray = cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY)
                            _, thresh = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
                            x, y, w, h = cv2.boundingRect(thresh)

                            if w == 0 or h == 0:
                                # Пульс (Heartbeat) - фіксовані координати та розмір
                                x, y, w, h = 0, 0, 1, 1
                                dirty = np.zeros((1, 1, 3), dtype=np.uint8)
                            else:
                                # ВИПРАВЛЕНО: Тепер обрізка відбувається ТІЛЬКИ якщо є реальні зміни
                                x = max(0, x)
                                y = max(0, y)
                                w = min(w, WIDTH - x)
                                h = min(h, HEIGHT - y)
                                dirty = frame[y:y+h, x:x+w]

                        # Зберігаємо поточний стан
                        np.copyto(prev_frame, frame)

                        # 4. Конвертація та відправка
                        data = cv2.cvtColor(dirty, cv2.COLOR_RGB2BGR565).tobytes()
                        s.sendall(struct.pack('>4H', x, y, w, h))
                        s.sendall(data)

                        # 5. Контроль FPS
                        elapsed = time.time() - start_time
                        time.sleep(max(0, FRAME_TIME - elapsed))

            except Exception as e:
                print(f"[-] Error: {e}. Retrying in 1s... timeout={current_timeout}")
                time.sleep(0.5)
                current_timeout -= 1
                
                if current_timeout <= 0:
                    print("[-] Connection timeout. Restarting streamer wait cycle.")
                    # Скидаємо таймаут, щоб скрипт просто продовжив чекати планшет нескінченно,
                    # замість того, щоб завершувати роботу (break).
                    current_timeout = TIMEOUT 
                    break

if __name__ == '__main__':
    try:
        start_stream()
    except KeyboardInterrupt:
        print("\n[!] Streamer stopped by user.")