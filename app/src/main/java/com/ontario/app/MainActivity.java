package com.ontario.app;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
import android.view.Gravity;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // Створюємо UI програмно, щоб мінімізувати ресурси, або через XML
        setContentView(R.layout.activity_main);
    }
}
