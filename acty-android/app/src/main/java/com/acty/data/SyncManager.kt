package com.acty.data

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Base64
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * SyncManager — uploads completed CSV sessions to the Acty API.
 * Respects WiFi-only preference and supports sync over mobile data.
 * Uses the same app-scoped storage path as CsvWriter.
 */
class SyncManager(private val context: Context) {

    companion object {
        private const val TAG      = "SyncManager"
        private const val MANIFEST = ".sync_manifest"
        private val UPLOAD_URL     = "${com.acty.ActyConfig.API_BASE}/api/v1/sessions/sync"
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    // Same path as CsvWriter — app-scoped, no storage permissions needed
    val dataDir: File = File(context.getExternalFilesDir(null), "data_capture")
        .also { it.mkdirs() }

    private val manifestFile: File get() = File(dataDir, MANIFEST)

    // ── Network checks ────────────────────────────────────────────────────────

    fun isOnWifi(): Boolean = hasTransport(NetworkCapabilities.TRANSPORT_WIFI)

    fun isNetworkAvailable(): Boolean =
        isOnWifi() || hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)

    private fun hasTransport(transport: Int): Boolean {
        val cm      = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return false
        val caps    = cm.getNetworkCapabilities(network) ?: return false
        return caps.hasTransport(transport)
    }

    // ── Manifest helpers ──────────────────────────────────────────────────────

    private fun loadManifest(): MutableSet<String> {
        if (!manifestFile.exists()) return mutableSetOf()
        return manifestFile.readLines()
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .toMutableSet()
    }

    private fun saveManifest(synced: Set<String>) {
        manifestFile.writeText(synced.sorted().joinToString("\n"))
    }

    // ── Sync ──────────────────────────────────────────────────────────────────

    /**
     * Upload all pending CSVs.
     * @param wifiOnly  When true, aborts if not on WiFi.
     * @param vehicleId Vehicle identifier to tag uploads with.
     * @param onProgress Callback per file: (fileName, success).
     */
    suspend fun syncPendingFiles(
        wifiOnly:   Boolean = true,
        vehicleId:  String = "unknown",
        onProgress: (String, Boolean) -> Unit = { _, _ -> },
    ): List<Pair<String, Boolean>> = withContext(Dispatchers.IO) {
        // Network gate
        if (wifiOnly && !isOnWifi()) {
            Log.d(TAG, "WiFi-only mode and not on WiFi — skipping")
            return@withContext emptyList()
        }
        if (!isNetworkAvailable()) {
            Log.d(TAG, "No network available — skipping")
            return@withContext emptyList()
        }

        val synced   = loadManifest()
        val csvFiles = dataDir.listFiles { f ->
            f.name.startsWith("acty_obd_") && f.name.endsWith(".csv") && f.name !in synced
        }?.sortedBy { it.name } ?: emptyList()

        if (csvFiles.isEmpty()) {
            Log.d(TAG, "No pending files")
            return@withContext emptyList()
        }

        Log.d(TAG, "Syncing ${csvFiles.size} file(s) [wifiOnly=$wifiOnly]")
        val results = mutableListOf<Pair<String, Boolean>>()

        for (file in csvFiles) {
            val ok = uploadFile(file, vehicleId)
            if (ok) synced.add(file.name)
            results.add(file.name to ok)
            onProgress(file.name, ok)
            Log.d(TAG, "  ${file.name}: ${if (ok) "✓" else "✗"}")
        }

        saveManifest(synced)
        results
    }

    private fun uploadFile(file: File, vehicleId: String): Boolean {
        val sigFile = File(file.parentFile, file.nameWithoutExtension + ".sig")
        if (!sigFile.exists()) {
            Log.w(TAG, "Missing .sig for ${file.name} — skipping")
            return false
        }

        val sessionId = file.nameWithoutExtension
        val csvB64    = Base64.encodeToString(file.readBytes(), Base64.NO_WRAP)
        val sigB64    = Base64.encodeToString(sigFile.readBytes(), Base64.NO_WRAP)

        val payload = JSONObject().apply {
            put("session_id", sessionId)
            put("vehicle_id", vehicleId)
            put("csv_b64",    csvB64)
            put("sig_b64",    sigB64)
        }.toString()

        return try {
            val body    = payload.toRequestBody("application/json".toMediaTypeOrNull())
            val request = Request.Builder().url(UPLOAD_URL).post(body).build()
            client.newCall(request).execute().use { it.isSuccessful }
        } catch (e: Exception) {
            Log.e(TAG, "Upload failed for ${file.name}: ${e.message}")
            false
        }
    }

    // ── Manifest read for UI ──────────────────────────────────────────────────

    fun syncedFileNames(): Set<String> = loadManifest()
}
