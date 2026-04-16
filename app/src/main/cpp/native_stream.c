#include <jni.h>
#include <android/native_window.h>
#include <android/native_window_jni.h>
#include <android/log.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
#include <sys/time.h>
#include <errno.h>
#include <signal.h> // ДОДАНО: Для захисту від SIGPIPE

#define LOG_TAG "OntarioNative"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

#define PORT 8080
#define MAX_PHYS_WIDTH 1024
#define MAX_PHYS_HEIGHT 768

volatile int is_running = 0;
int server_sock = -1;
int client_sock = -1;

// Функція читання з максимальним захистом від зависань
ssize_t read_all(int sock, void *buf, size_t count) {
    size_t total_read = 0;
    char *char_buf = (char *)buf;
    
    while (total_read < count && is_running) {
        ssize_t r = recv(sock, char_buf + total_read, count - total_read, 0);
        
        if (r < 0) {
            if (errno == EINTR) continue; // Перервано, але безпечно
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                return total_read; // Тайм-аут: віддаємо, що встигли зібрати
            }
            return -1; // Фатальна мережева помилка
        }
        if (r == 0) return 0; // Mac коректно розірвав з'єднання
        
        total_read += r;
    }
    return total_read;
}

JNIEXPORT void JNICALL
Java_com_ontario_app_MainActivity_startNativeStream(JNIEnv *env, jobject thiz, jobject surface, jint width, jint height) {
    LOGI("Запуск нативного стріму...");
    is_running = 1;

    // ЗАХИСТ #1: Блокуємо сигнал SIGPIPE, який вбиває Android-додатки при обриві мережі
    signal(SIGPIPE, SIG_IGN);

    ANativeWindow *window = ANativeWindow_fromSurface(env, surface);
    if (!window) return;
    ANativeWindow_setBuffersGeometry(window, width, height, WINDOW_FORMAT_RGB_565);

    size_t max_frame_size = MAX_PHYS_WIDTH * MAX_PHYS_HEIGHT * 2;
    uint16_t *master_frame = (uint16_t *)malloc(max_frame_size);
    uint16_t *net_buffer = (uint16_t *)malloc(max_frame_size);
    
    // ЗАХИСТ #2: Перевірка, чи вистачило пам'яті
    if (!master_frame || !net_buffer) {
        LOGE("КРИТИЧНА ПОМИЛКА: Не вистачає RAM!");
        if (master_frame) free(master_frame);
        if (net_buffer) free(net_buffer);
        ANativeWindow_release(window);
        return;
    }
    
    memset(master_frame, 0, max_frame_size);

    server_sock = socket(AF_INET, SOCK_STREAM, 0);
    if (server_sock < 0) {
        free(master_frame); free(net_buffer); ANativeWindow_release(window);
        return;
    }

    int opt = 1;
    setsockopt(server_sock, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in server_addr;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(PORT);

    if (bind(server_sock, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        close(server_sock); free(master_frame); free(net_buffer); ANativeWindow_release(window);
        return;
    }

    listen(server_sock, 1);

    while (is_running) {
        LOGI("Очікування підключення від Mac...");
        client_sock = accept(server_sock, NULL, NULL);
        if (client_sock < 0) continue;
        
        LOGI("Mac підключився!");

        // ЗАХИСТ #3: Тайм-аут сокета. Якщо Mac завис - чекаємо 2 секунди і відкидаємо.
        struct timeval tv;
        tv.tv_sec = 2;  
        tv.tv_usec = 0;
        setsockopt(client_sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof(tv));

        uint16_t header[4]; 
        
        while (is_running) {
            ssize_t h_read = read_all(client_sock, header, 8);
            if (h_read <= 0) {
                LOGI("Mac розірвав з'єднання (r=0)");
                break;
            }
            if (h_read != 8) {
                LOGE("Тайм-аут або битий заголовок. Розрив.");
                break; 
            }

            uint16_t x = ntohs(header[0]);
            uint16_t y = ntohs(header[1]);
            uint16_t w = ntohs(header[2]);
            uint16_t h = ntohs(header[3]);

            if (w == 0 || h == 0) {
                usleep(1000); // Захист від того, що Mac шле пусті кадри зі швидкістю світла
                continue; 
            }

            if (x + w > MAX_PHYS_WIDTH || y + h > MAX_PHYS_HEIGHT) {
                LOGE("Помилка координат: %d+%d > %d", x, w, MAX_PHYS_WIDTH);
                sleep(1); // ЗАХИСТ #4: Гальмуємо процес, щоб уникнути нескінченного циклу крашів
                break;
            }

            size_t bytes_to_read = w * h * 2;
            ssize_t p_read = read_all(client_sock, net_buffer, bytes_to_read);
            
            if (p_read != bytes_to_read) {
                LOGE("Неповний кадр! Скидання з'єднання.");
                break;
            }

            // Малюємо в пам'ять
            for (int row = 0; row < h; row++) {
                uint16_t *dst = master_frame + ((y + row) * MAX_PHYS_WIDTH) + x;
                uint16_t *src = net_buffer + (row * w);
                memcpy(dst, src, w * 2);
            }

            // Відправляємо на екран
            ANativeWindow_Buffer buffer;
            if (ANativeWindow_lock(window, &buffer, NULL) == 0) {
                uint16_t *out_pixels = (uint16_t *)buffer.bits;

                int safe_w = (width < buffer.width) ? width : buffer.width;
                int safe_h = (height < buffer.height) ? height : buffer.height;

                for (int row = 0; row < safe_h; row++) {
                    uint16_t *dst = out_pixels + (row * buffer.stride);
                    uint16_t *src = master_frame + (row * MAX_PHYS_WIDTH);
                    memcpy(dst, src, safe_w * 2);
                }

                ANativeWindow_unlockAndPost(window);
                usleep(1500); 
            }
        }

        // ЗАХИСТ #5: М'яке закриття (Graceful Shutdown) для старих USB-драйверів
        LOGI("Початок очищення з'єднання...");
        if (client_sock != -1) {
            shutdown(client_sock, SHUT_RDWR); // Кажемо ядру зупинити передачу
            usleep(50000); // Чекаємо 50 мс, щоб ядро встигло скинути USB-буфери
            close(client_sock);
            client_sock = -1;
        }
        LOGI("Готово до нового підключення.");
    }

    free(master_frame);
    free(net_buffer);
    ANativeWindow_release(window);
}

JNIEXPORT void JNICALL
Java_com_ontario_app_MainActivity_stopNativeStream(JNIEnv *env, jobject thiz) {
    is_running = 0;
    if (client_sock != -1) {
        shutdown(client_sock, SHUT_RDWR);
        close(client_sock);
    }
    if (server_sock != -1) {
        shutdown(server_sock, SHUT_RDWR);
        close(server_sock);
    }
}