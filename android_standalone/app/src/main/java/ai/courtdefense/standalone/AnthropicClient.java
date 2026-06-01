package ai.courtdefense.standalone;

import com.google.gson.*;
import okhttp3.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** Direct Anthropic API client — no server needed. */
public class AnthropicClient {

    private static final String BASE   = "https://api.anthropic.com/v1";
    private static final String MODEL  = "claude-sonnet-4-6";
    private static final String VER    = "2023-06-01";
    private static final String BETA   = "files-api-2025-04-14";
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private final OkHttpClient http;
    private final String apiKey;

    public AnthropicClient(String apiKey) {
        this.apiKey = apiKey;
        this.http   = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(300, TimeUnit.SECONDS)
            .writeTimeout(120, TimeUnit.SECONDS)
            .build();
    }

    // ── Files API: upload PDF ─────────────────────────────────────────────

    public String uploadPdf(byte[] pdfBytes, String filename) throws IOException {
        RequestBody body = new MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", filename,
                RequestBody.create(pdfBytes, MediaType.get("application/pdf")))
            .build();

        Request req = new Request.Builder()
            .url(BASE + "/files")
            .header("x-api-key", apiKey)
            .header("anthropic-version", VER)
            .header("anthropic-beta", BETA)
            .post(body)
            .build();

        try (Response resp = http.newCall(req).execute()) {
            String json = resp.body().string();
            if (!resp.isSuccessful()) throw new IOException("Files API error " + resp.code() + ": " + json);
            return new JsonParser().parse(json).getAsJsonObject().get("id").getAsString();
        }
    }

    public void deleteFile(String fileId) {
        try {
            Request req = new Request.Builder()
                .url(BASE + "/files/" + fileId)
                .header("x-api-key", apiKey)
                .header("anthropic-version", VER)
                .header("anthropic-beta", BETA)
                .delete()
                .build();
            http.newCall(req).execute().close();
        } catch (Exception ignored) {}
    }

    // ── Messages API ──────────────────────────────────────────────────────

    /**
     * Analyze content blocks (text + optional PDF file references).
     * contentBlocks: List of Maps with keys "type" and payload fields.
     */
    public String analyze(String systemPrompt, List<Map<String,Object>> contentBlocks)
            throws IOException {

        JsonArray content = new JsonArray();
        for (Map<String,Object> block : contentBlocks) {
            String type = (String) block.get("type");
            JsonObject obj = new JsonObject();

            if ("text".equals(type)) {
                obj.addProperty("type", "text");
                obj.addProperty("text", (String) block.get("text"));

            } else if ("pdf_file".equals(type)) {
                obj.addProperty("type", "document");
                JsonObject src = new JsonObject();
                src.addProperty("type", "file");
                src.addProperty("file_id", (String) block.get("file_id"));
                obj.add("source", src);
            }
            content.add(obj);
        }

        JsonObject userMsg = new JsonObject();
        userMsg.addProperty("role", "user");
        userMsg.add("content", content);

        JsonObject payload = new JsonObject();
        payload.addProperty("model", MODEL);
        payload.addProperty("max_tokens", 16000);
        payload.addProperty("system", systemPrompt);
        JsonArray msgs = new JsonArray();
        msgs.add(userMsg);
        payload.add("messages", msgs);

        Request req = new Request.Builder()
            .url(BASE + "/messages")
            .header("x-api-key", apiKey)
            .header("anthropic-version", VER)
            .header("anthropic-beta", BETA)   // needed if PDFs are included
            .post(RequestBody.create(payload.toString(), JSON))
            .build();

        try (Response resp = http.newCall(req).execute()) {
            String json = resp.body().string();
            if (!resp.isSuccessful()) throw new IOException("Claude API error " + resp.code() + ": " + json);

            JsonObject root = new JsonParser().parse(json).getAsJsonObject();
            return root.getAsJsonArray("content")
                       .get(0).getAsJsonObject()
                       .get("text").getAsString();
        }
    }
}
