package ai.courtdefense.standalone;

import okhttp3.*;
import java.io.*;
import java.util.concurrent.TimeUnit;

/** OpenAI Whisper API — audio → text. */
public class WhisperClient {

    private static final String ENDPOINT = "https://api.openai.com/v1/audio/transcriptions";

    private final OkHttpClient http;
    private final String apiKey;

    public WhisperClient(String apiKey) {
        this.apiKey = apiKey;
        this.http   = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(600, TimeUnit.SECONDS)   // long audio can take a while
            .writeTimeout(120, TimeUnit.SECONDS)
            .build();
    }

    /**
     * Transcribe audio bytes. mimeType e.g. "audio/mpeg", "audio/m4a", "audio/wav".
     * Returns plain text transcript.
     */
    public String transcribe(byte[] audioBytes, String filename, String mimeType) throws IOException {
        RequestBody body = new MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", filename,
                RequestBody.create(audioBytes, MediaType.get(mimeType)))
            .addFormDataPart("model",           "whisper-1")
            .addFormDataPart("language",        "uk")
            .addFormDataPart("response_format", "text")
            .build();

        Request req = new Request.Builder()
            .url(ENDPOINT)
            .header("Authorization", "Bearer " + apiKey)
            .post(body)
            .build();

        try (Response resp = http.newCall(req).execute()) {
            String text = resp.body().string();
            if (!resp.isSuccessful()) throw new IOException("Whisper API error " + resp.code() + ": " + text);
            return text.trim();
        }
    }

    /** Whisper API limit is 25 MB per request. */
    public static final long MAX_BYTES = 25L * 1024 * 1024;
}
