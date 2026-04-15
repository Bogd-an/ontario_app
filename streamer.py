import cv2
import socket
import numpy as np
import time
import mss

# --- НАЛАШТУВАННЯ ---
HOST = '192.168.42.129'
PORT = 8080

# Режим захоплення: 'screen' (екран Mac) або 'webcam' (камера)
CAPTURE_MODE = 'screen' 

# Фіксована роздільна здатність для Ontario (НЕ ЗМІНЮВАТИ, інакше впаде Java)
WIDTH = 640
HEIGHT = 480
# --------------------

def start_stream():
    print(f"[*] Підключення до Ontario {HOST}:{PORT}")
    print(f"[*] Режим: {CAPTURE_MODE.upper()} -> RAW RGB_565")
    
    cap = None
    sct = None
    monitor = None
    
    # Ініціалізація джерела
    if CAPTURE_MODE == 'webcam':
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    elif CAPTURE_MODE == 'screen':
        sct = mss.mss()
        monitor = sct.monitors[1] # 1 - головний монітор
    else:
        print("[-] Помилка: Невідомий CAPTURE_MODE!")
        return

    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                s.connect((HOST, PORT))
                print(f"[+] З'єднання встановлено! Транслюємо {CAPTURE_MODE}...")
                
                while True:
                    frame = None
                    
                    # 1. Захоплення кадру залежно від режиму
                    if CAPTURE_MODE == 'webcam':
                        ret, raw_frame = cap.read()
                        if not ret: continue
                        # Примусово підганяємо розмір (про всяк випадок)
                        frame = cv2.resize(raw_frame, (WIDTH, HEIGHT))
                        
                    elif CAPTURE_MODE == 'screen':
                        sct_img = sct.grab(monitor)
                        img = np.array(sct_img)
                        # Відкидаємо альфа-канал і зменшуємо до 640x480
                        frame = cv2.resize(img[:,:,:3], (WIDTH, HEIGHT))
                    
                    # 2. Конвертація кольорів (OpenCV/MSS віддають BGR)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 3. Упаковка в 16-бітний формат дисплея Android (RGB_565)
                    R = (rgb[..., 0] >> 3).astype(np.uint16)
                    G = (rgb[..., 1] >> 2).astype(np.uint16)
                    B = (rgb[..., 2] >> 3).astype(np.uint16)
                    
                    rgb565 = (R << 11) | (G << 5) | B
                    
                    # 4. Відправка сирих байтів прямо у відеопам'ять планшета
                    s.sendall(rgb565.tobytes())
                    
                    time.sleep(0.04)
                    
        except ConnectionRefusedError:
            print("[-] Планшет ще не готовий. Чекаємо...")
            time.sleep(2)
        except Exception as e:
            print(f"[-] Обрив: {e}. Перепідключення...")
            time.sleep(2)

if __name__ == '__main__':
    start_stream()
