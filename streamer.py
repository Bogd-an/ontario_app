import cv2
import socket
import numpy as np
import time
import mss
import pyautogui
import struct

HOST = '192.168.42.129'
PORT = 8080

# МАКСИМАЛЬНА РОЗДІЛЬНА ЗДАТНІСТЬ: Full HD
WIDTH = 1920
HEIGHT = 1080

def start_stream():
    print(f"[*] Підключення до Ontario {HOST}:{PORT}")
    mac_w, mac_h = pyautogui.size()
    pyautogui.FAILSAFE = False
    
    with mss.mss() as sct:
        monitor = sct.monitors[1] 

        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    # ЗБІЛЬШЕНО БУФЕР ДО 8 МБ ДЛЯ FULL HD
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8 * 1024 * 1024)
                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    s.connect((HOST, PORT))
                    print(f"[+] З'єднання встановлено! FULL HD MODE...")
                    
                    prev_frame = None

                    while True:
                        sct_img = sct.grab(monitor)
                        img = np.array(sct_img)[:,:,:3] 
                        frame = cv2.resize(img, (WIDTH, HEIGHT))
                        
                        mx, my = pyautogui.position()
                        target_x = max(0, min(WIDTH-1, int((mx / mac_w) * WIDTH)))
                        target_y = max(0, min(HEIGHT-1, int((my / mac_h) * HEIGHT)))
                        
                        cv2.drawMarker(frame, (target_x, target_y), (0, 0, 0), markerType=cv2.MARKER_CROSS, markerSize=22, thickness=4)
                        cv2.drawMarker(frame, (target_x, target_y), (0, 255, 0), markerType=cv2.MARKER_CROSS, markerSize=20, thickness=2)
                        
                        if prev_frame is None:
                            x, y, w, h = 0, 0, WIDTH, HEIGHT
                            dirty_frame = frame
                        else:
                            diff = cv2.absdiff(frame, prev_frame)
                            gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
                            _, thresh = cv2.threshold(gray_diff, 5, 255, cv2.THRESH_BINARY)
                            x, y, w, h = cv2.boundingRect(thresh)
                            
                            if w == 0 or h == 0:
                                s.sendall(struct.pack('>4H', 0, 0, 0, 0))
                                time.sleep(0.01)
                                continue
                                
                            dirty_frame = frame[y:y+h, x:x+w]
                        
                        prev_frame = frame.copy()
                        
                        frame565 = cv2.cvtColor(dirty_frame, cv2.COLOR_BGR2BGR565)
                        raw_bytes = frame565.tobytes()
                        
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
