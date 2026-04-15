import cv2
import socket
import numpy as np
import time
import mss
import pyautogui
import struct

HOST = '192.168.42.129'
PORT = 8080
WIDTH = 1280
HEIGHT = 720

def start_stream():
    print(f"[*] Підключення до Ontario {HOST}:{PORT}")
    mac_w, mac_h = pyautogui.size()
    pyautogui.FAILSAFE = False
    
    with mss.mss() as sct:
        monitor = sct.monitors[1] 

        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    s.connect((HOST, PORT))
                    print(f"[+] З'єднання встановлено! DIRTY RECTANGLES MODE...")
                    
                    prev_frame = None

                    while True:
                        # 1. Скріншот та курсор
                        sct_img = sct.grab(monitor)
                        img = np.array(sct_img)[:,:,:3] 
                        frame = cv2.resize(img, (WIDTH, HEIGHT))
                        
                        mx, my = pyautogui.position()
                        target_x = max(0, min(WIDTH-1, int((mx / mac_w) * WIDTH)))
                        target_y = max(0, min(HEIGHT-1, int((my / mac_h) * HEIGHT)))
                        
                        cv2.drawMarker(frame, (target_x, target_y), (0, 0, 0), markerType=cv2.MARKER_CROSS, markerSize=22, thickness=4)
                        cv2.drawMarker(frame, (target_x, target_y), (0, 255, 0), markerType=cv2.MARKER_CROSS, markerSize=20, thickness=2)
                        
                        # 2. АЛГОРИТМ БРУДНИХ ПРЯМОКУТНИКІВ
                        if prev_frame is None:
                            x, y, w, h = 0, 0, WIDTH, HEIGHT
                            dirty_frame = frame
                        else:
                            # Шукаємо різницю між поточним і минулим кадром
                            diff = cv2.absdiff(frame, prev_frame)
                            gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
                            
                            # Відсікаємо мікрошум
                            _, thresh = cv2.threshold(gray_diff, 5, 255, cv2.THRESH_BINARY)
                            
                            # Знаходимо межі усіх змін
                            x, y, w, h = cv2.boundingRect(thresh)
                            
                            if w == 0 or h == 0:
                                # Змін немає! Відправляємо Keep-Alive пакет (8 байт)
                                s.sendall(struct.pack('>4H', 0, 0, 0, 0))
                                time.sleep(0.01)
                                continue
                                
                            # Вирізаємо ТІЛЬКИ те, що змінилося
                            dirty_frame = frame[y:y+h, x:x+w]
                        
                        # Зберігаємо кадр для наступного порівняння
                        prev_frame = frame.copy()
                        
                        # 3. Конвертуємо лише брудний шматочок у RGB_565
                        frame565 = cv2.cvtColor(dirty_frame, cv2.COLOR_BGR2BGR565)
                        raw_bytes = frame565.tobytes()
                        
                        # 4. Відправляємо заголовок (X, Y, Ширина, Висота) + Payload
                        # '>4H' означає 4 Unsigned Shorts у Big Endian
                        s.sendall(struct.pack('>4H', x, y, w, h))
                        s.sendall(raw_bytes)
                        
            except ConnectionRefusedError:
                print("[-] Планшет не готовий. Чекаємо...")
                time.sleep(2)
            except Exception as e:
                print(f"[-] Обрив: {e}. Перепідключення...")
                time.sleep(2)

if __name__ == '__main__':
    start_stream()
