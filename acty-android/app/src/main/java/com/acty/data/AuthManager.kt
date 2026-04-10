package com.acty.data

import android.content.Context
import android.content.SharedPreferences
import android.net.Uri
import androidx.browser.customtabs.CustomTabsIntent
import com.acty.ActyConfig
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
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
    val provider:             String  = "",   // "" = email/password, "google" = OAuth
    val avatarUrl:            String  = "",
)

sealed class AuthResult {
    object Success : AuthResult()
    data class Error(val message: String) : AuthResult()
}

// ── AuthManager ───────────────────────────────────────────────────────────────

class AuthManager(private val context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences("acty_auth", Context.MODE_PRIVATE)
    private val httpClient = OkHttpClient()
    private val backgroundScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val jsonMediaType = "application/json".toMediaType()

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
        val activeVehicleId = o.optString("activeVehicleId", "")
        val arr = try { o.getJSONArray("vehicles") } catch (_: Exception) { JSONArray() }
        val vehicles = (0 until arr.length()).map { idx ->
            val vehicleJson = arr.getJSONObject(idx)
            val vehicleId = vehicleJson.optString("id", UUID.randomUUID().toString())
            VehicleEntry(
                id         = vehicleId,
                make       = vehicleJson.optString("make", ""),
                model      = vehicleJson.optString("model", ""),
                year       = vehicleJson.opt("year")?.toString()?.toIntOrNull() ?: 2020,
                drivetrain = vehicleJson.optString("drivetrain", ""),
                obdMac     = vehicleJson.optString("mac", vehicleJson.optString("obdMac", "")),
                isActive   = vehicleJson.optBoolean("active", vehicleId == activeVehicleId),
            )
        }
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
            provider             = o.optString("provider",             ""),
            avatarUrl            = o.optString("avatarUrl",            ""),
        )
    }

    private fun accountToJson(a: UserAccount): JSONObject {
        val activeVehicleId = a.vehicles.firstOrNull { it.isActive }?.id.orEmpty()
        val arr = JSONArray().also { arr -> a.vehicles.forEach { arr.put(vehicleToJson(it)) } }
        return JSONObject().apply {
            put("username",             a.username)
            put("displayName",          a.displayName)
            put("email",                a.email)
            put("pwHash",               a.pwHash)
            put("region",               a.region)
            put("vehicles",             arr)
            put("activeVehicleId",      activeVehicleId)
            put("byokApiKey",           a.byokApiKey)
            put("byokProvider",         a.byokProvider)
            put("syncWifiOnly",         a.syncWifiOnly)
            put("alertDtcEnabled",      a.alertDtcEnabled)
            put("alertLtftEnabled",     a.alertLtftEnabled)
            put("alertServiceEnabled",  a.alertServiceEnabled)
            put("alertChargingEnabled", a.alertChargingEnabled)
            put("ltftAlertThreshold",   a.ltftAlertThreshold.toDouble())
            put("provider",             a.provider)
            put("avatarUrl",            a.avatarUrl)
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

    private data class RemoteAuthResponse(
        val account: UserAccount? = null,
        val error: String? = null,
    )

    private fun remoteAccountFromJson(o: JSONObject, fallbackPasswordHash: String = ""): UserAccount {
        val activeVehicleId = o.optString("activeVehicleId", "")
        val arr = try { o.getJSONArray("vehicles") } catch (_: Exception) { JSONArray() }
        val vehicles = (0 until arr.length()).map { idx ->
            val vehicleJson = arr.getJSONObject(idx)
            val vehicleId = vehicleJson.optString("id", UUID.randomUUID().toString())
            VehicleEntry(
                id         = vehicleId,
                make       = vehicleJson.optString("make", ""),
                model      = vehicleJson.optString("model", ""),
                year       = vehicleJson.opt("year")?.toString()?.toIntOrNull() ?: 2020,
                drivetrain = vehicleJson.optString("drivetrain", ""),
                obdMac     = vehicleJson.optString("mac", vehicleJson.optString("obdMac", "")),
                isActive   = vehicleJson.optBoolean("active", vehicleId == activeVehicleId),
            )
        }

        return UserAccount(
            username             = o.optString("username", o.optString("displayName", "")),
            displayName          = o.optString("displayName", o.optString("username", "")),
            email                = o.optString("email", "").lowercase(),
            pwHash               = fallbackPasswordHash.ifEmpty {
                o.optString("pwHash", o.optString("_pwHash", ""))
            },
            region               = o.optString("region", ""),
            vehicles             = vehicles,
            byokApiKey           = o.optString("byokApiKey", ""),
            byokProvider         = o.optString("byokProvider", ""),
            syncWifiOnly         = o.optBoolean("syncWifiOnly", true),
            alertDtcEnabled      = o.optBoolean("alertDtcEnabled", true),
            alertLtftEnabled     = o.optBoolean("alertLtftEnabled", true),
            alertServiceEnabled  = o.optBoolean("alertServiceEnabled", true),
            alertChargingEnabled = o.optBoolean("alertChargingEnabled", true),
            ltftAlertThreshold   = o.optDouble("ltftAlertThreshold", 7.5).toFloat(),
        )
    }

    private suspend fun loginRemote(email: String, passwordHash: String): RemoteAuthResponse =
        withContext(Dispatchers.IO) {
            try {
                val requestBody = JSONObject()
                    .put("email", email)
                    .put("password_hash", passwordHash)
                    .toString()
                    .toRequestBody(jsonMediaType)
                val request = Request.Builder()
                    .url("${ActyConfig.API_BASE}/api/v1/auth/login")
                    .post(requestBody)
                    .build()

                httpClient.newCall(request).execute().use { response ->
                    val responseText = response.body?.string().orEmpty()
                    if (!response.isSuccessful) {
                        val message = try {
                            JSONObject(responseText).optString("detail", "")
                        } catch (_: Exception) { "" }
                        return@withContext RemoteAuthResponse(error = message.ifBlank {
                            "No account found for that email."
                        })
                    }

                    val payload = JSONObject(responseText)
                    val accountJson = payload.optJSONObject("account")
                        ?: return@withContext RemoteAuthResponse(error = "Invalid account response from server.")
                    val pwHash = payload.optString("password_hash", passwordHash)
                    RemoteAuthResponse(account = remoteAccountFromJson(accountJson, pwHash))
                }
            } catch (_: Exception) {
                RemoteAuthResponse(error = "Could not reach the shared account service.")
            }
        }

    private suspend fun registerRemote(account: UserAccount): RemoteAuthResponse =
        withContext(Dispatchers.IO) {
            try {
                val requestBody = JSONObject()
                    .put("email", account.email.lowercase())
                    .put("password_hash", account.pwHash)
                    .put("account", accountToJson(account))
                    .toString()
                    .toRequestBody(jsonMediaType)
                val request = Request.Builder()
                    .url("${ActyConfig.API_BASE}/api/v1/auth/register")
                    .post(requestBody)
                    .build()

                httpClient.newCall(request).execute().use { response ->
                    val responseText = response.body?.string().orEmpty()
                    if (!response.isSuccessful) {
                        val message = try {
                            JSONObject(responseText).optString("detail", "")
                        } catch (_: Exception) { "" }
                        return@withContext RemoteAuthResponse(error = message.ifBlank {
                            "Could not create account."
                        })
                    }

                    val payload = JSONObject(responseText)
                    val accountJson = payload.optJSONObject("account")
                        ?: return@withContext RemoteAuthResponse(error = "Invalid account response from server.")
                    val pwHash = payload.optString("password_hash", account.pwHash)
                    RemoteAuthResponse(account = remoteAccountFromJson(accountJson, pwHash))
                }
            } catch (_: Exception) {
                RemoteAuthResponse(error = "Could not reach the shared account service.")
            }
        }

    private suspend fun syncRemote(account: UserAccount): RemoteAuthResponse =
        withContext(Dispatchers.IO) {
            try {
                val payload = JSONObject()
                    .put("email", account.email.lowercase())
                    .put("account", accountToJson(account))
                if (account.pwHash.isNotBlank()) {
                    payload.put("password_hash", account.pwHash)
                } else {
                    payload.put("password_hash", JSONObject.NULL)
                }
                val requestBody = payload
                    .toString()
                    .toRequestBody(jsonMediaType)
                val request = Request.Builder()
                    .url("${ActyConfig.API_BASE}/api/v1/auth/sync")
                    .post(requestBody)
                    .build()

                httpClient.newCall(request).execute().use { response ->
                    val responseText = response.body?.string().orEmpty()
                    if (!response.isSuccessful) {
                        val message = try {
                            JSONObject(responseText).optString("detail", "")
                        } catch (_: Exception) { "" }
                        return@withContext RemoteAuthResponse(error = message.ifBlank {
                            "Could not sync account."
                        })
                    }

                    val payload = JSONObject(responseText)
                    val accountJson = payload.optJSONObject("account")
                        ?: return@withContext RemoteAuthResponse(error = "Invalid account response from server.")
                    val pwHash = payload.optString("password_hash", account.pwHash)
                    RemoteAuthResponse(account = remoteAccountFromJson(accountJson, pwHash))
                }
            } catch (_: Exception) {
                RemoteAuthResponse(error = "Could not reach the shared account service.")
            }
        }

    private fun persistAccount(account: UserAccount, pushRemote: Boolean = false) {
        saveAccount(account)
        _sessionEmail = account.email.lowercase()
        if (!pushRemote) return

        backgroundScope.launch {
            val remote = syncRemote(account)
            remote.account?.let { saveAccount(it) }
        }
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

    suspend fun login(email: String, password: String): AuthResult {
        val normalizedEmail = email.trim().lowercase()
        val hash = hashPassword(password)
        val localAccount = getAccount(normalizedEmail)

        if (localAccount == null) {
            val remote = loginRemote(normalizedEmail, hash)
            val remoteAccount = remote.account
            return if (remoteAccount != null) {
                persistAccount(remoteAccount)
                AuthResult.Success
            } else {
                AuthResult.Error(remote.error ?: "No account found for that email.")
            }
        }

        return if (localAccount.pwHash.isEmpty()) {
            persistAccount(localAccount.copy(pwHash = hash), pushRemote = true)
            AuthResult.Success
        } else if (hash == localAccount.pwHash) {
            _sessionEmail = localAccount.email.lowercase()
            AuthResult.Success
        } else {
            val remote = loginRemote(normalizedEmail, hash)
            val remoteAccount = remote.account
            if (remoteAccount != null) {
                persistAccount(remoteAccount)
                AuthResult.Success
            } else {
                AuthResult.Error(remote.error ?: "Incorrect password.")
            }
        }
    }

    suspend fun register(
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
        val remote = registerRemote(account)
        val savedAccount = remote.account ?: account

        if (remote.account == null && remote.error?.contains("already exists", ignoreCase = true) == true) {
            return AuthResult.Error(remote.error)
        }

        persistAccount(savedAccount)
        return AuthResult.Success
    }

    // ── Google OAuth via Chrome Custom Tabs ───────────────────────────────────

    fun loginWithGoogle(context: Context) {
        val url = "${ActyConfig.SUPABASE_URL}/auth/v1/authorize" +
            "?provider=google" +
            "&redirect_to=${Uri.encode(ActyConfig.OAUTH_REDIRECT)}"
        CustomTabsIntent.Builder().build().launchUrl(context, Uri.parse(url))
    }

    /** Called from MainActivity.onNewIntent with the deep-link URI. Returns true on success. */
    suspend fun handleOAuthCallback(uri: Uri): Boolean = withContext(Dispatchers.IO) {
        // Supabase puts tokens in the URL fragment: #access_token=...&token_type=bearer&...
        val fragment = uri.fragment ?: return@withContext false
        val params = fragment.split("&").associate {
            val pair = it.split("=", limit = 2)
            (pair.getOrNull(0) ?: "") to (pair.getOrNull(1) ?: "")
        }
        val accessToken = params["access_token"] ?: return@withContext false

        // Fetch user info from Supabase
        try {
            val request = Request.Builder()
                .url("${ActyConfig.SUPABASE_URL}/auth/v1/user")
                .header("Authorization", "Bearer $accessToken")
                .header("apikey", ActyConfig.SUPABASE_ANON_KEY)
                .build()

            httpClient.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@withContext false
                val body = JSONObject(response.body?.string() ?: return@withContext false)
                val email = body.optString("email", "").lowercase()
                if (email.isEmpty()) return@withContext false

                val meta = body.optJSONObject("user_metadata") ?: JSONObject()
                val fullName = meta.optString("full_name", meta.optString("name", "")).ifEmpty { email }
                val avatarUrl = meta.optString("avatar_url", "")

                // Merge with any existing local account (preserve vehicles / settings)
                val existing = getAccount(email)
                val account = (existing ?: UserAccount(
                    username    = fullName,
                    displayName = fullName,
                    email       = email,
                )).copy(
                    displayName = fullName,
                    provider    = "google",
                    avatarUrl   = avatarUrl,
                )

                persistAccount(account)
                true
            }
        } catch (_: Exception) { false }
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
        persistAccount(updated, pushRemote = true)
    }

    fun addVehicle(vehicle: VehicleEntry) {
        val account = currentUser() ?: return
        val existing = account.vehicles
        val withId   = vehicle.copy(
            id       = vehicle.id.ifEmpty { UUID.randomUUID().toString() },
            isActive = existing.isEmpty(),   // first vehicle becomes active
        )
        persistAccount(account.copy(vehicles = existing + withId), pushRemote = true)
    }

    fun removeVehicle(id: String) {
        val account = currentUser() ?: return
        val wasActive = account.vehicles.firstOrNull { it.id == id }?.isActive ?: false
        val remaining = account.vehicles.filter { it.id != id }
        val adjusted = if (wasActive && remaining.isNotEmpty())
            remaining.mapIndexed { i, v -> if (i == 0) v.copy(isActive = true) else v }
        else remaining
        persistAccount(account.copy(vehicles = adjusted), pushRemote = true)
    }

    fun setActiveVehicle(id: String) {
        val account = currentUser() ?: return
        persistAccount(account.copy(
            vehicles = account.vehicles.map { it.copy(isActive = it.id == id) }
        ), pushRemote = true)
    }

    fun updateVehicleObd(vehicleId: String, mac: String) {
        val account = currentUser() ?: return
        persistAccount(account.copy(
            vehicles = account.vehicles.map { v ->
                if (v.id == vehicleId) v.copy(obdMac = mac) else v
            }
        ), pushRemote = true)
    }
}
