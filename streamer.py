import cv2
import socket
import numpy as np
import time
import mss
import pyautogui
import struct
import os

HOST = '192.168.42.129'
PORT = 8080
WIDTH = int(os.environ.get('WIDTH', 960))
HEIGHT = int(os.environ.get('HEIGHT', 720))

print(f"[*] Робоча роздільна здатність: {WIDTH}x{HEIGHT}")

def start_stream():
    print(f"[*] Starting Stable Cyberdeck Streamer...")
    mac_w, mac_h = pyautogui.size()
    
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        prev_frame = None

        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    s.connect((HOST, PORT))
                    print("[+] Connected to Tablet!")

                    while True:
                        start_time = time.time()
                        
                        # Захоплення
                        img = np.array(sct.grab(monitor))[:,:,:3]
                        frame = cv2.resize(img, (WIDTH, HEIGHT))
                        
                        # Курсор
                        mx, my = pyautogui.position()
                        tx = max(0, min(WIDTH-1, int((mx / mac_w) * WIDTH)))
                        ty = max(0, min(HEIGHT-1, int((my / mac_h) * HEIGHT)))
                        cv2.drawMarker(frame, (tx, ty), (90, 90, 90), cv2.MARKER_CROSS, 20, 2)

                        if prev_frame is None:
                            x, y, w, h = 0, 0, WIDTH, HEIGHT
                            dirty = frame
                        else:
                            diff = cv2.absdiff(frame, prev_frame)
                            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
                            _, thresh = cv2.threshold(gray, 8, 255, cv2.THRESH_BINARY)
                            x, y, w, h = cv2.boundingRect(thresh)
                            
                            if w == 0 or h == 0:
                                s.sendall(struct.pack('>4H', 0, 0, 0, 0))
                                time.sleep(0.05) # Жорсткий ліміт для порожніх кадрів
                                continue
                            
                            dirty = frame[y:y+h, x:x+w]

                        prev_frame = frame.copy()
                        data = cv2.cvtColor(dirty, cv2.COLOR_BGR2BGR565).tobytes()
                        
                        s.sendall(struct.pack('>4H', x, y, w, h))
                        s.sendall(data)
                        
                        # Динамічна пауза: тримаємо стабільні 20 FPS (0.05 сек на кадр)
                        elapsed = time.time() - start_time
                        sleep_time = max(0.01, 0.1 - elapsed)
                        time.sleep(sleep_time)

            except Exception as e:
                print(f"[-] Error: {e}. Retrying in 2s...")
                time.sleep(2)
                prev_frame = None

if __name__ == '__main__':
    start_stream()
