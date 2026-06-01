package ai.courtdefense.app;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.text.TextUtils;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;

public class SetupActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_setup);

        SharedPreferences prefs = getSharedPreferences("cd_prefs", MODE_PRIVATE);
        EditText urlInput = findViewById(R.id.url_input);
        Button btnConnect = findViewById(R.id.btn_connect);

        // Pre-fill if already saved
        String saved = prefs.getString("server_url", "");
        if (!saved.isEmpty()) urlInput.setText(saved);

        btnConnect.setOnClickListener(v -> {
            String url = urlInput.getText().toString().trim();

            // Auto-add http:// if missing
            if (!url.startsWith("http://") && !url.startsWith("https://")) {
                url = "http://" + url;
            }
            // Auto-add port 8000 if no port specified and http
            if (url.startsWith("http://") && !url.contains(":", 7)) {
                url = url + ":8000";
            }

            if (TextUtils.isEmpty(url)) {
                Toast.makeText(this, "Enter server address", Toast.LENGTH_SHORT).show();
                return;
            }

            prefs.edit().putString("server_url", url).apply();
            startActivity(new Intent(this, MainActivity.class));
            finish();
        });
    }
}
