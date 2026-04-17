#include <jni.h>
#include <android/log.h>
#include <GLES2/gl2.h>
#include <pthread.h>
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

#define LOG_TAG "OntarioGL"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

#define PORT     8080
#define MAX_W        1024
#define MAX_H        768
#define SOCK_BUF (4 * 1024 * 1024) // 4 МБ для стабільності черги ядра

// --- Стан програми ---
volatile int is_running = 0;
int server_sock = -1;
int client_sock = -1;

// --- Багатопотоковість ---
pthread_t net_thread;
pthread_mutex_t frame_mutex = PTHREAD_MUTEX_INITIALIZER;
volatile int frame_updated = 0;

// --- Буфери ---
uint16_t *master_frame = NULL; // Єдиний справжній кадр (полотно)
uint16_t *net_buffer = NULL;   // Тимчасовий буфер для прийому шматка з мережі

// --- OpenGL ---
GLuint texture_id;
GLuint shader_program;
GLint position_loc, texcoord_loc, sampler_loc;

const char* vertex_shader_src =
    "attribute vec4 a_position;\n"
    "attribute vec2 a_texcoord;\n"
    "varying vec2 v_texcoord;\n"
    "void main() {\n"
    "  gl_Position = a_position;\n"
    "  v_texcoord = a_texcoord;\n"
    "}\n";

const char* fragment_shader_src =
    "precision mediump float;\n"
    "varying vec2 v_texcoord;\n"
    "uniform sampler2D u_sampler;\n"
    "void main() {\n"
    "  gl_FragColor = texture2D(u_sampler, v_texcoord);\n"
    "}\n";

GLuint load_shader(GLenum type, const char* shaderSrc) {
    GLuint shader = glCreateShader(type);
    if (shader == 0) return 0;
    glShaderSource(shader, 1, &shaderSrc, NULL);
    glCompileShader(shader);
    GLint compiled;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &compiled);
    if (!compiled) {
        GLint infoLen = 0;
        glGetShaderiv(shader, GL_INFO_LOG_LENGTH, &infoLen);
        if (infoLen > 1) {
            char* infoLog = malloc(sizeof(char) * infoLen);
            glGetShaderInfoLog(shader, infoLen, NULL, infoLog);
            LOGE("Помилка шейдера:\n%s", infoLog);
            free(infoLog);
        }
        glDeleteShader(shader);
        return 0;
    }
    return shader;
}

// --- МЕРЕЖА ---
ssize_t read_all(int sock, void *buf, size_t count) {
    size_t total = 0;
    char *p = (char *)buf;
    while (total < count && is_running) {
        ssize_t r = recv(sock, p + total, count - total, 0);
        if (r < 0) {
            if (errno == EINTR) continue;
            // EAGAIN означає, що даних поки немає. Чекаємо далі.
            if (errno == EAGAIN || errno == EWOULDBLOCK) continue; 
            return -1; // Справжня помилка
        }
        if (r == 0) return 0; // Клієнт розірвав з'єднання
        total += r;
    }
    return total;
}

void* network_thread_func(void* arg) {
    server_sock = socket(AF_INET, SOCK_STREAM, 0);
    if (server_sock < 0) return NULL;

    int opt = 1;
    setsockopt(server_sock, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    int rcvbuf = SOCK_BUF;
    setsockopt(server_sock, SOL_SOCKET, SO_RCVBUF, &rcvbuf, sizeof(rcvbuf));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(PORT);

    if (bind(server_sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        LOGE("Помилка bind() порту %d", PORT);
        return NULL;
    }
    listen(server_sock, 1);

    while (is_running) {
        LOGI("Очікування підключення...");
        client_sock = accept(server_sock, NULL, NULL);
        if (client_sock < 0) { usleep(100000); continue; }
        LOGI("Клієнт підключений!");

        // Таймаут 15 секунд (щоб не розривалося, коли на Mac нічого не відбувається)
        struct timeval tv = { .tv_sec = 15, .tv_usec = 0 };
        setsockopt(client_sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        int nodelay = 1;
        setsockopt(client_sock, IPPROTO_TCP, TCP_NODELAY, &nodelay, sizeof(nodelay));

        uint16_t header[4];

        while (is_running) {
            // 1. Читаємо заголовок (8 байт)
            if (read_all(client_sock, header, 8) != 8) break;

            uint16_t x = ntohs(header[0]);
            uint16_t y = ntohs(header[1]);
            uint16_t w = ntohs(header[2]);
            uint16_t h = ntohs(header[3]);

            if (w == 0 || h == 0) continue;
            
            // Жорсткий захист від Buffer Overflow
            if (x + w > MAX_W || y + h > MAX_H) {
                LOGE("КРИТИЧНО: Координати за межами екрана (x:%d y:%d w:%d h:%d). Скидання.", x, y, w, h);
                break;
            }

            // 2. Читаємо сирі байти "патчу" у тимчасовий буфер
            size_t bytes = (size_t)w * h * 2;
            if (read_all(client_sock, net_buffer, bytes) != (ssize_t)bytes) break;

            // 3. Блокуємо відеокарту і накладаємо патч ПРЯМО на master_frame
            pthread_mutex_lock(&frame_mutex);
            for (int row = 0; row < h; row++) {
                uint16_t *dst = master_frame + (y + row) * MAX_W + x;
                uint16_t *src = net_buffer + row * w;
                memcpy(dst, src, w * 2);
            }
            frame_updated = 1; // Даємо сигнал OpenGL перемалювати текстуру
            pthread_mutex_unlock(&frame_mutex);
        }

        LOGI("З'єднання розірвано. Перезапуск...");
        if (client_sock != -1) { close(client_sock); client_sock = -1; }
    }
    return NULL;
}


// --- JNI ВЗАЄМОДІЯ (Життєвий цикл) ---
JNIEXPORT void JNICALL
Java_com_ontario_app_MainActivity_startNetworkThread(JNIEnv *env, jobject thiz) {
    if (is_running) return;
    is_running = 1;
    signal(SIGPIPE, SIG_IGN); // Захист від падіння ядра при обриві сокета

    // Виділення пам'яті, вирівняної по 32 байти (для SIMD інструкцій Intel Atom)
    posix_memalign((void**)&master_frame, 32, MAX_W * MAX_H * 2);
    posix_memalign((void**)&net_buffer,   32, MAX_W * MAX_H * 2);
    
    memset(master_frame, 0, MAX_W * MAX_H * 2);

    pthread_create(&net_thread, NULL, network_thread_func, NULL);
}

JNIEXPORT void JNICALL
Java_com_ontario_app_MainActivity_stopNetworkThread(JNIEnv *env, jobject thiz) {
    is_running = 0;
    if (client_sock != -1) shutdown(client_sock, SHUT_RDWR);
    if (server_sock != -1) shutdown(server_sock, SHUT_RDWR);
    pthread_join(net_thread, NULL);
    
    // Блокуємо відеокарту, перед тим як звільнити пам'ять
    pthread_mutex_lock(&frame_mutex);
    if (master_frame) { free(master_frame); master_frame = NULL; }
    if (net_buffer)   { free(net_buffer);   net_buffer   = NULL; }
    pthread_mutex_unlock(&frame_mutex);
}


// --- JNI ВЗАЄМОДІЯ (OpenGL Рендеринг) ---
JNIEXPORT void JNICALL
Java_com_ontario_app_MainActivity_nativeInitGL(JNIEnv *env, jobject thiz) {
    GLuint vertexShader = load_shader(GL_VERTEX_SHADER, vertex_shader_src);
    GLuint fragmentShader = load_shader(GL_FRAGMENT_SHADER, fragment_shader_src);

    shader_program = glCreateProgram();
    glAttachShader(shader_program, vertexShader);
    glAttachShader(shader_program, fragmentShader);
    glLinkProgram(shader_program);

    position_loc = glGetAttribLocation(shader_program, "a_position");
    texcoord_loc = glGetAttribLocation(shader_program, "a_texcoord");
    sampler_loc  = glGetUniformLocation(shader_program, "u_sampler");

    glGenTextures(1, &texture_id);
    glBindTexture(GL_TEXTURE_2D, texture_id);
    
    // Nearest фільтрація найшвидша для такого типу відображення
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

    // Ініціалізація пустої текстури 960x720 у відеопам'яті
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, MAX_W, MAX_H, 0, GL_RGB, GL_UNSIGNED_SHORT_5_6_5, NULL);
}

JNIEXPORT void JNICALL
Java_com_ontario_app_MainActivity_nativeResizeGL(JNIEnv *env, jobject thiz, jint width, jint height) {
    glViewport(0, 0, width, height); 
}

JNIEXPORT void JNICALL
Java_com_ontario_app_MainActivity_nativeDrawFrame(JNIEnv *env, jobject thiz) {
    // Ця функція викликається постійно циклом GLSurfaceView (VSYNC)
    
    glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    glUseProgram(shader_program);

    GLfloat vertices[] = { -1.0f, 1.0f,  -1.0f, -1.0f,  1.0f, 1.0f,  1.0f, -1.0f };
    GLfloat texCoords[] = { 0.0f, 0.0f,   0.0f,  1.0f,  1.0f, 0.0f,  1.0f,  1.0f };

    glVertexAttribPointer(position_loc, 2, GL_FLOAT, GL_FALSE, 0, vertices);
    glEnableVertexAttribArray(position_loc);

    glVertexAttribPointer(texcoord_loc, 2, GL_FLOAT, GL_FALSE, 0, texCoords);
    glEnableVertexAttribArray(texcoord_loc);

    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, texture_id);
    glUniform1i(sampler_loc, 0);

    // Перевіряємо, чи є нові дані для відеокарти
    if (master_frame != NULL && frame_updated) {
        pthread_mutex_lock(&frame_mutex);
        // Заливаємо оновлений кадр у відеокарту (Intel HD Graphics)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, MAX_W, MAX_H, GL_RGB, GL_UNSIGNED_SHORT_5_6_5, master_frame);
        frame_updated = 0;
        pthread_mutex_unlock(&frame_mutex);
    }

    // Малюємо текстуру на весь екран
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

    // ЗАХИСТ ВІД ПЕРЕГРІВУ CPU (Ліміт ~30 FPS).
    usleep(33000); 
}