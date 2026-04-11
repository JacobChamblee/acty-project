package com.acty.data

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import org.json.JSONArray
import org.json.JSONObject

/**
 * ActyPrefs — central preferences store for Cactus Insights.
 * Regular settings in plain SharedPreferences; BYOK API key in EncryptedSharedPreferences.
 */
class ActyPrefs(private val context: Context) {

    // ── Plain prefs ───────────────────────────────────────────────────────────

    private val prefs: SharedPreferences by lazy {
        context.getSharedPreferences("acty_settings", Context.MODE_PRIVATE)
    }

    // ── Encrypted prefs (API keys) ────────────────────────────────────────────

    private val encryptedPrefs: SharedPreferences by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            "acty_secure",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    // ── OBD / Bluetooth ───────────────────────────────────────────────────────

    var obdMacAddress: String
        get() = prefs.getString("obd_mac", "") ?: ""
        set(v) = prefs.edit().putString("obd_mac", v).apply()

    var obdDeviceName: String
        get() = prefs.getString("obd_device_name", "No device selected") ?: "No device selected"
        set(v) = prefs.edit().putString("obd_device_name", v).apply()

    // ── Vehicle list ──────────────────────────────────────────────────────────

    fun saveVehicles(vehicles: List<VehicleEntry>) {
        val arr = JSONArray()
        vehicles.forEach { v ->
            arr.put(JSONObject().apply {
                put("id",         v.id)
                put("make",       v.make)
                put("model",      v.model)
                put("year",       v.year)
                put("drivetrain", v.drivetrain)
                put("mac",        v.obdMac)
                put("active",     v.isActive)
            })
        }
        prefs.edit().putString("vehicles", arr.toString()).apply()
    }

    fun loadVehicles(): List<VehicleEntry> {
        val json = prefs.getString("vehicles", null) ?: return emptyList()
        return try {
            val arr = JSONArray(json)
            (0 until arr.length()).map { i ->
                val o = arr.getJSONObject(i)
                VehicleEntry(
                    id         = o.optString("id",         java.util.UUID.randomUUID().toString()),
                    make       = o.optString("make",       ""),
                    model      = o.optString("model",      ""),
                    year       = o.optInt("year",          2020),
                    drivetrain = o.optString("drivetrain", ""),
                    obdMac     = o.optString("mac",        ""),
                    isActive   = o.optBoolean("active",    false),
                )
            }
        } catch (_: Exception) { emptyList() }
    }

    fun setActiveVehicle(id: String) {
        val updated = loadVehicles().map { it.copy(isActive = it.id == id) }
        saveVehicles(updated)
    }

    fun activeVehicle(): VehicleEntry? = loadVehicles().firstOrNull { it.isActive }

    // ── OBD adapter list ──────────────────────────────────────────────────────
    // Richer than the legacy single-adapter obdMacAddress / obdDeviceName fields.
    // Persists all known adapters per device so the user can pick any paired dongle.

    fun saveAdapters(adapters: List<ObdAdapter>) {
        val arr = JSONArray()
        adapters.forEach { a ->
            arr.put(JSONObject().apply {
                put("mac",         a.macAddress)
                put("name",        a.name)
                put("type",        a.adapterType)
                put("default",     a.isDefault)
                put("pids",        JSONArray(a.supportedPids))
            })
        }
        prefs.edit().putString("obd_adapters", arr.toString()).apply()
    }

    fun loadAdapters(): List<ObdAdapter> {
        val json = prefs.getString("obd_adapters", null) ?: return emptyList()
        return try {
            val arr = JSONArray(json)
            (0 until arr.length()).map { i ->
                val o = arr.getJSONObject(i)
                val pidsArr = o.optJSONArray("pids") ?: JSONArray()
                ObdAdapter(
                    macAddress     = o.optString("mac", ""),
                    name           = o.optString("name", ""),
                    adapterType    = o.optString("type", "unknown"),
                    isDefault      = o.optBoolean("default", false),
                    supportedPids  = (0 until pidsArr.length()).map { pidsArr.getString(it) },
                )
            }
        } catch (_: Exception) { emptyList() }
    }

    fun upsertAdapter(adapter: ObdAdapter) {
        val existing = loadAdapters().filter { it.macAddress != adapter.macAddress }
        // If this is set as default, clear default from others
        val updated = if (adapter.isDefault) {
            existing.map { it.copy(isDefault = false) } + adapter
        } else {
            existing + adapter
        }
        saveAdapters(updated)
        // Keep legacy single-mac fields in sync for ObdCaptureService
        if (adapter.isDefault || updated.size == 1) {
            obdMacAddress  = adapter.macAddress
            obdDeviceName  = adapter.name
        }
    }

    fun defaultAdapter(): ObdAdapter? =
        loadAdapters().firstOrNull { it.isDefault } ?: loadAdapters().firstOrNull()

    // ── Sync failure tracking ─────────────────────────────────────────────────
    // Tracks filenames where a sync upload was attempted but failed.
    // Separate from the .sync_manifest (successful syncs) so the UI can show
    // NOT SYNCED (red) vs PENDING (amber) vs SYNCED (green).

    fun markSyncFailed(filename: String) {
        val failed = failedSyncFileNames().toMutableSet()
        failed.add(filename)
        prefs.edit().putStringSet("sync_failed", failed).apply()
    }

    fun clearSyncFailed(filename: String) {
        val failed = failedSyncFileNames().toMutableSet()
        failed.remove(filename)
        prefs.edit().putStringSet("sync_failed", failed).apply()
    }

    fun failedSyncFileNames(): Set<String> =
        prefs.getStringSet("sync_failed", emptySet()) ?: emptySet()

    // ── Sync settings ─────────────────────────────────────────────────────────

    var syncWifiOnly: Boolean
        get() = prefs.getBoolean("sync_wifi_only", true)
        set(v) = prefs.edit().putBoolean("sync_wifi_only", v).apply()

    var syncFrequencyLabel: String
        get() = prefs.getString("sync_frequency", "Per Drive") ?: "Per Drive"
        set(v) = prefs.edit().putString("sync_frequency", v).apply()

    // ── Supabase JWT (encrypted) ──────────────────────────────────────────────
    // Stored after OAuth callback or Supabase email/password sign-in.
    // Used by SyncManager to attach Authorization headers to API calls.

    var supabaseAccessToken: String
        get()  = try { encryptedPrefs.getString("sb_access_token", "") ?: "" } catch (_: Exception) { "" }
        set(v) = try { encryptedPrefs.edit().putString("sb_access_token", v).apply() } catch (_: Exception) {}

    var supabaseRefreshToken: String
        get()  = try { encryptedPrefs.getString("sb_refresh_token", "") ?: "" } catch (_: Exception) { "" }
        set(v) = try { encryptedPrefs.edit().putString("sb_refresh_token", v).apply() } catch (_: Exception) {}

    fun clearSupabaseTokens() {
        try { encryptedPrefs.edit().remove("sb_access_token").remove("sb_refresh_token").apply() } catch (_: Exception) {}
    }

    // ── BYOK (encrypted) ──────────────────────────────────────────────────────

    var byokApiKey: String
        get() = try { encryptedPrefs.getString("byok_api_key", "") ?: "" } catch (_: Exception) { "" }
        set(v) = try { encryptedPrefs.edit().putString("byok_api_key", v).apply() } catch (_: Exception) {}

    var byokProvider: String
        get() = prefs.getString("byok_provider", "") ?: ""
        set(v) = prefs.edit().putString("byok_provider", v).apply()
}

data class VehicleEntry(
    val id:         String = java.util.UUID.randomUUID().toString(),
    val make:       String,
    val model:      String,
    val year:       Int,
    val drivetrain: String = "",
    val obdMac:     String = "",
    val isActive:   Boolean = false,
)

data class ObdAdapter(
    val macAddress:    String,
    val name:          String,
    val adapterType:   String        = "unknown",
    val isDefault:     Boolean       = false,
    val supportedPids: List<String>  = emptyList(),
)
