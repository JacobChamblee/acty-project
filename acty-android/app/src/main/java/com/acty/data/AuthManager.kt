package com.acty.data

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject
import java.security.MessageDigest
import java.util.UUID

// ── User account model ────────────────────────────────────────────────────────

data class UserAccount(
    val username:             String,
    val displayName:          String,
    val email:                String,
    val pwHash:               String  = "",   // SHA-256 hex; empty triggers migration
    val region:               String  = "",
    val vehicles:             List<VehicleEntry> = emptyList(),
    val byokApiKey:           String  = "",
    val byokProvider:         String  = "",
    val syncWifiOnly:         Boolean = true,
    val alertDtcEnabled:      Boolean = true,
    val alertLtftEnabled:     Boolean = true,
    val alertServiceEnabled:  Boolean = true,
    val alertChargingEnabled: Boolean = true,
    val ltftAlertThreshold:   Float   = 7.5f,
)

sealed class AuthResult {
    object Success : AuthResult()
    data class Error(val message: String) : AuthResult()
}

// ── AuthManager ───────────────────────────────────────────────────────────────

class AuthManager(private val context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences("acty_auth", Context.MODE_PRIVATE)

    // ── Password hashing ──────────────────────────────────────────────────────

    companion object {
        fun hashPassword(password: String): String {
            val bytes = MessageDigest.getInstance("SHA-256")
                .digest(password.toByteArray(Charsets.UTF_8))
            return bytes.joinToString("") { "%02x".format(it) }
        }
    }

    // ── JSON serialisation ────────────────────────────────────────────────────

    private fun loadAccountsJson(): JSONObject = try {
        JSONObject(prefs.getString("auth_accounts", "{}") ?: "{}")
    } catch (_: Exception) { JSONObject() }

    private fun saveAccountsJson(obj: JSONObject) {
        prefs.edit().putString("auth_accounts", obj.toString()).apply()
    }

    private fun vehicleFromJson(o: JSONObject) = VehicleEntry(
        id         = o.optString("id",         UUID.randomUUID().toString()),
        make       = o.optString("make",       ""),
        model      = o.optString("model",      ""),
        year       = o.optInt("year",          2020),
        drivetrain = o.optString("drivetrain", ""),
        obdMac     = o.optString("mac",        ""),
        isActive   = o.optBoolean("active",    false),
    )

    private fun vehicleToJson(v: VehicleEntry) = JSONObject().apply {
        put("id",         v.id)
        put("make",       v.make)
        put("model",      v.model)
        put("year",       v.year)
        put("drivetrain", v.drivetrain)
        put("mac",        v.obdMac)
        put("active",     v.isActive)
    }

    private fun accountFromJson(o: JSONObject): UserAccount {
        val arr = try { o.getJSONArray("vehicles") } catch (_: Exception) { JSONArray() }
        val vehicles = (0 until arr.length()).map { vehicleFromJson(arr.getJSONObject(it)) }
        return UserAccount(
            username             = o.optString("username",             ""),
            displayName          = o.optString("displayName",          o.optString("username", "")),
            email                = o.optString("email",                ""),
            pwHash               = o.optString("pwHash",               ""),
            region               = o.optString("region",               ""),
            vehicles             = vehicles,
            byokApiKey           = o.optString("byokApiKey",           ""),
            byokProvider         = o.optString("byokProvider",         ""),
            syncWifiOnly         = o.optBoolean("syncWifiOnly",         true),
            alertDtcEnabled      = o.optBoolean("alertDtcEnabled",      true),
            alertLtftEnabled     = o.optBoolean("alertLtftEnabled",     true),
            alertServiceEnabled  = o.optBoolean("alertServiceEnabled",  true),
            alertChargingEnabled = o.optBoolean("alertChargingEnabled", true),
            ltftAlertThreshold   = o.optDouble("ltftAlertThreshold",    7.5).toFloat(),
        )
    }

    private fun accountToJson(a: UserAccount): JSONObject {
        val arr = JSONArray().also { arr -> a.vehicles.forEach { arr.put(vehicleToJson(it)) } }
        return JSONObject().apply {
            put("username",             a.username)
            put("displayName",          a.displayName)
            put("email",                a.email)
            put("pwHash",               a.pwHash)
            put("region",               a.region)
            put("vehicles",             arr)
            put("byokApiKey",           a.byokApiKey)
            put("byokProvider",         a.byokProvider)
            put("syncWifiOnly",         a.syncWifiOnly)
            put("alertDtcEnabled",      a.alertDtcEnabled)
            put("alertLtftEnabled",     a.alertLtftEnabled)
            put("alertServiceEnabled",  a.alertServiceEnabled)
            put("alertChargingEnabled", a.alertChargingEnabled)
            put("ltftAlertThreshold",   a.ltftAlertThreshold.toDouble())
        }
    }

    private fun getAccount(email: String): UserAccount? {
        val obj = loadAccountsJson().optJSONObject(email.lowercase()) ?: return null
        return accountFromJson(obj)
    }

    private fun saveAccount(account: UserAccount) {
        val accounts = loadAccountsJson()
        accounts.put(account.email.lowercase(), accountToJson(account))
        saveAccountsJson(accounts)
    }

    // ── Session ───────────────────────────────────────────────────────────────

    private var _sessionEmail: String
        get() = prefs.getString("auth_session", "") ?: ""
        set(v) { prefs.edit().putString("auth_session", v).apply() }

    fun isLoggedIn(): Boolean = _sessionEmail.isNotEmpty() && getAccount(_sessionEmail) != null

    fun currentUser(): UserAccount? {
        val email = _sessionEmail.ifEmpty { return null }
        return getAccount(email)
    }

    // ── Auth operations ───────────────────────────────────────────────────────

    fun login(email: String, password: String): AuthResult {
        val account = getAccount(email)
            ?: return AuthResult.Error("No account found for that email.")
        val hash = hashPassword(password)
        return if (account.pwHash.isEmpty()) {
            // Migration: first login sets the hash
            saveAccount(account.copy(pwHash = hash))
            _sessionEmail = account.email.lowercase()
            AuthResult.Success
        } else if (hash == account.pwHash) {
            _sessionEmail = account.email.lowercase()
            AuthResult.Success
        } else {
            AuthResult.Error("Incorrect password.")
        }
    }

    fun register(
        username: String,
        email:    String,
        password: String,
        region:   String           = "",
        vehicles: List<VehicleEntry> = emptyList(),
    ): AuthResult {
        val key = email.trim().lowercase()
        if (getAccount(key) != null)
            return AuthResult.Error("An account with this email already exists.")
        val account = UserAccount(
            username    = username.trim(),
            displayName = username.trim(),
            email       = key,
            pwHash      = hashPassword(password),
            region      = region,
            vehicles    = vehicles,
        )
        saveAccount(account)
        _sessionEmail = key
        return AuthResult.Success
    }

    fun logout() {
        prefs.edit().remove("auth_session").apply()
    }

    fun deleteAccount() {
        val email = _sessionEmail.ifEmpty { return }
        val accounts = loadAccountsJson()
        accounts.remove(email.lowercase())
        saveAccountsJson(accounts)
        prefs.edit().remove("auth_session").apply()
    }

    // ── User mutations (all write back to storage immediately) ────────────────

    fun updateUser(updated: UserAccount) {
        saveAccount(updated)
        // Keep session pointing to updated email
        _sessionEmail = updated.email.lowercase()
    }

    fun addVehicle(vehicle: VehicleEntry) {
        val account = currentUser() ?: return
        val existing = account.vehicles
        val withId   = vehicle.copy(
            id       = vehicle.id.ifEmpty { UUID.randomUUID().toString() },
            isActive = existing.isEmpty(),   // first vehicle becomes active
        )
        saveAccount(account.copy(vehicles = existing + withId))
    }

    fun removeVehicle(id: String) {
        val account = currentUser() ?: return
        val wasActive = account.vehicles.firstOrNull { it.id == id }?.isActive ?: false
        val remaining = account.vehicles.filter { it.id != id }
        val adjusted = if (wasActive && remaining.isNotEmpty())
            remaining.mapIndexed { i, v -> if (i == 0) v.copy(isActive = true) else v }
        else remaining
        saveAccount(account.copy(vehicles = adjusted))
    }

    fun setActiveVehicle(id: String) {
        val account = currentUser() ?: return
        saveAccount(account.copy(
            vehicles = account.vehicles.map { it.copy(isActive = it.id == id) }
        ))
    }

    fun updateVehicleObd(vehicleId: String, mac: String) {
        val account = currentUser() ?: return
        saveAccount(account.copy(
            vehicles = account.vehicles.map { v ->
                if (v.id == vehicleId) v.copy(obdMac = mac) else v
            }
        ))
    }
}
