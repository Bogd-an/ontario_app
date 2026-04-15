import cv2
import socket
import numpy as np
import time
import mss
import pyautogui

HOST = '192.168.42.129'
PORT = 8080
CAPTURE_MODE = 'screen' 
WIDTH = 1280
HEIGHT = 720

def start_stream():
    print(f"[*] Підключення до Ontario {HOST}:{PORT}")
    mac_w, mac_h = pyautogui.size()
    pyautogui.FAILSAFE = False
    
    cap = None
    sct = None
    monitor = None
    
    if CAPTURE_MODE == 'webcam':
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    elif CAPTURE_MODE == 'screen':
        sct = mss.mss()
        monitor = sct.monitors[1] 

    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # РОЗГІН МЕРЕЖІ: Максимальний буфер відправки
                s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                
                s.connect((HOST, PORT))
                print(f"[+] З'єднання встановлено! Транслюємо {CAPTURE_MODE} (TURBO MODE)...")
                
                while True:
                    if CAPTURE_MODE == 'webcam':
                        ret, raw_frame = cap.read()
                        if not ret: continue
                        frame = cv2.resize(raw_frame, (WIDTH, HEIGHT))
                    elif CAPTURE_MODE == 'screen':
                        sct_img = sct.grab(monitor)
                        img = np.array(sct_img)[:,:,:3] 
                        frame = cv2.resize(img, (WIDTH, HEIGHT))
                        
                        mx, my = pyautogui.position()
                        target_x = int((mx / mac_w) * WIDTH)
                        target_y = int((my / mac_h) * HEIGHT)
                        cv2.drawMarker(frame, (target_x, target_y), (0, 0, 0), markerType=cv2.MARKER_CROSS, markerSize=22, thickness=4)
                        cv2.drawMarker(frame, (target_x, target_y), (0, 255, 0), markerType=cv2.MARKER_CROSS, markerSize=20, thickness=2)
                    
                    # РОЗГІН ПРОЦЕСОРА: Використовуємо C++ функцію OpenCV замість математики Numpy
                    # COLOR_BGR2BGR565 ідеально лягає у відеопам'ять Android x86
                    frame565 = cv2.cvtColor(frame, cv2.COLOR_BGR2BGR565)
                    
                    s.sendall(frame565.tobytes())
                    
                    # Ми зняли time.sleep(0.04)! 
                    # Тепер скрипт відправляє кадри зі швидкістю світла (наскільки дозволяє USB)
                    
        except ConnectionRefusedError:
            print("[-] Планшет не готовий. Чекаємо...")
            time.sleep(2)
        except Exception as e:
            print(f"[-] Обрив: {e}. Перепідключення...")
            time.sleep(2)

if __name__ == '__main__':
    start_stream()
