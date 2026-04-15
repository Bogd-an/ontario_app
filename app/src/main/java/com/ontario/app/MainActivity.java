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

import java.io.BufferedInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.ByteBuffer;

public class MainActivity extends Activity implements SurfaceHolder.Callback {
    private SurfaceView surfaceView;
    private SurfaceHolder holder;
    private Thread serverThread;
    private volatile boolean isRunning = false;
    
    // СТАТИЧНІ ПАРАМЕТРИ (Скінченна пам'ять)
    private final int FRAME_WIDTH = 1024;
    private final int FRAME_HEIGHT = 768;
    private final int FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * 2; 

    private String currentStatus = "Очікування...";
    private int currentFps = 0;
    private int frameCount = 0;
    private long lastTime = 0;
    
    // PRE-ALLOCATED OBJECTS (Запобігають роботі Garbage Collector)
    private final Paint textPaint = new Paint();
    private final Rect screenRect = new Rect();
    private final StringBuilder infoBuilder = new StringBuilder(100);
    private byte[] masterPixels;
    private byte[] netBuffer;
    private ByteBuffer masterBuffer;
    private Bitmap bitmap;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        
        // Ініціалізація скінченних ресурсів один раз при запуску
        masterPixels = new byte[FRAME_SIZE];
        netBuffer = new byte[FRAME_SIZE];
        masterBuffer = ByteBuffer.wrap(masterPixels);
        bitmap = Bitmap.createBitmap(FRAME_WIDTH, FRAME_HEIGHT, Bitmap.Config.RGB_565);
        
        surfaceView = new SurfaceView(this);
        setContentView(surfaceView);
        holder = surfaceView.getHolder();
        holder.addCallback(this);

        textPaint.setColor(Color.GREEN);
        textPaint.setTextSize(35);
        textPaint.setFakeBoldText(true);
        textPaint.setShadowLayer(3f, 2f, 2f, Color.BLACK);
    }

    private void drawDebugOverlay(Canvas canvas, int w, int h) {
        if (canvas == null) return;
        
        // 1. Малюємо бітмап на весь екран
        screenRect.set(0, 0, canvas.getWidth(), canvas.getHeight());
        canvas.drawBitmap(bitmap, null, screenRect, null);
        
        // 2. Вивід тексту без створення нових String об'єктів (майже)
        canvas.drawText(currentStatus, 30, 50, textPaint);
        
        infoBuilder.setLength(0);
        infoBuilder.append("FPS: ").append(currentFps).append(" | Part: ").append(w).append("x").append(h);
        canvas.drawText(infoBuilder.toString(), 30, 90, textPaint);
    }

    @Override
    public void surfaceCreated(SurfaceHolder surfaceHolder) {
        if (serverThread != null && serverThread.isAlive()) return;
        
        isRunning = true;
        serverThread = new Thread(new Runnable() {
            @Override
            public void run() {
                ServerSocket serverSocket = null;
                try {
                    serverSocket = new ServerSocket(8080);
                    
                    while (isRunning) {
                        Socket client = null;
                        try {
                            client = serverSocket.accept();
                            // Захист від "завислих" з'єднань
                            client.setSoTimeout(3000); 
                            client.setReceiveBufferSize(1024 * 1024);
                            
                            DataInputStream dis = new DataInputStream(new BufferedInputStream(client.getInputStream(), 256 * 1024));
                            currentStatus = "Потік активний";
                            
                            lastTime = System.currentTimeMillis();
                            frameCount = 0;

                            while (isRunning && !client.isClosed()) {
                                // Читаємо координати (4 х 2 байти)
                                int x = dis.readUnsignedShort();
                                int y = dis.readUnsignedShort();
                                int w = dis.readUnsignedShort();
                                int h = dis.readUnsignedShort();
                                
                                // ВАЛІДАЦІЯ: головний захист від Kernel Panic
                                if (x + w > FRAME_WIDTH || y + h > FRAME_HEIGHT) {
                                    throw new IOException("Protocol sync error: Out of bounds");
                                }

                                if (w > 0 && h > 0) {
                                    int bytesToRead = w * h * 2;
                                    dis.readFully(netBuffer, 0, bytesToRead);
                                    
                                    // Копіювання в master-масив
                                    for (int row = 0; row < h; row++) {
                                        int destOffset = ((y + row) * FRAME_WIDTH + x) * 2;
                                        int srcOffset = row * w * 2;
                                        System.arraycopy(netBuffer, srcOffset, masterPixels, destOffset, w * 2);
                                    }
                                    
                                    // Оновлюємо Bitmap
                                    masterBuffer.rewind();
                                    bitmap.copyPixelsFromBuffer(masterBuffer);
                                }
                                
                                // Розрахунок FPS
                                frameCount++;
                                long now = System.currentTimeMillis();
                                if (now - lastTime >= 1000) {
                                    currentFps = frameCount;
                                    frameCount = 0;
                                    lastTime = now;
                                }

                                // Малювання
                                Canvas canvas = null;
                                try {
                                    canvas = holder.lockCanvas();
                                    if (canvas != null) {
                                        drawDebugOverlay(canvas, w, h);
                                    }
                                } finally {
                                    if (canvas != null) holder.unlockCanvasAndPost(canvas);
                                }
                            }
                        } catch (Exception e) {
                            currentStatus = "З'єднання закрито";
                        } finally {
                            if (client != null) try { client.close(); } catch (IOException ignored) {}
                        }
                    }
                } catch (IOException e) {
                    currentStatus = "Помилка сервера";
                } finally {
                    if (serverSocket != null) try { serverSocket.close(); } catch (IOException ignored) {}
                }
            }
        });
        serverThread.start();
    }

    @Override
    public void surfaceChanged(SurfaceHolder h, int format, int width, int height) {}

    @Override
    public void surfaceDestroyed(SurfaceHolder surfaceHolder) {
        isRunning = false;
        if (serverThread != null) {
            serverThread.interrupt();
        }
    }
}