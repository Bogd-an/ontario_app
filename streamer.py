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
TARGET_FPS = 15
FRAME_TIME = 1.0 / TARGET_FPS

def start_stream():
    print(f"[*] Starting Streamer {WIDTH}x{HEIGHT} @ {TARGET_FPS}fps")
    mac_w, mac_h = pyautogui.size()

    # Виділяємо буфери ОДИН РАЗ — не в циклі
    prev_frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    
    with mss.mss() as sct:
        monitor = sct.monitors[1]

        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    s.connect((HOST, PORT))
                    print("[+] Connected!")
                    first_frame = True

                    while True:
                        start_time = time.time()

                        # Захоплення
                        raw = sct.grab(monitor)
                        # Використовуємо np.frombuffer замість np.array — без зайвої копії
                        img = np.frombuffer(raw.rgb, dtype=np.uint8).reshape(
                            (raw.height, raw.width, 3))
                        frame = cv2.resize(img, (WIDTH, HEIGHT),
                                           interpolation=cv2.INTER_NEAREST)  # швидший метод

                        # Курсор
                        mx, my = pyautogui.position()
                        tx = max(0, min(WIDTH-1, int((mx / mac_w) * WIDTH)))
                        ty = max(0, min(HEIGHT-1, int((my / mac_h) * HEIGHT)))
                        cv2.drawMarker(frame, (tx, ty), (90, 90, 90),
                                       cv2.MARKER_CROSS, 20, 2)

                        if first_frame:
                            x, y, w, h = 0, 0, WIDTH, HEIGHT
                            dirty = frame
                            first_frame = False
                        else:
                            diff = cv2.absdiff(frame, prev_frame)
                            gray = cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY)
                            _, thresh = cv2.threshold(gray, 8, 255, cv2.THRESH_BINARY)
                            x, y, w, h = cv2.boundingRect(thresh)

                            if w == 0 or h == 0:
                                # Порожній кадр — та ж затримка, що й звичайний
                                elapsed = time.time() - start_time
                                time.sleep(max(0, FRAME_TIME - elapsed))
                                continue

                            dirty = frame[y:y+h, x:x+w]

                        # Копіюємо в буфер БЕЗ .copy() на весь кадр
                        np.copyto(prev_frame, frame)

                        data = cv2.cvtColor(dirty, cv2.COLOR_RGB2BGR565).tobytes()
                        s.sendall(struct.pack('>4H', x, y, w, h))
                        s.sendall(data)

                        elapsed = time.time() - start_time
                        time.sleep(max(0, FRAME_TIME - elapsed))

            except Exception as e:
                print(f"[-] Error: {e}. Retrying in 2s...")
                time.sleep(2)
                first_frame = True

if __name__ == '__main__':
    start_stream()