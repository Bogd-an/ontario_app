import cv2
import socket
import numpy as np
import time
import mss
import pyautogui

HOST = '192.168.42.129'
PORT = 8080

# HD Роздільна здатність
WIDTH = 1280
HEIGHT = 720

def start_stream():
    print(f"[*] Підключення до Ontario {HOST}:{PORT} (HD 720p + Mouse)")
    
    # Отримуємо логічний розмір екрану Mac для математики миші
    mac_w, mac_h = pyautogui.size()
    
    with mss.mss() as sct:
        monitor = sct.monitors[1] 
        
        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    s.connect((HOST, PORT))
                    print("[+] З'єднання встановлено! Транслюємо екран...")
                    
                    while True:
                        # 1. Скріншот
                        sct_img = sct.grab(monitor)
                        img = np.array(sct_img)[:,:,:3] # Тільки RGB
                        
                        # 2. Зменшення до HD 720p
                        frame = cv2.resize(img, (WIDTH, HEIGHT))
                        
                        # 3. МАЛЮЄМО МИШУ
                        mx, my = pyautogui.position()
                        # Масштабуємо координати Mac -> HD 720p
                        target_x = int((mx / mac_w) * WIDTH)
                        target_y = int((my / mac_h) * HEIGHT)
                        
                        # Малюємо курсор (яскраво-зелений хрестик з чорною обводкою)
                        cv2.drawMarker(frame, (target_x, target_y), (0, 0, 0), markerType=cv2.MARKER_CROSS, markerSize=22, thickness=4)
                        cv2.drawMarker(frame, (target_x, target_y), (0, 255, 0), markerType=cv2.MARKER_CROSS, markerSize=20, thickness=2)
                        
                        # 4. Конвертація BGR -> RGB -> RGB_565
                        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        R = (rgb[..., 0] >> 3).astype(np.uint16)
                        G = (rgb[..., 1] >> 2).astype(np.uint16)
                        B = (rgb[..., 2] >> 3).astype(np.uint16)
                        
                        rgb565 = (R << 11) | (G << 5) | B
                        
                        # 5. Відправка
                        s.sendall(rgb565.tobytes())
                        
                        time.sleep(0.04) 
                        
            except ConnectionRefusedError:
                print("[-] Планшет не готовий. Чекаємо...")
                time.sleep(2)
            except Exception as e:
                print(f"[-] Обрив: {e}. Перепідключення...")
                time.sleep(2)

if __name__ == '__main__':
    # Вимикаємо захист pyautogui (щоб скрипт не падав, якщо відвести мишу в кут)
    pyautogui.FAILSAFE = False
    start_stream()
