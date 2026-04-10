package com.acty.ui.screens

import android.content.Intent
import androidx.compose.animation.*
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.acty.data.ActyPrefs
import com.acty.data.SyncManager
import com.acty.model.SessionSummary
import com.acty.ui.SessionViewModel
import com.acty.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

// ── SessionsScreen ────────────────────────────────────────────────────────────

@Composable
fun SessionsScreen(
    viewModel: SessionViewModel,
    onShare:   (String) -> Unit,
    onAnalyze: (String) -> Unit = {},   // filename → InsightsScreen
) {
    val context      = LocalContext.current
    val scope        = rememberCoroutineScope()
    val prefs        = remember { ActyPrefs(context) }
    val syncManager  = remember { SyncManager(context) }

    var sessions    by remember { mutableStateOf<List<SessionSummary>>(emptyList()) }
    var syncStatus  by remember { mutableStateOf("") }
    var isSyncing   by remember { mutableStateOf(false) }
    val sessionState by viewModel.state.collectAsStateWithLifecycle()

    fun reload() {
        scope.launch {
            sessions = loadSessions(syncManager)
        }
    }

    LaunchedEffect(Unit)                    { reload() }
    LaunchedEffect(sessionState.csvPath)    { if (sessionState.csvPath != null) reload() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(CactusBluePale, Color(0xFFF8FAFC)),
                    startY = 0f, endY = 500f,
                )
            )
            .systemBarsPadding(),
    ) {
        SessionsHeader(
            count       = sessions.size,
            syncedCount = sessions.count { it.synced },
            networkOk   = syncManager.isNetworkAvailable(),
            wifiOnly    = prefs.syncWifiOnly,
            isSyncing   = isSyncing,
            syncStatus  = syncStatus,
            onSync      = {
                scope.launch {
                    isSyncing  = true
                    syncStatus = "Syncing…"
                    val active = prefs.activeVehicle()
                    val results = syncManager.syncPendingFiles(
                        wifiOnly  = prefs.syncWifiOnly,
                        vehicleId = active?.id ?: "unknown",
                    )
                    val ok     = results.count { it.second }
                    val failed = results.count { !it.second }
                    syncStatus = when {
                        results.isEmpty() -> "All sessions up to date"
                        failed == 0       -> "$ok session(s) synced"
                        else              -> "$ok synced · $failed failed"
                    }
                    isSyncing = false
                    reload()
                }
            },
        )

        if (sessions.isNotEmpty()) {
            SessionStatsRow(sessions = sessions)
        }

        if (sessions.isEmpty()) {
            EmptySessionsState()
        } else {
            LazyColumn(
                contentPadding      = PaddingValues(horizontal = 20.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(sessions, key = { it.sessionId }) { session ->
                    SessionRow(
                        session   = session,
                        onAnalyze = { onAnalyze(session.fileName) },
                        onShare   = { onShare(session.sessionId) },
                        onExport  = {
                            // Export CSV + .sig via Android share sheet
                            val csvFile = File(syncManager.dataDir, session.fileName)
                            val sigFile = File(syncManager.dataDir, session.fileName.replace(".csv", ".sig"))
                            val uris = buildList {
                                if (csvFile.exists()) add(
                                    FileProvider.getUriForFile(context, "${context.packageName}.provider", csvFile)
                                )
                                if (sigFile.exists()) add(
                                    FileProvider.getUriForFile(context, "${context.packageName}.provider", sigFile)
                                )
                            }
                            if (uris.isNotEmpty()) {
                                val intent = Intent(Intent.ACTION_SEND_MULTIPLE).apply {
                                    type = "text/plain"
                                    putParcelableArrayListExtra(Intent.EXTRA_STREAM, ArrayList(uris))
                                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                }
                                context.startActivity(Intent.createChooser(intent, "Export Session Data"))
                            }
                        },
                    )
                }
                item { Spacer(Modifier.height(80.dp)) }
            }
        }
    }
}

// ── Header ────────────────────────────────────────────────────────────────────

@Composable
fun SessionsHeader(
    count:      Int,
    syncedCount: Int,
    networkOk:  Boolean,
    wifiOnly:   Boolean,
    isSyncing:  Boolean,
    syncStatus: String,
    onSync:     () -> Unit,
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp, vertical = 20.dp),
    ) {
        Column {
            Row(
                modifier              = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment     = Alignment.CenterVertically,
            ) {
                Column {
                    Text(
                        text  = "Sessions",
                        style = MaterialTheme.typography.headlineMedium.copy(
                            fontWeight = FontWeight.Black,
                            color      = TextPrimary,
                        ),
                    )
                    Text(
                        text  = "$count sessions · $syncedCount synced",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }

                // Sync button
                val canSync = networkOk && !isSyncing
                Box(
                    modifier = Modifier
                        .shadow(if (canSync) 5.dp else 0.dp, RoundedCornerShape(12.dp),
                            spotColor = CactusBlue.copy(alpha = 0.15f))
                        .clip(RoundedCornerShape(12.dp))
                        .background(if (canSync) CactusBlue else BgCardElevated)
                        .border(0.5.dp, if (canSync) CactusBlue else BgBorder, RoundedCornerShape(12.dp))
                        .clickable(enabled = canSync, onClick = onSync)
                        .padding(horizontal = 14.dp, vertical = 10.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    if (isSyncing) {
                        CircularProgressIndicator(
                            modifier    = Modifier.size(16.dp),
                            color       = CactusBlue,
                            strokeWidth = 2.dp,
                        )
                    } else {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                Icons.Outlined.Sync, null,
                                tint     = if (canSync) Color.White else TextDim,
                                modifier = Modifier.size(16.dp),
                            )
                            Spacer(Modifier.width(6.dp))
                            Text(
                                text  = if (!networkOk) "Offline" else if (wifiOnly) "Sync (WiFi)" else "Sync",
                                style = MaterialTheme.typography.labelLarge.copy(
                                    color = if (canSync) Color.White else TextDim,
                                ),
                            )
                        }
                    }
                }
            }

            if (syncStatus.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    val isOk = syncStatus.contains("up to date") || syncStatus.contains("synced")
                    Icon(
                        imageVector        = if (isOk) Icons.Filled.CheckCircle else Icons.Outlined.CloudSync,
                        contentDescription = null,
                        tint               = if (isOk) StatusGreenDim else TextSecondary,
                        modifier           = Modifier.size(13.dp),
                    )
                    Spacer(Modifier.width(4.dp))
                    Text(syncStatus, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

// ── Stats Row ─────────────────────────────────────────────────────────────────

@Composable
fun SessionStatsRow(sessions: List<SessionSummary>) {
    val totalKb = sessions.sumOf { it.sizeKb }
    val pending = sessions.count { !it.synced }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .padding(bottom = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        MiniStatCard(
            label    = "Total Size",
            value    = if (totalKb > 1024) "%.1f MB".format(totalKb / 1024) else "%.0f KB".format(totalKb),
            color    = TextSecondary,
            modifier = Modifier.weight(1f),
        )
        MiniStatCard(
            label    = "Pending",
            value    = "$pending",
            color    = if (pending > 0) StatusAmber else StatusGreen,
            modifier = Modifier.weight(1f),
        )
        MiniStatCard(
            label    = "Sessions",
            value    = "${sessions.size}",
            color    = CactusBlue,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
fun MiniStatCard(label: String, value: String, color: Color, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .shadow(4.dp, RoundedCornerShape(12.dp), spotColor = Color.Black.copy(alpha = 0.05f))
            .clip(RoundedCornerShape(12.dp))
            .background(Color.White)
            .border(0.5.dp, BgBorder, RoundedCornerShape(12.dp))
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Column {
            Text(label, style = MaterialTheme.typography.labelSmall)
            Text(value, style = MaterialTheme.typography.titleLarge.copy(color = color, fontWeight = FontWeight.Bold))
        }
    }
}

// ── Session Row ───────────────────────────────────────────────────────────────

@Composable
fun SessionRow(session: SessionSummary, onAnalyze: () -> Unit = {}, onShare: () -> Unit, onExport: () -> Unit) {
    var expanded by remember { mutableStateOf(false) }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .shadow(5.dp, RoundedCornerShape(16.dp), spotColor = Color.Black.copy(alpha = 0.05f))
            .clip(RoundedCornerShape(16.dp))
            .background(Color.White)
            .border(0.5.dp, BgBorder, RoundedCornerShape(16.dp))
            .clickable { expanded = !expanded },
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(
                modifier              = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment     = Alignment.Top,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        text  = session.displayDate,
                        style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.SemiBold),
                    )
                    Spacer(Modifier.height(4.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(
                            text  = "%.1f KB".format(session.sizeKb),
                            style = MaterialTheme.typography.bodySmall,
                        )
                        if (session.sampleCount > 0) {
                            Text("·", style = MaterialTheme.typography.bodySmall.copy(color = TextDim))
                            Text(
                                text  = "${session.sampleCount} samples",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }

                val (badgeText, badgeColor, badgeBg) = if (session.synced) {
                    Triple("SYNCED", StatusGreenDim, StatusGreenBg)
                } else {
                    Triple("PENDING", StatusAmber, StatusAmberBg)
                }
                Text(
                    text  = badgeText,
                    style = MaterialTheme.typography.labelSmall.copy(color = badgeColor),
                    modifier = Modifier
                        .clip(RoundedCornerShape(100.dp))
                        .background(badgeBg)
                        .border(0.5.dp, badgeColor.copy(alpha = 0.25f), RoundedCornerShape(100.dp))
                        .padding(horizontal = 8.dp, vertical = 3.dp),
                )
            }

            AnimatedVisibility(visible = expanded) {
                Column {
                    Spacer(Modifier.height(12.dp))
                    HorizontalDivider(color = BgBorder, thickness = 0.5.dp)
                    Spacer(Modifier.height(12.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        SessionAction(
                            icon     = Icons.Outlined.Analytics,
                            label    = "Analyze",
                            onClick  = onAnalyze,
                            modifier = Modifier.weight(1f),
                        )
                        SessionAction(
                            icon     = Icons.Outlined.Share,
                            label    = "Share",
                            onClick  = onShare,
                            modifier = Modifier.weight(1f),
                        )
                        SessionAction(
                            icon     = Icons.Outlined.FileDownload,
                            label    = "Export",
                            onClick  = onExport,
                            modifier = Modifier.weight(1f),
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun SessionAction(
    icon:     androidx.compose.ui.graphics.vector.ImageVector,
    label:    String,
    onClick:  () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(10.dp))
            .background(BgCardElevated)
            .border(0.5.dp, BgBorder, RoundedCornerShape(10.dp))
            .clickable(onClick = onClick)
            .padding(vertical = 10.dp),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(icon, null, tint = CactusBlue, modifier = Modifier.size(18.dp))
            Spacer(Modifier.height(3.dp))
            Text(label, style = MaterialTheme.typography.labelSmall.copy(color = TextSecondary))
        }
    }
}

// ── Empty State ───────────────────────────────────────────────────────────────

@Composable
fun EmptySessionsState() {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(80.dp)
                    .clip(RoundedCornerShape(24.dp))
                    .background(CactusBluePale),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector        = Icons.Outlined.DirectionsCar,
                    contentDescription = null,
                    tint               = CactusBlue,
                    modifier           = Modifier.size(40.dp),
                )
            }
            Text("No sessions yet", style = MaterialTheme.typography.headlineSmall.copy(color = TextPrimary))
            Text(
                text  = "Tap Capture to start your first drive session",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

// ── Data loader ───────────────────────────────────────────────────────────────

private suspend fun loadSessions(syncManager: SyncManager): List<SessionSummary> =
    withContext(Dispatchers.IO) {
        val dataDir  = syncManager.dataDir
        val manifest = syncManager.syncedFileNames()

        val csvFiles = dataDir.listFiles { f ->
            f.name.startsWith("acty_obd_") && f.name.endsWith(".csv")
        } ?: return@withContext emptyList()

        csvFiles
            .sortedByDescending { it.name }
            .map { f ->
                // filename format: acty_obd_YYYYMMDD_HHMMSS_<uuid>.csv
                val parts = f.nameWithoutExtension.split("_")
                val displayDate = try {
                    val date = parts.getOrNull(2) ?: ""
                    val time = parts.getOrNull(3) ?: ""
                    if (date.length == 8 && time.length == 6)
                        "${date.substring(0,4)}-${date.substring(4,6)}-${date.substring(6,8)} " +
                        "${time.substring(0,2)}:${time.substring(2,4)}"
                    else f.name
                } catch (_: Exception) { f.name }

                SessionSummary(
                    sessionId   = f.name,
                    displayDate = displayDate,
                    fileName    = f.name,
                    sizeKb      = f.length() / 1024.0,
                    synced      = f.name in manifest,
                )
            }
    }
