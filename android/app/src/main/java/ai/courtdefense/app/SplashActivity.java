package ai.courtdefense.app;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Handler;
import androidx.appcompat.app.AppCompatActivity;

public class SplashActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_splash);

        new Handler().postDelayed(() -> {
            SharedPreferences prefs = getSharedPreferences("cd_prefs", MODE_PRIVATE);
            String url = prefs.getString("server_url", "");

            Intent next = url.isEmpty()
                ? new Intent(this, SetupActivity.class)
                : new Intent(this, MainActivity.class);
            startActivity(next);
            finish();
        }, 1200);
    }
}
