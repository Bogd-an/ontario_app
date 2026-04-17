package com.ontario.app;

import android.app.Activity;
import android.opengl.GLSurfaceView;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;

import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

public class MainActivity extends Activity {

    private GLSurfaceView glSurfaceView;

    static {
        System.loadLibrary("native_stream");
    }

    // --- OpenGL Native Хуки ---
    private native void nativeInitGL();
    private native void nativeResizeGL(int width, int height);
    private native void nativeDrawFrame();

    // --- Мережеві Native Хуки ---
    private native void startNetworkThread();
    private native void stopNetworkThread();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // Забороняємо гаснути екрану
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        
        glSurfaceView = new GLSurfaceView(this);
        
        // Встановлюємо версію OpenGL ES 2.0 (підтримується всіма, ідеально для 2D)
        glSurfaceView.setEGLContextClientVersion(2);
        
        glSurfaceView.setRenderer(new GLSurfaceView.Renderer() {
            @Override
            public void onSurfaceCreated(GL10 gl, EGLConfig config) {
                // Викликається один раз, тут компілюємо шейдери в С
                nativeInitGL();
            }

            @Override
            public void onSurfaceChanged(GL10 gl, int width, int height) {
                // Встановлюємо glViewport у С
                nativeResizeGL(width, height);
            }

            @Override
            public void onDrawFrame(GL10 gl) {
                // Викликається 60 разів на секунду. Тут робимо glTexSubImage2D
                nativeDrawFrame();
            }
        });

        // GLSurfaceView буде викликати onDrawFrame постійно, синхронізовано з VSYNC екрану
        glSurfaceView.setRenderMode(GLSurfaceView.RENDERMODE_CONTINUOUSLY);

        setContentView(glSurfaceView);
        hideSystemUI();

        // Запускаємо сервер. С-код має сам створити pthread для слухання сокетів!
        startNetworkThread();
    }

    private void hideSystemUI() {
        View decorView = getWindow().getDecorView();
        decorView.setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION 
                | View.SYSTEM_UI_FLAG_FULLSCREEN    
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            hideSystemUI();
        }
    }

    // Життєвий цикл GLSurfaceView дуже важливий для запобігання крашів
    @Override
    protected void onResume() {
        super.onResume();
        if (glSurfaceView != null) {
            glSurfaceView.onResume();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (glSurfaceView != null) {
            glSurfaceView.onPause();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        stopNetworkThread();
    }
}