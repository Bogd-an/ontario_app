#include <jni.h>
#include <android/native_window.h>
#include <android/native_window_jni.h>
#include <android/rect.h>
#include <android/log.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
#include <sys/time.h>
#include <errno.h>
#include <signal.h>

#define LOG_TAG "OntarioNative"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

#define PORT     8080
#define MAX_W        960
#define MAX_H        720
#define SOCK_BUF (2 * 1024 * 1024)

volatile int is_running = 0;
int server_sock = -1;
int client_sock = -1;

// Захищене читання з обробкою переривань
ssize_t read_all(int sock, void *buf, size_t count) {
    size_t total = 0;
    char *p = (char *)buf;
    while (total < count && is_running) {
        ssize_t r = recv(sock, p + total, count - total, 0);
        if (r < 0) {
            if (errno == EINTR) continue;
            if (errno == EAGAIN || errno == EWOULDBLOCK) return total;
            return -1;
        }
        if (r == 0) return 0; // Сокет закрито
        total += r;
    }
    return total;
}

JNIEXPORT void JNICALL
Java_com_ontario_app_MainActivity_startNativeStream(
        JNIEnv *env, jobject thiz, jobject surface, jint width, jint height) {

    LOGI("Запуск %dx%d...", width, height);
    is_running = 1;
    
    // Ігноруємо SIGPIPE, щоб додаток не падав при різкому обриві з'єднання
    signal(SIGPIPE, SIG_IGN);

    ANativeWindow *window = ANativeWindow_fromSurface(env, surface);
    if (!window) return;
    ANativeWindow_setBuffersGeometry(window, width, height, WINDOW_FORMAT_RGB_565);

    uint16_t *master_frame = NULL;
    uint16_t *net_buffer = NULL;

    // ВИПРАВЛЕННЯ 1: Вирівнювання пам'яті для x86 (Intel Atom дуже чутливий до цього)
    posix_memalign((void**)&master_frame, 32, MAX_W * MAX_H * 2);
    posix_memalign((void**)&net_buffer, 32, MAX_W * MAX_H * 2);

    if (!master_frame || !net_buffer) {
        LOGE("Не вистачає RAM!");
        if(master_frame) free(master_frame);
        if(net_buffer) free(net_buffer);
        ANativeWindow_release(window);
        return;
    }
    memset(master_frame, 0, MAX_W * MAX_H * 2);

    server_sock = socket(AF_INET, SOCK_STREAM, 0);
    if (server_sock < 0) {
        free(master_frame); free(net_buffer);
        ANativeWindow_release(window);
        return;
    }

    int opt = 1;
    setsockopt(server_sock, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    int rcvbuf = SOCK_BUF;
    setsockopt(server_sock, SOL_SOCKET, SO_RCVBUF, &rcvbuf, sizeof(rcvbuf));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port        = htons(PORT);

    if (bind(server_sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(server_sock);
        free(master_frame); free(net_buffer);
        ANativeWindow_release(window);
        return;
    }
    listen(server_sock, 1);

    while (is_running) {
        LOGI("Очікування підключення...");
        client_sock = accept(server_sock, NULL, NULL);
        if (client_sock < 0) {
            usleep(100000); // Запобігає 100% CPU, якщо accept сипле помилками
            continue;
        }
        LOGI("Підключено!");

        struct timeval tv = { .tv_sec = 2, .tv_usec = 0 }; // Трохи зменшив таймаут
        setsockopt(client_sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        int nodelay = 1;
        setsockopt(client_sock, IPPROTO_TCP, TCP_NODELAY, &nodelay, sizeof(nodelay));

        memset(master_frame, 0, MAX_W * MAX_H * 2);
        uint16_t header[4];

        while (is_running) {
            ssize_t h_read = read_all(client_sock, header, 8);
            if (h_read <= 0) { LOGI("Розірвано"); break; }
            if (h_read != 8) { LOGE("Битий заголовок"); break; }

            uint16_t x = ntohs(header[0]);
            uint16_t y = ntohs(header[1]);
            uint16_t w = ntohs(header[2]);
            uint16_t h = ntohs(header[3]);

            if (w == 0 || h == 0) continue;

            if (x + w > MAX_W || y + h > MAX_H) {
                LOGE("Координати за межами: x=%d y=%d w=%d h=%d", x, y, w, h);
                break;
            }

            size_t bytes = (size_t)w * h * 2;
            ssize_t p_read = read_all(client_sock, net_buffer, bytes);
            if (p_read != (ssize_t)bytes) { LOGE("Неповний кадр"); break; }

            // Оновлюємо master_frame (наше внутрішнє сховище)
            for (int row = 0; row < h; row++) {
                uint16_t *dst = master_frame + (y + row) * MAX_W + x;
                uint16_t *src = net_buffer   + row * w;
                memcpy(dst, src, (size_t)w * 2);
            }

            // ВИПРАВЛЕННЯ 2: Використовуємо Dirty Rects замість копіювання всього екрану
            ARect dirtyBounds;
            dirtyBounds.left   = x;
            dirtyBounds.top    = y;
            dirtyBounds.right  = x + w;
            dirtyBounds.bottom = y + h;

            ANativeWindow_Buffer buf;
            // Передаємо dirtyBounds. Система сама вирішить, яку область нам дозволити перемалювати
            if (ANativeWindow_lock(window, &buf, &dirtyBounds) != 0) {
                usleep(5000); // Чекаємо, якщо Surface тимчасово недоступний
                continue;
            }

            // Копіюємо ТІЛЬКИ ту область, яку запросила система (вона може бути ширшою за наш патч)
            int copy_w = dirtyBounds.right - dirtyBounds.left;
            int copy_h = dirtyBounds.bottom - dirtyBounds.top;

            for (int row = 0; row < copy_h; row++) {
                int src_y = dirtyBounds.top + row;
                if (src_y >= MAX_H) break; // Захист від виходу за межі

                uint16_t *src = master_frame + src_y * MAX_W + dirtyBounds.left;
                uint16_t *dst = (uint16_t *)buf.bits + (src_y * buf.stride) + dirtyBounds.left;
                
                memcpy(dst, src, copy_w * 2);
            }

            ANativeWindow_unlockAndPost(window);
        }

        LOGI("Закриваємо з'єднання...");
        if (client_sock != -1) {
            shutdown(client_sock, SHUT_RDWR);
            close(client_sock);
            client_sock = -1;
        }
    }

    free(master_frame);
    free(net_buffer);
    ANativeWindow_release(window);
}

JNIEXPORT void JNICALL
Java_com_ontario_app_MainActivity_stopNativeStream(JNIEnv *env, jobject thiz) {
    is_running = 0;
    // Жорстко перериваємо блокуючі виклики accept() та recv()
    if (client_sock != -1) { shutdown(client_sock, SHUT_RDWR); close(client_sock); }
    if (server_sock != -1) { shutdown(server_sock, SHUT_RDWR); close(server_sock); }
}