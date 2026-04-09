package com.acty.ui.screens

import android.content.Context
import android.graphics.Color as AColor
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.ui.graphics.*
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.acty.model.SessionState
import com.acty.ui.SessionViewModel
import com.acty.ui.theme.*
import com.github.mikephil.charting.charts.LineChart
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet

// ── PID display config ────────────────────────────────────────────────────────

data class PidConfig(
    val key:   String,
    val label: String,
    val unit:  String,
    val warn:  ((Double) -> Boolean)? = null,
    val alert: ((Double) -> Boolean)? = null,
)

private val PID_GRID = listOf(
    PidConfig("RPM",               "RPM",      "rpm"),
    PidConfig("SPEED",             "Speed",    "km/h"),
    PidConfig("COOLANT_TEMP",      "Coolant",  "°C",  warn = { it > 100 }, alert = { it > 108 }),
    PidConfig("ENGINE_LOAD",       "Load",     "%"),
    PidConfig("SHORT_FUEL_TRIM_1", "STFT",     "%",   warn = { it > 10 || it < -10 }),
    PidConfig("LONG_FUEL_TRIM_1",  "LTFT",     "%",   warn = { it > 7.5 || it < -7.5 }, alert = { it > 10 || it < -10 }),
    PidConfig("THROTTLE_POS",      "Throttle", "%"),
    PidConfig("CONTROL_VOLTAGE",   "Voltage",  "V",   warn = { it < 13.5 }, alert = { it < 13.0 }),
)

// ── CaptureScreen ─────────────────────────────────────────────────────────────

@Composable
fun CaptureScreen(viewModel: SessionViewModel) {
    val state   by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current

    var noteText     by remember { mutableStateOf("") }
    var selectedTags by remember { mutableStateOf(setOf<String>()) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(Color(0xFFFFF7ED), Color(0xFFF8FAFC), Color(0xFFF8FAFC)),
                    startY = 0f,
                    endY   = 800f,
                )
            )
            .verticalScroll(rememberScrollState())
            .systemBarsPadding()
            .padding(bottom = 16.dp),
    ) {
        // ── Session header ───────────────────────────────────
        CaptureHeader(state = state)

        Spacer(Modifier.height(16.dp))

        // ── RPM chart ────────────────────────────────────────
        RpmChartCard(rpmHistory = state.rpmHistory)

        Spacer(Modifier.height(16.dp))

        // ── PID grid ─────────────────────────────────────────
        SectionHeader(title = "Live Gauges")
        Spacer(Modifier.height(10.dp))
        PidGrid(state = state)

        Spacer(Modifier.height(16.dp))

        // ── DTC alerts ───────────────────────────────────────
        if (!state.isRunning || state.statusMessage.contains("DTC", ignoreCase = true)) {
            DtcAlertBanner()
            Spacer(Modifier.height(16.dp))
        }

        // ── Tags + Notes ─────────────────────────────────────
        SectionHeader(title = "Session Tags")
        Spacer(Modifier.height(10.dp))
        TagSelector(
            selected = selectedTags,
            onToggle = { tag ->
                selectedTags = if (tag in selectedTags) selectedTags - tag else selectedTags + tag
            },
        )

        Spacer(Modifier.height(12.dp))

        // Notes
        OutlinedTextField(
            value         = noteText,
            onValueChange = { noteText = it },
            modifier      = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp),
            label         = { Text("Session notes (optional)", style = MaterialTheme.typography.bodySmall) },
            minLines      = 2,
            maxLines      = 4,
            colors        = OutlinedTextFieldDefaults.colors(
                focusedBorderColor   = CactusBlue,
                unfocusedBorderColor = BgBorder,
                focusedLabelColor    = CactusBlue,
                unfocusedLabelColor  = TextDim,
                cursorColor          = CactusBlue,
                focusedTextColor     = TextPrimary,
                unfocusedTextColor   = TextPrimary,
                unfocusedContainerColor = Color.White,
                focusedContainerColor   = Color.White,
            ),
            shape = RoundedCornerShape(14.dp),
        )

        Spacer(Modifier.height(24.dp))

        // ── Start / Stop ─────────────────────────────────────
        CaptureButton(
            isRunning = state.isRunning,
            onStart   = { viewModel.startCapture(context) },
            onStop    = { viewModel.stopCapture(context) },
        )

        Spacer(Modifier.height(24.dp))
    }
}

// ── Capture Header ────────────────────────────────────────────────────────────

@Composable
fun CaptureHeader(state: SessionState) {
    val min = state.elapsedSeconds / 60
    val sec = state.elapsedSeconds % 60

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                Brush.verticalGradient(
                    listOf(Color(0xFFFEF3C7).copy(alpha = 0.6f), Color.Transparent)
                )
            )
            .padding(horizontal = 20.dp, vertical = 20.dp),
    ) {
        Column {
            Text(
                text  = "Capture",
                style = MaterialTheme.typography.headlineMedium.copy(
                    fontWeight = FontWeight.Black,
                    color      = TextPrimary,
                ),
            )
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                InfoChip(
                    icon  = Icons.Outlined.Timer,
                    label = "%02d:%02d".format(min, sec),
                    tint  = if (state.isRunning) CactusAmber else TextSecondary,
                )
                InfoChip(
                    icon  = Icons.Outlined.DataUsage,
                    label = "${state.sampleCount} samples",
                )
                if (state.vin != null) {
                    InfoChip(
                        icon  = Icons.Outlined.DirectionsCar,
                        label = state.vin.takeLast(6),
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(6.dp)
                        .clip(CircleShape)
                        .background(if (state.isRunning) StatusGreen else TextDim)
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    text  = state.statusMessage,
                    style = MaterialTheme.typography.bodySmall.copy(
                        color = if (state.isRunning) StatusGreenDim else TextSecondary,
                    ),
                )
            }
        }
    }
}

@Composable
fun InfoChip(
    icon:  androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    tint:  Color = TextSecondary,
) {
    Row(
        modifier = Modifier
            .shadow(3.dp, RoundedCornerShape(100.dp), spotColor = Color.Black.copy(alpha = 0.04f))
            .clip(RoundedCornerShape(100.dp))
            .background(Color.White)
            .border(0.5.dp, BgBorder, RoundedCornerShape(100.dp))
            .padding(horizontal = 10.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, tint = tint, modifier = Modifier.size(13.dp))
        Spacer(Modifier.width(4.dp))
        Text(
            text  = label,
            style = MaterialTheme.typography.labelSmall.copy(
                color      = tint,
                fontFamily = FontFamily.Monospace,
            ),
        )
    }
}

// ── RPM Chart ─────────────────────────────────────────────────────────────────

@Composable
fun RpmChartCard(rpmHistory: List<Float>) {
    ActyCard(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(
                modifier              = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment     = Alignment.CenterVertically,
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(CactusBlue)
                    )
                    Spacer(Modifier.width(8.dp))
                    Text("RPM — Live", style = MaterialTheme.typography.titleSmall)
                }
                val currentRpm = rpmHistory.lastOrNull()
                if (currentRpm != null) {
                    Text(
                        text  = "${currentRpm.toInt()}",
                        style = MaterialTheme.typography.headlineSmall.copy(
                            color      = CactusBlue,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace,
                        ),
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            AndroidView(
                factory  = { ctx -> buildRpmChart(ctx) },
                update   = { chart -> updateRpmChart(chart, rpmHistory) },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(130.dp),
            )
        }
    }
}

private fun buildRpmChart(ctx: Context): LineChart {
    return LineChart(ctx).apply {
        description.isEnabled  = false
        setTouchEnabled(false)
        isDragEnabled           = false
        setScaleEnabled(false)
        setDrawGridBackground(false)
        legend.isEnabled        = false
        xAxis.isEnabled         = false
        axisRight.isEnabled     = false
        setBackgroundColor(AColor.TRANSPARENT)
        axisLeft.apply {
            textColor   = AColor.argb(180, 71, 85, 105)   // slate-600 ~70%
            gridColor   = AColor.argb(30, 15, 23, 42)     // slate-900 ~12%
            axisMinimum = 0f
            axisMaximum = 8000f
            setLabelCount(4, true)
            textSize    = 10f
        }
    }
}

private fun updateRpmChart(chart: LineChart, history: List<Float>) {
    if (history.isEmpty()) return
    val entries = history.mapIndexed { i, v -> Entry(i.toFloat(), v) }
    val ds = LineDataSet(entries, "RPM").apply {
        color         = AColor.parseColor("#1E40AF")  // CactusBlue
        setDrawCircles(false)
        lineWidth     = 2.5f
        mode          = LineDataSet.Mode.CUBIC_BEZIER
        setDrawFilled(true)
        fillColor     = AColor.parseColor("#3B82F6")  // CactusBlueMid
        fillAlpha     = 25
        setDrawValues(false)
    }
    chart.data = LineData(ds)
    chart.invalidate()
}

// ── PID Grid ──────────────────────────────────────────────────────────────────

@Composable
fun PidGrid(state: SessionState) {
    val rows = PID_GRID.chunked(2)
    Column(
        modifier            = Modifier.padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        rows.forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                row.forEach { cfg ->
                    val reading = state.pidReadings[cfg.key]
                    val value   = reading?.value
                    PidGaugeCard(config = cfg, value = value, modifier = Modifier.weight(1f))
                }
                if (row.size < 2) Spacer(Modifier.weight(1f))
            }
        }
    }
}

@Composable
fun PidGaugeCard(config: PidConfig, value: Double?, modifier: Modifier = Modifier) {
    val tintColor = when {
        value != null && config.alert?.invoke(value) == true -> StatusRed
        value != null && config.warn?.invoke(value)  == true -> StatusAmber
        else                                                  -> CactusBlue
    }
    val bgColor = when {
        value != null && config.alert?.invoke(value) == true -> StatusRedBg
        value != null && config.warn?.invoke(value)  == true -> StatusAmberBg
        else                                                  -> Color.White
    }
    val borderColor = when {
        value != null && config.alert?.invoke(value) == true -> StatusRed.copy(alpha = 0.3f)
        value != null && config.warn?.invoke(value)  == true -> StatusAmber.copy(alpha = 0.3f)
        else                                                  -> BgBorder
    }

    val displayValue = if (value != null) {
        when {
            value == value.toLong().toDouble() -> value.toLong().toString()
            else                               -> "%.1f".format(value)
        }
    } else "—"

    Box(
        modifier = modifier
            .shadow(4.dp, RoundedCornerShape(14.dp), spotColor = tintColor.copy(alpha = 0.08f))
            .clip(RoundedCornerShape(14.dp))
            .background(bgColor)
            .border(0.5.dp, borderColor, RoundedCornerShape(14.dp))
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Column {
            Text(
                text  = config.label.uppercase(),
                style = MaterialTheme.typography.labelSmall.copy(
                    color         = TextDim,
                    letterSpacing = 0.8.sp,
                ),
            )
            Spacer(Modifier.height(4.dp))
            Text(
                text  = displayValue,
                style = MaterialTheme.typography.headlineSmall.copy(
                    color      = tintColor,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                ),
            )
            Text(
                text  = config.unit,
                style = MaterialTheme.typography.labelSmall.copy(color = TextDim),
            )
        }
    }
}

// ── DTC Alert Banner ──────────────────────────────────────────────────────────

@Composable
fun DtcAlertBanner() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .shadow(4.dp, RoundedCornerShape(14.dp), spotColor = StatusRed.copy(alpha = 0.12f))
            .clip(RoundedCornerShape(14.dp))
            .background(StatusRedBg)
            .border(0.5.dp, StatusRed.copy(alpha = 0.3f), RoundedCornerShape(14.dp))
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(StatusRed.copy(alpha = 0.10f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Outlined.Error, null, tint = StatusRed, modifier = Modifier.size(18.dp))
            }
            Spacer(Modifier.width(12.dp))
            Column {
                Text("DTC Detected", style = MaterialTheme.typography.titleSmall.copy(color = StatusRed))
                Text(
                    "Fault codes present. Check NeedleNest for details.",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

// ── Tag Selector ──────────────────────────────────────────────────────────────

private val SESSION_TAGS = listOf(
    "Highway", "Cold Start", "City", "Track", "Idle", "Tow", "Rain", "Hot Weather"
)

@Composable
fun TagSelector(selected: Set<String>, onToggle: (String) -> Unit) {
    val rows = SESSION_TAGS.chunked(4)
    Column(
        modifier            = Modifier.padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        rows.forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                row.forEach { tag ->
                    val isSelected = tag in selected
                    Text(
                        text  = tag,
                        style = MaterialTheme.typography.labelMedium.copy(
                            color      = if (isSelected) Color.White else TextSecondary,
                            fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
                        ),
                        modifier = Modifier
                            .shadow(
                                if (isSelected) 4.dp else 0.dp,
                                RoundedCornerShape(100.dp),
                                spotColor = CactusBlue.copy(alpha = 0.15f),
                            )
                            .clip(RoundedCornerShape(100.dp))
                            .background(if (isSelected) CactusBlue else Color.White)
                            .border(
                                0.5.dp,
                                if (isSelected) CactusBlue else BgBorder,
                                RoundedCornerShape(100.dp),
                            )
                            .clickable { onToggle(tag) }
                            .padding(horizontal = 12.dp, vertical = 6.dp),
                    )
                }
            }
        }
    }
}

// ── Capture Button ────────────────────────────────────────────────────────────

@Composable
fun CaptureButton(isRunning: Boolean, onStart: () -> Unit, onStop: () -> Unit) {
    val scale by animateFloatAsState(
        targetValue   = if (isRunning) 1.01f else 1f,
        animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy),
        label         = "btnScale",
    )

    // Running = red "Stop Session", idle = blue "Start Session"
    val bgBrush = if (isRunning)
        Brush.linearGradient(listOf(Color(0xFFDC2626), Color(0xFFEF4444)))
    else
        Brush.linearGradient(listOf(CactusBlue, CactusBlueMid))

    val borderColor = if (isRunning) StatusRed.copy(alpha = 0.5f) else CactusBlue
    val shadowColor = if (isRunning) StatusRed else CactusBlue

    Box(
        modifier         = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .shadow(10.dp, RoundedCornerShape(18.dp), spotColor = shadowColor.copy(alpha = 0.25f))
                .clip(RoundedCornerShape(18.dp))
                .background(bgBrush)
                .border(1.dp, borderColor, RoundedCornerShape(18.dp))
                .clickable(onClick = if (isRunning) onStop else onStart)
                .padding(vertical = 20.dp),
            contentAlignment = Alignment.Center,
        ) {
            Row(
                verticalAlignment     = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Icon(
                    imageVector        = if (isRunning) Icons.Filled.Stop else Icons.Filled.FiberManualRecord,
                    contentDescription = null,
                    tint               = Color.White,
                    modifier           = Modifier.size(22.dp),
                )
                Text(
                    text  = if (isRunning) "Stop Session" else "Start Session",
                    style = MaterialTheme.typography.titleMedium.copy(
                        color      = Color.White,
                        fontWeight = FontWeight.Bold,
                    ),
                )
            }
        }
    }
}
