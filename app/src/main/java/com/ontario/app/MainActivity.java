package com.ontario.app;

import android.app.Activity;
import android.os.Bundle;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.View;
import android.view.WindowManager;

public class MainActivity extends Activity implements SurfaceHolder.Callback {

    // Фізичний максимум екрана, який ми передамо в C-код
    private final int FRAME_WIDTH = 960;
    private final int FRAME_HEIGHT = 720;
    
    private SurfaceView surfaceView;
    private Thread nativeThread;

    static {
        System.loadLibrary("native_stream");
    }

    private native void startNativeStream(Surface surface, int width, int height);
    private native void stopNativeStream();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // Забороняємо гаснути екрану
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        
        surfaceView = new SurfaceView(this);
        setContentView(surfaceView);
        surfaceView.getHolder().addCallback(this);

        // Ховаємо інтерфейс при запуску
        hideSystemUI();
    }

    // Режим Immersive Sticky (Android 4.4+)
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
        // Знову ховаємо кнопки, якщо вони випадково з'явилися
        if (hasFocus) {
            hideSystemUI();
        }
    }

    @Override
    public void surfaceCreated(final SurfaceHolder holder) {
        nativeThread = new Thread(new Runnable() {
            @Override
            public void run() {
                // ОПТ: Підвищуємо пріоритет потоку — менше переривань від ОС
                android.os.Process.setThreadPriority(
                    android.os.Process.THREAD_PRIORITY_URGENT_DISPLAY
                );
                startNativeStream(holder.getSurface(), FRAME_WIDTH, FRAME_HEIGHT);
            }
        });
        nativeThread.setName("native-stream");
        nativeThread.start();
    }

    @Override
    public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) {}

    @Override
    public void surfaceDestroyed(SurfaceHolder holder) {
        stopNativeStream();
        if (nativeThread != null) {
            try {
                nativeThread.join(1000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
    }
}