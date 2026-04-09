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

    // ── Sync settings ─────────────────────────────────────────────────────────

    var syncWifiOnly: Boolean
        get() = prefs.getBoolean("sync_wifi_only", true)
        set(v) = prefs.edit().putBoolean("sync_wifi_only", v).apply()

    var syncFrequencyLabel: String
        get() = prefs.getString("sync_frequency", "Per Drive") ?: "Per Drive"
        set(v) = prefs.edit().putString("sync_frequency", v).apply()

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
