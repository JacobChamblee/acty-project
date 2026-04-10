package com.acty.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.acty.ActyConfig
import com.acty.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

// ── Suggested questions ───────────────────────────────────────────────────────

private val SUGGESTIONS = listOf(
    "Summarize the key findings from this drive session.",
    "Are there any concerning patterns in the fuel trim data?",
    "How does the engine load profile look? Any signs of stress?",
    "What does the battery voltage trend suggest about charging health?",
    "Are there any signs of a vacuum leak or MAF sensor issues?",
    "Give me an overall health assessment based on this data.",
)

// ── InsightsScreen ────────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InsightsScreen(
    sessionFilename: String,          // pre-selected from SessionsScreen
    onBack: () -> Unit,
) {
    val context       = LocalContext.current
    val scope         = rememberCoroutineScope()
    val clipboard     = LocalClipboardManager.current

    // Model list
    var models        by remember { mutableStateOf<List<OllamaModel>>(emptyList()) }
    var modelsLoading by remember { mutableStateOf(true) }
    var modelsError   by remember { mutableStateOf("") }
    var selectedModel by remember { mutableStateOf("") }

    // Query
    var question      by remember { mutableStateOf("") }

    // Streaming
    var streaming     by remember { mutableStateOf(false) }
    var response      by remember { mutableStateOf("") }
    var sessionDate   by remember { mutableStateOf("") }
    var alerts        by remember { mutableStateOf<List<String>>(emptyList()) }
    var streamError   by remember { mutableStateOf("") }
    var streamJob     by remember { mutableStateOf<Job?>(null) }

    val httpClient = remember {
        OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)
            .build()
    }

    // Fetch available Ollama models
    LaunchedEffect(Unit) {
        modelsLoading = true
        modelsError   = ""
        val fetched = fetchOllamaModels(httpClient)
        if (fetched == null) {
            modelsError   = "Ollama server unreachable. Make sure it's running."
        } else {
            models        = fetched
            selectedModel = fetched.firstOrNull()?.name ?: ""
        }
        modelsLoading = false
    }

    fun doAnalyze() {
        if (selectedModel.isEmpty() || streaming) return
        val q = question.trim().ifEmpty { SUGGESTIONS[0] }

        streamJob?.cancel()
        streaming   = true
        response    = ""
        sessionDate = ""
        alerts      = emptyList()
        streamError = ""

        streamJob = scope.launch {
            streamOllamaAnalysis(
                client          = httpClient,
                sessionFilename = sessionFilename,
                question        = q,
                model           = selectedModel,
                onMeta          = { date, alertList ->
                    sessionDate = date
                    alerts      = alertList
                },
                onToken         = { token -> response += token },
                onError         = { err -> streamError = err; streaming = false },
                onDone          = { streaming = false },
            )
        }
    }

    fun stopStream() {
        streamJob?.cancel()
        streaming = false
    }

    // ── UI ───────────────────────────────────────────────────────────────────

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(Color(0xFFF0F4FF), Color(0xFFF8FAFC)),
                    startY = 0f, endY = 900f,
                )
            )
            .systemBarsPadding(),
    ) {
        // ── Top bar ──────────────────────────────────────────────────────────
        Row(
            modifier              = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment     = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.Filled.ArrowBack, contentDescription = "Back", tint = TextPrimary)
            }
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Icon(Icons.Outlined.AutoAwesome, contentDescription = null, tint = CactusBlue, modifier = Modifier.size(18.dp))
                    Text(
                        "AI Insights",
                        style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.ExtraBold, color = TextPrimary),
                    )
                }
                if (sessionFilename.isNotEmpty()) {
                    Text(
                        sessionFilename,
                        style = MaterialTheme.typography.bodySmall.copy(color = TextDim),
                        maxLines = 1,
                    )
                }
            }
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Spacer(Modifier.height(4.dp))

            // ── Model picker ─────────────────────────────────────────────────
            Surface(
                shape           = RoundedCornerShape(16.dp),
                color           = Color.White,
                shadowElevation = 2.dp,
                modifier        = Modifier.fillMaxWidth(),
            ) {
                Column(Modifier.padding(16.dp)) {
                    Text("Model", style = MaterialTheme.typography.labelSmall.copy(color = TextDim, fontWeight = FontWeight.Bold))
                    Spacer(Modifier.height(10.dp))
                    when {
                        modelsLoading -> {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp, color = CactusBlue)
                                Text("Connecting to Ollama…", style = MaterialTheme.typography.bodySmall.copy(color = TextDim))
                            }
                        }
                        modelsError.isNotEmpty() -> {
                            Text(modelsError, style = MaterialTheme.typography.bodySmall.copy(color = StatusRed))
                        }
                        else -> {
                            Row(
                                modifier              = Modifier.horizontalScroll(rememberScrollState()),
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                models.forEach { m ->
                                    val sel = m.name == selectedModel
                                    Box(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(10.dp))
                                            .background(if (sel) CactusBluePale else Color(0xFFF8FAFC))
                                            .border(
                                                1.dp,
                                                if (sel) CactusBlue else BgBorder,
                                                RoundedCornerShape(10.dp),
                                            )
                                            .clickable { selectedModel = m.name }
                                            .padding(horizontal = 14.dp, vertical = 8.dp),
                                    ) {
                                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                            Text(
                                                m.name,
                                                style    = MaterialTheme.typography.bodySmall.copy(
                                                    fontWeight = FontWeight.SemiBold,
                                                    color      = if (sel) CactusBlue else TextPrimary,
                                                ),
                                            )
                                            if (m.sizeGb > 0) {
                                                Text(
                                                    "%.1f GB".format(m.sizeGb),
                                                    style = MaterialTheme.typography.labelSmall.copy(color = TextDim),
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ── Question input ────────────────────────────────────────────────
            Surface(
                shape           = RoundedCornerShape(16.dp),
                color           = Color.White,
                shadowElevation = 2.dp,
                modifier        = Modifier.fillMaxWidth(),
            ) {
                Column(Modifier.padding(16.dp)) {
                    Text("Your Question", style = MaterialTheme.typography.labelSmall.copy(color = TextDim, fontWeight = FontWeight.Bold))
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value         = question,
                        onValueChange = { question = it },
                        modifier      = Modifier.fillMaxWidth(),
                        placeholder   = { Text("Ask anything about this session…", style = MaterialTheme.typography.bodySmall.copy(color = TextDim)) },
                        shape         = RoundedCornerShape(10.dp),
                        minLines      = 2,
                        maxLines      = 4,
                        colors        = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor   = CactusBlue,
                            unfocusedBorderColor = BgBorder,
                        ),
                    )
                    Spacer(Modifier.height(10.dp))
                    // Suggestion chips
                    Text("Suggestions", style = MaterialTheme.typography.labelSmall.copy(color = TextDim, fontWeight = FontWeight.Bold))
                    Spacer(Modifier.height(6.dp))
                    SUGGESTIONS.forEach { s ->
                        val active = question == s
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 3.dp)
                                .clip(RoundedCornerShape(8.dp))
                                .background(if (active) CactusBluePale else Color(0xFFF8FAFC))
                                .border(1.dp, if (active) CactusBlue else BgBorder, RoundedCornerShape(8.dp))
                                .clickable { question = s }
                                .padding(horizontal = 12.dp, vertical = 8.dp),
                        ) {
                            Text(
                                s,
                                style = MaterialTheme.typography.bodySmall.copy(
                                    color      = if (active) CactusBlue else TextSecondary,
                                    fontWeight = if (active) FontWeight.SemiBold else FontWeight.Normal,
                                ),
                            )
                        }
                    }
                }
            }

            // ── Analyze button ────────────────────────────────────────────────
            if (streaming) {
                Button(
                    onClick  = { stopStream() },
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                    shape    = RoundedCornerShape(13.dp),
                    colors   = ButtonDefaults.buttonColors(containerColor = StatusRed),
                ) {
                    Icon(Icons.Filled.Stop, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Stop", fontWeight = FontWeight.SemiBold, fontSize = 15.sp)
                }
            } else {
                Button(
                    onClick  = { doAnalyze() },
                    enabled  = selectedModel.isNotEmpty() && !modelsLoading,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                    shape    = RoundedCornerShape(13.dp),
                    colors   = ButtonDefaults.buttonColors(containerColor = CactusBlue),
                ) {
                    Icon(Icons.Outlined.AutoAwesome, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Analyze Session", fontWeight = FontWeight.SemiBold, fontSize = 15.sp)
                }
            }

            // ── Alerts ───────────────────────────────────────────────────────
            AnimatedVisibility(visible = alerts.isNotEmpty()) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    alerts.forEach { a ->
                        val isCrit = a.startsWith("CRITICAL")
                        Surface(
                            shape  = RoundedCornerShape(8.dp),
                            color  = if (isCrit) StatusRedBg else StatusAmberBg,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(
                                a,
                                style    = MaterialTheme.typography.bodySmall.copy(
                                    fontFamily = FontFamily.Monospace,
                                    color      = if (isCrit) StatusRed else StatusAmber,
                                    fontWeight = FontWeight.SemiBold,
                                ),
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                            )
                        }
                    }
                }
            }

            // ── Response ─────────────────────────────────────────────────────
            AnimatedVisibility(visible = response.isNotEmpty() || streaming || streamError.isNotEmpty()) {
                Surface(
                    shape           = RoundedCornerShape(16.dp),
                    color           = Color.White,
                    shadowElevation = 2.dp,
                    modifier        = Modifier.fillMaxWidth(),
                ) {
                    Column(Modifier.padding(16.dp)) {
                        Row(
                            modifier              = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment     = Alignment.CenterVertically,
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Icon(Icons.Outlined.AutoAwesome, contentDescription = null, tint = CactusBlue, modifier = Modifier.size(16.dp))
                                Text(
                                    if (streaming) "Analyzing…" else "Analysis",
                                    style = MaterialTheme.typography.labelMedium.copy(fontWeight = FontWeight.Bold, color = TextPrimary),
                                )
                            }
                            if (!streaming && response.isNotEmpty()) {
                                IconButton(
                                    onClick  = { clipboard.setText(AnnotatedString(response)) },
                                    modifier = Modifier.size(32.dp),
                                ) {
                                    Icon(Icons.Filled.ContentCopy, contentDescription = "Copy", tint = TextDim, modifier = Modifier.size(16.dp))
                                }
                            }
                        }

                        if (streamError.isNotEmpty()) {
                            Spacer(Modifier.height(8.dp))
                            Text("⚠ $streamError", style = MaterialTheme.typography.bodySmall.copy(color = StatusRed))
                        } else if (streaming && response.isEmpty()) {
                            Spacer(Modifier.height(12.dp))
                            LinearProgressIndicator(
                                modifier = Modifier.fillMaxWidth(),
                                color    = CactusBlue,
                            )
                        } else if (response.isNotEmpty()) {
                            Spacer(Modifier.height(10.dp))
                            Text(
                                text  = response + if (streaming) "▋" else "",
                                style = MaterialTheme.typography.bodySmall.copy(
                                    color      = TextPrimary,
                                    lineHeight = 22.sp,
                                ),
                            )
                        }

                        if (!streaming && sessionDate.isNotEmpty()) {
                            Spacer(Modifier.height(12.dp))
                            HorizontalDivider(color = BgBorder, thickness = 0.5.dp)
                            Spacer(Modifier.height(6.dp))
                            Text(
                                "Session: $sessionDate  ·  $selectedModel",
                                style = MaterialTheme.typography.labelSmall.copy(color = TextDim),
                            )
                        }
                    }
                }
            }

            Spacer(Modifier.height(80.dp))
        }
    }
}

// ── Data model ────────────────────────────────────────────────────────────────

data class OllamaModel(val name: String, val sizeGb: Double)

// ── Network helpers ───────────────────────────────────────────────────────────

private suspend fun fetchOllamaModels(client: OkHttpClient): List<OllamaModel>? =
    withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder()
                .url("${ActyConfig.API_BASE}/api/v1/ollama/models")
                .build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return@withContext null
                val body = JSONObject(resp.body?.string() ?: return@withContext null)
                val arr  = body.optJSONArray("models") ?: return@withContext emptyList()
                (0 until arr.length()).map { i ->
                    val m = arr.getJSONObject(i)
                    OllamaModel(
                        name   = m.optString("name", "unknown"),
                        sizeGb = m.optDouble("size_gb", 0.0),
                    )
                }
            }
        } catch (_: Exception) { null }
    }

private suspend fun streamOllamaAnalysis(
    client:          OkHttpClient,
    sessionFilename: String,
    question:        String,
    model:           String,
    onMeta:          suspend (date: String, alerts: List<String>) -> Unit,
    onToken:         suspend (String) -> Unit,
    onError:         suspend (String) -> Unit,
    onDone:          suspend () -> Unit,
) = withContext(Dispatchers.IO) {
    val bodyJson = JSONObject()
        .put("session_filename", sessionFilename.ifEmpty { null })
        .put("question", question)
        .put("model", model)
        .toString()
        .toRequestBody("application/json".toMediaType())

    val req = Request.Builder()
        .url("${ActyConfig.API_BASE}/api/v1/ollama/analyze")
        .post(bodyJson)
        .build()

    try {
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) {
                val msg = resp.body?.string()?.take(200) ?: "HTTP ${resp.code}"
                withContext(Dispatchers.Main) { onError(msg) }
                return@withContext
            }

            val source = resp.body?.source() ?: run {
                withContext(Dispatchers.Main) { onError("Empty response body") }
                return@withContext
            }

            while (!source.exhausted()) {
                val line = source.readUtf8Line() ?: break
                if (!line.startsWith("data: ")) continue
                val data = line.removePrefix("data: ")

                when {
                    data == "[DONE]" -> {
                        withContext(Dispatchers.Main) { onDone() }
                        return@withContext
                    }
                    data.startsWith("[ERROR]") -> {
                        withContext(Dispatchers.Main) { onError(data.removePrefix("[ERROR] ")) }
                        return@withContext
                    }
                    data.startsWith("{") -> {
                        // Meta event
                        try {
                            val meta     = JSONObject(data)
                            val date     = meta.optString("session", "")
                            val rawAlerts = meta.optJSONArray("alerts")
                            val alertList = if (rawAlerts != null)
                                (0 until rawAlerts.length()).map { rawAlerts.getString(it) }
                            else emptyList()
                            withContext(Dispatchers.Main) { onMeta(date, alertList) }
                        } catch (_: Exception) {}
                    }
                    else -> {
                        val token = data.replace("\\n", "\n")
                        withContext(Dispatchers.Main) { onToken(token) }
                    }
                }
            }
            withContext(Dispatchers.Main) { onDone() }
        }
    } catch (e: Exception) {
        withContext(Dispatchers.Main) { onError(e.message ?: "Connection error") }
    }
}
