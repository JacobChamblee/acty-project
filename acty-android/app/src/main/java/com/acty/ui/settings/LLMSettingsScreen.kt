package com.acty.ui.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

// ── Data models ───────────────────────────────────────────────────────────────

data class ProviderMeta(
    val providerId: String,
    val displayName: String,
    val supportedModels: List<String>,
    val inputCostPerM: Double,
    val outputCostPerM: Double,
    val requiresApiKey: Boolean,
)

data class ConfiguredProvider(
    val providerId: String,
    val displayName: String,
    val modelId: String,
    val keyHint: String,           // "...xK9f" — last 4 chars only
    val isActive: Boolean,
    val lastUsedAt: String?,
)

sealed class SettingsEvent {
    data class ShowError(val message: String) : SettingsEvent()
    data class ShowSuccess(val message: String) : SettingsEvent()
}

data class LLMSettingsUiState(
    val availableProviders: List<ProviderMeta> = emptyList(),
    val configuredProviders: List<ConfiguredProvider> = emptyList(),
    val activeProviderId: String? = null,  // which provider is used for insight generation
    val isLoading: Boolean = false,
    val event: SettingsEvent? = null,
)

// ── ViewModel ─────────────────────────────────────────────────────────────────

class LLMSettingsViewModel(
    private val apiBase: String,
    private val userId: String,      // UUID from Supabase auth / local dev header
    private val httpClient: OkHttpClient = OkHttpClient(),
) : ViewModel() {

    private val _uiState = MutableStateFlow(LLMSettingsUiState())
    val uiState: StateFlow<LLMSettingsUiState> = _uiState

    private val json = "application/json".toMediaType()

    init {
        loadAll()
    }

    fun loadAll() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            val available = fetchAvailableProviders()
            val configured = fetchConfiguredProviders()
            _uiState.value = _uiState.value.copy(
                availableProviders = available,
                configuredProviders = configured,
                isLoading = false,
            )
        }
    }

    private suspend fun fetchAvailableProviders(): List<ProviderMeta> =
        withContext(Dispatchers.IO) {
            try {
                val req = Request.Builder()
                    .url("$apiBase/api/v1/llm-config/providers")
                    .get()
                    .build()
                val body = httpClient.newCall(req).execute().use { it.body?.string() ?: "" }
                val arr = JSONObject(body).getJSONArray("providers")
                (0 until arr.length()).map { i ->
                    val obj = arr.getJSONObject(i)
                    val cost = obj.optJSONObject("token_cost_estimate")
                    val models = obj.getJSONArray("supported_models")
                    ProviderMeta(
                        providerId = obj.getString("provider_id"),
                        displayName = obj.getString("display_name"),
                        supportedModels = (0 until models.length()).map { models.getString(it) },
                        inputCostPerM = cost?.optDouble("input_per_1m", 0.0) ?: 0.0,
                        outputCostPerM = cost?.optDouble("output_per_1m", 0.0) ?: 0.0,
                        requiresApiKey = obj.optBoolean("requires_api_key", true),
                    )
                }
            } catch (e: Exception) {
                emptyList()
            }
        }

    private suspend fun fetchConfiguredProviders(): List<ConfiguredProvider> =
        withContext(Dispatchers.IO) {
            try {
                val req = Request.Builder()
                    .url("$apiBase/api/v1/llm-config")
                    .addHeader("X-User-Id", userId)
                    .get()
                    .build()
                val body = httpClient.newCall(req).execute().use { it.body?.string() ?: "[]" }
                val arr = JSONArray(body)
                (0 until arr.length()).map { i ->
                    val obj = arr.getJSONObject(i)
                    ConfiguredProvider(
                        providerId = obj.getString("provider"),
                        displayName = obj.optString("display_name", obj.getString("provider")),
                        modelId = obj.getString("model_id"),
                        keyHint = obj.optString("key_hint", "...????"),
                        isActive = obj.optBoolean("is_active", true),
                        lastUsedAt = obj.optString("last_used_at").takeIf { it.isNotBlank() },
                    )
                }
            } catch (e: Exception) {
                emptyList()
            }
        }

    /** Validate key with server before saving. Never logs the key. */
    suspend fun validateKey(providerId: String, apiKey: String): Boolean =
        withContext(Dispatchers.IO) {
            try {
                val body = JSONObject().put("api_key", apiKey).toString()
                    .toRequestBody(json)
                val req = Request.Builder()
                    .url("$apiBase/api/v1/llm-config/$providerId/validate")
                    .addHeader("X-User-Id", userId)
                    .post(body)
                    .build()
                val resp = httpClient.newCall(req).execute()
                val respJson = JSONObject(resp.body?.string() ?: "{}")
                respJson.optBoolean("valid", false)
            } catch (e: Exception) {
                false
            }
        }

    /**
     * Register a key. The key is sent over HTTPS to the backend, which encrypts
     * it with AES-256-GCM before storing. The plaintext key must not be cached
     * or logged after this call returns.
     *
     * Pre-TEE note: Once the TEE node (AMD SEV-SNP) is live, key encryption
     * should happen on-device before network transmission. For now HTTPS is the
     * transport security boundary.
     */
    fun registerKey(providerId: String, modelId: String, apiKey: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            val isValid = validateKey(providerId, apiKey)
            if (!isValid) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    event = SettingsEvent.ShowError("Key validation failed for $providerId. Check the key and try again."),
                )
                return@launch
            }

            val success = withContext(Dispatchers.IO) {
                try {
                    val body = JSONObject()
                        .put("provider", providerId)
                        .put("model_id", modelId)
                        .put("api_key", apiKey)
                        .toString()
                        .toRequestBody(json)
                    val req = Request.Builder()
                        .url("$apiBase/api/v1/llm-config")
                        .addHeader("X-User-Id", userId)
                        .post(body)
                        .build()
                    val resp = httpClient.newCall(req).execute()
                    resp.isSuccessful
                } catch (e: Exception) {
                    false
                }
            }

            val configured = fetchConfiguredProviders()
            _uiState.value = _uiState.value.copy(
                configuredProviders = configured,
                isLoading = false,
                event = if (success)
                    SettingsEvent.ShowSuccess("$providerId key registered successfully")
                else
                    SettingsEvent.ShowError("Failed to register key — check server connection"),
            )
        }
    }

    fun removeKey(providerId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            withContext(Dispatchers.IO) {
                try {
                    val req = Request.Builder()
                        .url("$apiBase/api/v1/llm-config/$providerId")
                        .addHeader("X-User-Id", userId)
                        .delete()
                        .build()
                    httpClient.newCall(req).execute().close()
                } catch (_: Exception) { }
            }
            val configured = fetchConfiguredProviders()
            _uiState.value = _uiState.value.copy(
                configuredProviders = configured,
                isLoading = false,
                event = SettingsEvent.ShowSuccess("$providerId key removed"),
                activeProviderId = if (_uiState.value.activeProviderId == providerId) null
                                   else _uiState.value.activeProviderId,
            )
        }
    }

    fun setActiveProvider(providerId: String?) {
        _uiState.value = _uiState.value.copy(activeProviderId = providerId)
        // TODO: persist to SharedPreferences / Datastore
    }

    fun consumeEvent() {
        _uiState.value = _uiState.value.copy(event = null)
    }
}

// ── Composable screens ─────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LLMSettingsScreen(viewModel: LLMSettingsViewModel) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    // Consume one-shot events
    LaunchedEffect(uiState.event) {
        uiState.event?.let { event ->
            val msg = when (event) {
                is SettingsEvent.ShowError -> "Error: ${event.message}"
                is SettingsEvent.ShowSuccess -> event.message
            }
            snackbarHostState.showSnackbar(msg)
            viewModel.consumeEvent()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("AI Provider Settings", fontWeight = FontWeight.SemiBold) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        if (uiState.isLoading && uiState.availableProviders.isEmpty()) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // Active provider selector
            item {
                ActiveProviderCard(
                    activeProviderId = uiState.activeProviderId,
                    configuredProviders = uiState.configuredProviders,
                    onSelectProvider = { viewModel.setActiveProvider(it) },
                )
            }

            // Cost transparency
            if (uiState.configuredProviders.isNotEmpty()) {
                item {
                    CostTransparencyCard(configured = uiState.configuredProviders)
                }
            }

            item {
                Text(
                    "API Keys",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 8.dp, bottom = 4.dp),
                )
            }

            items(uiState.availableProviders) { provider ->
                val configured = uiState.configuredProviders.find { it.providerId == provider.providerId }
                ProviderCard(
                    meta = provider,
                    configured = configured,
                    isActive = uiState.activeProviderId == provider.providerId,
                    onRegister = { modelId, key -> viewModel.registerKey(provider.providerId, modelId, key) },
                    onRemove = { viewModel.removeKey(provider.providerId) },
                    onSetActive = { viewModel.setActiveProvider(provider.providerId) },
                )
            }
        }
    }
}

@Composable
private fun ActiveProviderCard(
    activeProviderId: String?,
    configuredProviders: List<ConfiguredProvider>,
    onSelectProvider: (String?) -> Unit,
) {
    val label = if (activeProviderId == null) "Cactus Local (free)"
                else configuredProviders.find { it.providerId == activeProviderId }?.displayName
                    ?: activeProviderId

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Icon(Icons.Filled.Psychology, contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary)
                Text("Active AI Provider", fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onPrimaryContainer)
            }
            Text(label, fontSize = 18.sp, fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onPrimaryContainer)
            if (activeProviderId != null) {
                TextButton(onClick = { onSelectProvider(null) }) {
                    Text("Switch to Cactus Local (free)")
                }
            }
        }
    }
}

@Composable
private fun CostTransparencyCard(configured: List<ConfiguredProvider>) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Icon(Icons.Filled.Receipt, contentDescription = null,
                    tint = MaterialTheme.colorScheme.secondary)
                Text("Cost Transparency", fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSecondaryContainer)
            }
            Spacer(Modifier.height(4.dp))
            configured.forEach { c ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(c.displayName, color = MaterialTheme.colorScheme.onSecondaryContainer)
                    Text(
                        c.lastUsedAt?.let { "Last used: ${it.take(10)}" } ?: "Not used yet",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSecondaryContainer.copy(alpha = 0.7f),
                    )
                }
            }
            Spacer(Modifier.height(4.dp))
            Text(
                "Costs are charged to your own API key — Cactus never sees your usage.",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSecondaryContainer.copy(alpha = 0.6f),
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ProviderCard(
    meta: ProviderMeta,
    configured: ConfiguredProvider?,
    isActive: Boolean,
    onRegister: (modelId: String, apiKey: String) -> Unit,
    onRemove: () -> Unit,
    onSetActive: () -> Unit,
) {
    var showKeyInput by remember { mutableStateOf(false) }
    var apiKeyInput by remember { mutableStateOf("") }
    var keyVisible by remember { mutableStateOf(false) }
    var selectedModel by remember { mutableStateOf(configured?.modelId ?: meta.supportedModels.firstOrNull() ?: "") }
    var modelDropdownExpanded by remember { mutableStateOf(false) }

    val isConfigured = configured != null

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        border = if (isActive)
            androidx.compose.foundation.BorderStroke(2.dp, MaterialTheme.colorScheme.primary)
        else null,
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            // Header row
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    // Connected / not configured indicator dot
                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .background(
                                color = if (isConfigured) Color(0xFF22C55E) else Color(0xFF94A3B8),
                                shape = CircleShape,
                            )
                    )
                    Text(meta.displayName, fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                }
                if (isActive) {
                    Badge { Text("Active") }
                }
            }

            // Key hint or "not configured"
            if (isConfigured) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Icon(Icons.Filled.Key, contentDescription = null,
                        modifier = Modifier.size(14.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(configured!!.keyHint, fontSize = 13.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace)
                    Text("• ${configured.modelId}", fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f))
                }
            } else {
                Text("No API key configured", fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f))
            }

            // Cost estimate
            if (meta.inputCostPerM > 0) {
                Text(
                    "\$${meta.inputCostPerM}/M in · \$${meta.outputCostPerM}/M out",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f),
                )
            }

            // Model selector (shown when adding a key or configured)
            if (showKeyInput || isConfigured) {
                ExposedDropdownMenuBox(
                    expanded = modelDropdownExpanded,
                    onExpandedChange = { modelDropdownExpanded = it },
                ) {
                    OutlinedTextField(
                        value = selectedModel,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("Model") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(modelDropdownExpanded) },
                        modifier = Modifier.menuAnchor().fillMaxWidth(),
                        colors = ExposedDropdownMenuDefaults.outlinedTextFieldColors(),
                    )
                    ExposedDropdownMenu(
                        expanded = modelDropdownExpanded,
                        onDismissRequest = { modelDropdownExpanded = false },
                    ) {
                        meta.supportedModels.forEach { model ->
                            DropdownMenuItem(
                                text = { Text(model) },
                                onClick = {
                                    selectedModel = model
                                    modelDropdownExpanded = false
                                },
                            )
                        }
                    }
                }
            }

            // Key input field (shown when adding)
            if (showKeyInput) {
                OutlinedTextField(
                    value = apiKeyInput,
                    onValueChange = { apiKeyInput = it },
                    label = { Text("API Key") },
                    placeholder = { Text("sk-...") },
                    visualTransformation = if (keyVisible) VisualTransformation.None
                                          else PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    trailingIcon = {
                        IconButton(onClick = { keyVisible = !keyVisible }) {
                            Icon(
                                if (keyVisible) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                                contentDescription = if (keyVisible) "Hide key" else "Show key",
                            )
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
            }

            // Action buttons
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (!isConfigured) {
                    if (!showKeyInput) {
                        OutlinedButton(onClick = { showKeyInput = true }) {
                            Icon(Icons.Filled.Add, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(4.dp))
                            Text("Add Key")
                        }
                    } else {
                        Button(
                            onClick = {
                                if (apiKeyInput.isNotBlank()) {
                                    onRegister(selectedModel, apiKeyInput)
                                    apiKeyInput = ""        // clear from memory immediately
                                    showKeyInput = false
                                }
                            },
                            enabled = apiKeyInput.length >= 8,
                        ) {
                            Text("Test & Save")
                        }
                        TextButton(onClick = {
                            showKeyInput = false
                            apiKeyInput = ""
                        }) {
                            Text("Cancel")
                        }
                    }
                } else {
                    if (!isActive) {
                        Button(onClick = onSetActive) {
                            Text("Use for insights")
                        }
                    }
                    OutlinedButton(onClick = onRemove) {
                        Icon(Icons.Filled.Delete, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("Remove")
                    }
                }
            }
        }
    }
}
