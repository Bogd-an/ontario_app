package com.ontario.app;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.os.Bundle;
import android.util.Log;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;

import java.io.BufferedInputStream;
import java.io.DataInputStream;
import java.io.EOFException;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.ByteBuffer;

public class MainActivity extends Activity implements SurfaceHolder.Callback {
    private static final String TAG = "OntarioStream";
    private SurfaceView surfaceView;
    private SurfaceHolder holder;
    private Thread serverThread;
    private volatile boolean isRunning = false;
    
    private final int FRAME_WIDTH = 960;
    private final int FRAME_HEIGHT = 720;
    private final int FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * 2; 

    private String currentStatus = "Очікування...";
    private int currentFps = 0;
    private long lastTime = 0;
    private int lastBandwidth = 0;

    private byte[] masterPixels = new byte[FRAME_SIZE];
    private ByteBuffer masterBuffer = ByteBuffer.wrap(masterPixels);
    private Bitmap bitmap = Bitmap.createBitmap(FRAME_WIDTH, FRAME_HEIGHT, Bitmap.Config.RGB_565);
    private byte[] netBuffer = new byte[FRAME_SIZE];

    private Paint debugPaint;
    private boolean debugMode = false; // Вмикає/вимикає оверлей з інформацією
    private Rect destRect;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        hideSystemUI();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        surfaceView = new SurfaceView(this);
        setContentView(surfaceView);
        holder = surfaceView.getHolder();
        holder.addCallback(this);

        if (debugMode) {
            debugPaint = new Paint();
            debugPaint.setColor(Color.GREEN);
            debugPaint.setTextSize(40);
            debugPaint.setShadowLayer(5f, 2f, 2f, Color.BLACK);
        }
        destRect = new Rect();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) hideSystemUI();
    }

    private void hideSystemUI() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
            final WindowInsetsController controller = getWindow().getInsetsController();
            if (controller != null) {
                controller.hide(WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars());
            }
        } else {
            getWindow().getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_FULLSCREEN);
        }
    }

    private void drawDebugOverlay(Canvas canvas, Bitmap bitmap, int w, int h) {
        if (canvas == null) return;
        try {
            if (bitmap != null) {
                destRect.set(0, 0, canvas.getWidth(), canvas.getHeight());
                canvas.drawBitmap(bitmap, null, destRect, null);
            } else {
                canvas.drawColor(Color.BLACK);
            }
            if(debugMode){
                canvas.drawText(currentStatus + " | FPS: " + currentFps, 30, 60, debugPaint);
                canvas.drawText(String.format("Rect: %dx%d | %d KB", w, h, lastBandwidth), 30, 110, debugPaint);
            }
        } catch (Exception e) {
            Log.e(TAG, "Draw error: " + e.getMessage());
        }
    }

@Override
public void surfaceCreated(SurfaceHolder surfaceHolder) {
    isRunning = true;
    serverThread = new Thread(() -> {
        // reuseAddress дозволяє швидше перезапускати сервер після збою
        try (ServerSocket serverSocket = new ServerSocket(8080)) {
            serverSocket.setReuseAddress(true);
            
            while (isRunning) {
                try (Socket client = serverSocket.accept()) {
                    client.setTcpNoDelay(true);
                    client.setReceiveBufferSize(1024 * 1024);
                    client.setSoTimeout(5000); // Тайм-аут 5 секунд, щоб не висіти вічно

                    DataInputStream dis = new DataInputStream(new BufferedInputStream(client.getInputStream(), 1024 * 1024));
                    currentStatus = "Стрім іде";
                    lastTime = System.currentTimeMillis();
                    int fCount = 0;
                    
                    while (isRunning && !client.isClosed()) {
                        try {
                            // Читаємо заголовок
                            int x = dis.readUnsignedShort();
                            int y = dis.readUnsignedShort();
                            int w = dis.readUnsignedShort();
                            int h = dis.readUnsignedShort();
                            
                            if (w > 0 && h > 0) {
                                // КРИТИЧНО: Перевірка меж масиву перед копіюванням
                                if (x + w <= FRAME_WIDTH && y + h <= FRAME_HEIGHT) {
                                    int bytesToRead = w * h * 2;
                                    dis.readFully(netBuffer, 0, bytesToRead);
                                    
                                    for (int row = 0; row < h; row++) {
                                        System.arraycopy(netBuffer, row * w * 2, masterPixels, ((y + row) * FRAME_WIDTH + x) * 2, w * 2);
                                    }
                                    
                                    masterBuffer.rewind();
                                    bitmap.copyPixelsFromBuffer(masterBuffer);

                                    // Безпечне малювання
                                    Canvas canvas = holder.lockCanvas();
                                    if (canvas != null) {
                                        try { 
                                            drawDebugOverlay(canvas, bitmap, w, h); 
                                        } finally { 
                                            holder.unlockCanvasAndPost(canvas); 
                                        }
                                    }
                                } else {
                                    // Якщо розміри некоректні — пропускаємо байти, щоб не розсинхронізувати потік
                                    dis.skipBytes(w * h * 2);
                                    Log.e(TAG, "Некоректні розміри кадру: " + w + "x" + h);
                                }
                            }
                            
                            fCount++;
                            if (System.currentTimeMillis() - lastTime >= 1000) {
                                currentFps = fCount;
                                fCount = 0;
                                lastTime = System.currentTimeMillis();
                            }
                            
                        } catch (EOFException e) {
                            Log.d(TAG, "Клієнт відключився");
                            break; 
                        } catch (Exception e) {
                            Log.e(TAG, "Помилка кадру: " + e.getMessage());
                            // Маленька пауза при помилці, щоб не зациклити процесор
                            Thread.sleep(10); 
                        }
                    }
                } catch (Exception e) {
                    Log.e(TAG, "Помилка з'єднання: " + e.getMessage());
                    currentStatus = "Очікування...";
                }
            }
        } catch (Exception e) { 
            Log.e(TAG, "Критична помилка сервера: " + e.getMessage()); 
        }
    });
    serverThread.start();
}

    @Override
    public void surfaceChanged(SurfaceHolder h, int f, int w, int h2) {}
    @Override
    public void surfaceDestroyed(SurfaceHolder h) {
        isRunning = false;
        if (serverThread != null) serverThread.interrupt();
    }
}
