package com.ontario.app;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.os.Bundle;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.WindowManager;

import java.io.DataInputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.ByteBuffer;

public class MainActivity extends Activity implements SurfaceHolder.Callback {
    private SurfaceView surfaceView;
    private SurfaceHolder holder;
    private Thread serverThread;
    private boolean isRunning = false;
    
    // Фіксована роздільна здатність стріму
    private final int FRAME_WIDTH = 640;
    private final int FRAME_HEIGHT = 480;
    
    // Формат RGB_565 займає 2 байти на піксель
    private final int FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * 2; 

    private String currentStatus = "Очікування сирого потоку (Raw Pixels)...";
    private int currentFps = 0;
    private int frameCount = 0;
    private long lastTime = 0;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        surfaceView = new SurfaceView(this);
        setContentView(surfaceView);
        holder = surfaceView.getHolder();
        holder.addCallback(this);
    }

    private void drawDebugOverlay(Canvas canvas, Bitmap bitmap) {
        if (canvas == null) return;
        if (bitmap != null) {
            Rect destRect = new Rect(0, 0, canvas.getWidth(), canvas.getHeight());
            canvas.drawBitmap(bitmap, null, destRect, null);
        } else {
            canvas.drawColor(Color.BLACK);
        }
        Paint textPaint = new Paint();
        textPaint.setColor(Color.GREEN);
        textPaint.setTextSize(40);
        textPaint.setFakeBoldText(true);
        textPaint.setShadowLayer(5f, 2f, 2f, Color.BLACK);
        canvas.drawText(currentStatus, 30, 60, textPaint);
        if (bitmap != null) {
            canvas.drawText(String.format("FPS: %d | Raw Mode: %d KB/frame", currentFps, FRAME_SIZE / 1024), 30, 110, textPaint);
        }
    }

    @Override
    public void surfaceCreated(SurfaceHolder surfaceHolder) {
        isRunning = true;
        serverThread = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    ServerSocket serverSocket = new ServerSocket(8080);
                    
                    // --- МАГІЯ: Виділяємо пам'ять ОДИН РАЗ на весь час ---
                    byte[] frameData = new byte[FRAME_SIZE];
                    ByteBuffer buffer = ByteBuffer.wrap(frameData);
                    Bitmap bitmap = Bitmap.createBitmap(FRAME_WIDTH, FRAME_HEIGHT, Bitmap.Config.RGB_565);

                    while (isRunning) {
                        Socket client = serverSocket.accept();
                        currentStatus = "Стрім іде (Direct Memory Copy)";
                        DataInputStream dis = new DataInputStream(client.getInputStream());
                        
                        lastTime = System.currentTimeMillis();
                        frameCount = 0;

                        while (isRunning && !client.isClosed()) {
                            try {
                                // Читаємо РІВНО один кадр у буфер (без парсингу розмірів)
                                dis.readFully(frameData);
                                
                                // Скидаємо позицію буфера в нуль
                                buffer.rewind();
                                
                                // МИТТЄВО копіюємо байти у відеопам'ять (без декодування)
                                bitmap.copyPixelsFromBuffer(buffer);
                                
                                frameCount++;
                                long now = System.currentTimeMillis();
                                if (now - lastTime >= 1000) {
                                    currentFps = frameCount;
                                    frameCount = 0;
                                    lastTime = now;
                                }

                                Canvas canvas = null;
                                try {
                                    canvas = holder.lockCanvas();
                                    drawDebugOverlay(canvas, bitmap);
                                } finally {
                                    if (canvas != null) holder.unlockCanvasAndPost(canvas);
                                }
                            } catch (Exception e) { 
                                break; 
                            }
                        }
                        client.close();
                        currentStatus = "Обрив. Очікування...";
                    }
                    serverSocket.close();
                } catch (Exception e) {}
            }
        });
        serverThread.start();
    }

    @Override
    public void surfaceChanged(SurfaceHolder surfaceHolder, int format, int width, int height) {}

    @Override
    public void surfaceDestroyed(SurfaceHolder surfaceHolder) {
        isRunning = false;
        try { if (serverThread != null) serverThread.interrupt(); } catch (Exception e) {}
    }
}
