package com.acty.ui.screens

import android.content.Context
import android.graphics.Color as AColor
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.acty.model.*
import com.acty.ui.SessionViewModel
import com.acty.ui.theme.*
import com.github.mikephil.charting.charts.LineChart
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet

// ── Sample analytics data ─────────────────────────────────────────────────────

private val sampleLtft = (0 until 60).map { i ->
    LtftDataPoint(
        timestamp = System.currentTimeMillis() - (60 - i) * 60_000L,
        stft      = (-2f + Math.sin(i * 0.3) * 3f).toFloat(),
        ltft      = (-5f - Math.sin(i * 0.1) * 2f - (if (i > 40) 2f else 0f)).toFloat(),
    )
}

private val sampleVoltage = (0 until 60).map { i ->
    VoltageDataPoint(
        timestamp = System.currentTimeMillis() - (60 - i) * 60_000L,
        voltage   = (13.8f + Math.sin(i * 0.2) * 0.4f - (if (i in 20..25) 1.5f else 0f)).toFloat(),
    )
}

private val sampleThermal = (0 until 60).map { i ->
    ThermalDataPoint(
        timestamp = System.currentTimeMillis() - (60 - i) * 60_000L,
        coolantC  = minOf(95f, 20f + i * 1.3f),
        oilC      = minOf(90f, 15f + i * 1.1f),
        catalystC = if (i > 10) minOf(450f, i * 8f) else null,
    )
}

private val sampleMpgHistory = listOf(
    MpgDataPoint(System.currentTimeMillis() - 6 * 86_400_000L, 25.4f),
    MpgDataPoint(System.currentTimeMillis() - 5 * 86_400_000L, 24.1f),
    MpgDataPoint(System.currentTimeMillis() - 4 * 86_400_000L, 26.8f),
    MpgDataPoint(System.currentTimeMillis() - 3 * 86_400_000L, 27.2f),
    MpgDataPoint(System.currentTimeMillis() - 2 * 86_400_000L, 25.9f),
    MpgDataPoint(System.currentTimeMillis() - 1 * 86_400_000L, 28.3f),
)

private val anomalyPoints = listOf(
    Triple(10L, "LTFT spike",     InsightSeverity.WARN),
    Triple(35L, "Voltage dip",    InsightSeverity.CRITICAL),
    Triple(48L, "Timing retard",  InsightSeverity.WARN),
)

// ── NeedleNestScreen ──────────────────────────────────────────────────────────

@Composable
fun NeedleNestScreen(viewModel: SessionViewModel) {
    var selectedTab by remember { mutableStateOf(NeedleNestTab.LTFT) }
    var dateRange   by remember { mutableStateOf("Last 7 Days") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(Color(0xFFF5F3FF), Color(0xFFF8FAFC), Color(0xFFF8FAFC)),
                    startY = 0f,
                    endY   = 800f,
                )
            )
            .systemBarsPadding()
    ) {
        NeedleNestHeader(dateRange = dateRange, onDateChange = { dateRange = it })

        NeedleNestTabRow(selected = selectedTab, onSelect = { selectedTab = it })

        Box(modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            AnimatedContent(
                targetState   = selectedTab,
                transitionSpec = {
                    (fadeIn(tween(200)) + slideInHorizontally { it / 4 }).togetherWith(
                        fadeOut(tween(150)) + slideOutHorizontally { -it / 4 }
                    )
                },
                label    = "tabContent",
                modifier = Modifier.fillMaxWidth(),
            ) { tab ->
                Column(Modifier.padding(bottom = 24.dp)) {
                    Spacer(Modifier.height(16.dp))
                    when (tab) {
                        NeedleNestTab.LTFT      -> LtftContent(sampleLtft)
                        NeedleNestTab.THERMAL   -> ThermalContent(sampleThermal)
                        NeedleNestTab.VOLTAGE   -> VoltageContent(sampleVoltage)
                        NeedleNestTab.MPG       -> MpgContent(sampleMpgHistory)
                        NeedleNestTab.ANOMALIES -> AnomaliesContent()
                    }
                }
            }
        }
    }
}

// ── Header ────────────────────────────────────────────────────────────────────

@Composable
fun NeedleNestHeader(dateRange: String, onDateChange: (String) -> Unit) {
    val ranges   = listOf("Last Drive", "Last 7 Days", "Last 30 Days", "All Time")
    var expanded by remember { mutableStateOf(false) }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                Brush.verticalGradient(
                    listOf(AccentPurple.copy(alpha = 0.10f), Color.Transparent)
                )
            )
            .padding(horizontal = 20.dp, vertical = 20.dp),
    ) {
        Row(
            modifier              = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment     = Alignment.CenterVertically,
        ) {
            Column {
                Text(
                    text  = "NeedleNest",
                    style = MaterialTheme.typography.headlineMedium.copy(
                        fontWeight = FontWeight.Black,
                        color      = TextPrimary,
                    ),
                )
                Text(
                    text  = "Analytics & Trends",
                    style = MaterialTheme.typography.bodySmall.copy(color = AccentPurple),
                )
            }

            Box {
                Row(
                    modifier = Modifier
                        .shadow(4.dp, RoundedCornerShape(100.dp), spotColor = Color.Black.copy(alpha = 0.05f))
                        .clip(RoundedCornerShape(100.dp))
                        .background(Color.White)
                        .border(0.5.dp, BgBorder, RoundedCornerShape(100.dp))
                        .clickable { expanded = true }
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Outlined.DateRange, null, tint = AccentPurple, modifier = Modifier.size(15.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(dateRange, style = MaterialTheme.typography.labelMedium.copy(color = TextPrimary))
                    Spacer(Modifier.width(4.dp))
                    Icon(Icons.Filled.ArrowDropDown, null, tint = TextDim, modifier = Modifier.size(16.dp))
                }
                DropdownMenu(
                    expanded         = expanded,
                    onDismissRequest = { expanded = false },
                    modifier         = Modifier.background(Color.White),
                ) {
                    ranges.forEach { r ->
                        DropdownMenuItem(
                            text    = { Text(r, style = MaterialTheme.typography.bodyMedium.copy(color = TextPrimary)) },
                            onClick = { onDateChange(r); expanded = false },
                        )
                    }
                }
            }
        }
    }
}

// ── Tab Row ───────────────────────────────────────────────────────────────────

@Composable
fun NeedleNestTabRow(selected: NeedleNestTab, onSelect: (NeedleNestTab) -> Unit) {
    ScrollableTabRow(
        selectedTabIndex = NeedleNestTab.entries.indexOf(selected),
        containerColor   = Color.White,
        contentColor     = CactusBlue,
        edgePadding      = 16.dp,
        indicator        = { tabPositions ->
            val idx = NeedleNestTab.entries.indexOf(selected)
            TabRowDefaults.SecondaryIndicator(
                modifier = Modifier
                    .tabIndicatorOffset(tabPositions[idx])
                    .clip(RoundedCornerShape(topStart = 3.dp, topEnd = 3.dp)),
                color    = CactusBlue,
            )
        },
        divider = { HorizontalDivider(color = BgBorder, thickness = 0.5.dp) },
    ) {
        NeedleNestTab.entries.forEach { tab ->
            Tab(
                selected = selected == tab,
                onClick  = { onSelect(tab) },
                text     = {
                    Text(
                        text  = tab.label,
                        style = MaterialTheme.typography.labelLarge.copy(
                            color      = if (selected == tab) CactusBlue else TextDim,
                            fontWeight = if (selected == tab) FontWeight.Bold else FontWeight.Normal,
                        ),
                    )
                },
            )
        }
    }
}

// ── LTFT Content ──────────────────────────────────────────────────────────────

@Composable
fun LtftContent(data: List<LtftDataPoint>) {
    Column(Modifier.padding(horizontal = 20.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            val avgLtft = data.map { it.ltft }.average().toFloat()
            val avgStft = data.map { it.stft }.average().toFloat()
            StatSummaryCard(
                label    = "Avg LTFT",
                value    = "%.1f%%".format(avgLtft),
                color    = if (avgLtft < -7.5f || avgLtft > 7.5f) StatusAmber else StatusGreen,
                modifier = Modifier.weight(1f),
            )
            StatSummaryCard(
                label    = "Avg STFT",
                value    = "%.1f%%".format(avgStft),
                color    = if (avgStft < -10f || avgStft > 10f) StatusRed
                           else if (avgStft < -5f || avgStft > 5f) StatusAmber
                           else StatusGreen,
                modifier = Modifier.weight(1f),
            )
        }

        Spacer(Modifier.height(16.dp))

        ActyCard(modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("LTFT / STFT Trend", style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(4.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    LegendDot(color = CactusBlue,  label = "LTFT")
                    LegendDot(color = CactusAmber, label = "STFT")
                }
                Spacer(Modifier.height(8.dp))
                AndroidView(
                    factory = { ctx -> buildMultiLineChart(ctx) },
                    update  = { chart ->
                        val ltftEntries = data.mapIndexed { i, p -> Entry(i.toFloat(), p.ltft) }
                        val stftEntries = data.mapIndexed { i, p -> Entry(i.toFloat(), p.stft) }
                        val ds1 = makeLightLineDataSet(ltftEntries, "LTFT", AColor.parseColor("#1E40AF"))
                        val ds2 = makeLightLineDataSet(stftEntries, "STFT", AColor.parseColor("#F59E0B"))
                        chart.data = LineData(ds1, ds2)
                        chart.invalidate()
                    },
                    modifier = Modifier.fillMaxWidth().height(160.dp),
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text  = "Thresholds: ±7.5% warn  ·  ±10% action",
                    style = MaterialTheme.typography.labelSmall.copy(color = TextDim),
                )
            }
        }

        Spacer(Modifier.height(16.dp))

        InterpretationCard(
            title    = "Fuel Trim Analysis",
            body     = "LTFT running lean (negative) — typically indicates excess airflow or lean mixture. Values drifting below −7.5% warm suggest MAF sensor drift, vacuum leak, or injector issue. Cross-session trend: worsening.",
            severity = InsightSeverity.WARN,
        )
    }
}

// ── Thermal Content ───────────────────────────────────────────────────────────

@Composable
fun ThermalContent(data: List<ThermalDataPoint>) {
    Column(Modifier.padding(horizontal = 20.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            val maxCoolant = data.maxOfOrNull { it.coolantC } ?: 0f
            val warmupIdx  = data.indexOfFirst { it.coolantC >= 80 }
            StatSummaryCard("Max Coolant", "%.0f°C".format(maxCoolant), StatusGreen,   Modifier.weight(1f))
            StatSummaryCard("80°C Warmup", if (warmupIdx > 0) "${warmupIdx}s" else "—", StatusBlue, Modifier.weight(1f))
        }
        Spacer(Modifier.height(16.dp))
        ActyCard(modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("Thermal Profile", style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(4.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    LegendDot(color = StatusBlue,  label = "Coolant")
                    LegendDot(color = CactusAmber, label = "Oil")
                    LegendDot(color = StatusRed,   label = "Catalyst")
                }
                Spacer(Modifier.height(8.dp))
                AndroidView(
                    factory = { ctx -> buildMultiLineChart(ctx, yMax = 500f) },
                    update  = { chart ->
                        val coolEntries = data.mapIndexed { i, p -> Entry(i.toFloat(), p.coolantC) }
                        val oilEntries  = data.mapIndexed { i, p -> Entry(i.toFloat(), p.oilC ?: 0f) }
                        val catEntries  = data.mapIndexed { i, p -> Entry(i.toFloat(), p.catalystC ?: 0f) }
                        chart.data = LineData(
                            makeLightLineDataSet(coolEntries, "Coolant", AColor.parseColor("#3B82F6")),
                            makeLightLineDataSet(oilEntries,  "Oil",     AColor.parseColor("#F59E0B")),
                            makeLightLineDataSet(catEntries,  "Cat",     AColor.parseColor("#EF4444")),
                        )
                        chart.invalidate()
                    },
                    modifier = Modifier.fillMaxWidth().height(160.dp),
                )
            }
        }
        Spacer(Modifier.height(16.dp))
        InterpretationCard(
            title    = "Thermal Analysis",
            body     = "Coolant reaching 80°C in nominal time. Oil temp trailing by ~2–3 min — expected. Catalyst light-off >300°C confirmed. No thermal anomalies detected.",
            severity = InsightSeverity.OK,
        )
    }
}

// ── Voltage Content ───────────────────────────────────────────────────────────

@Composable
fun VoltageContent(data: List<VoltageDataPoint>) {
    Column(Modifier.padding(horizontal = 20.dp)) {
        val avgV = data.map { it.voltage }.average().toFloat()
        val minV = data.minOfOrNull { it.voltage } ?: 0f
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            StatSummaryCard(
                "Avg Voltage", "%.2fV".format(avgV),
                if (avgV < 13.0f) StatusRed else if (avgV < 13.5f) StatusAmber else StatusGreen,
                Modifier.weight(1f),
            )
            StatSummaryCard(
                "Min Voltage", "%.2fV".format(minV),
                if (minV < 13.0f) StatusRed else if (minV < 13.5f) StatusAmber else StatusGreen,
                Modifier.weight(1f),
            )
        }
        Spacer(Modifier.height(16.dp))
        ActyCard(modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("Charging Voltage", style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(8.dp))
                AndroidView(
                    factory = { ctx ->
                        buildMultiLineChart(ctx, yMin = 11f, yMax = 15.5f).also {
                            it.axisLeft.addLimitLine(
                                com.github.mikephil.charting.components.LimitLine(13.5f, "Warn").apply {
                                    lineColor = AColor.parseColor("#F59E0B")
                                    lineWidth = 1f
                                    textColor = AColor.parseColor("#F59E0B")
                                    textSize  = 9f
                                }
                            )
                        }
                    },
                    update  = { chart ->
                        val entries = data.mapIndexed { i, p -> Entry(i.toFloat(), p.voltage) }
                        chart.data  = LineData(makeLightLineDataSet(entries, "Voltage", AColor.parseColor("#3B82F6"), fill = true))
                        chart.invalidate()
                    },
                    modifier = Modifier.fillMaxWidth().height(160.dp),
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text  = "Normal: 13.8–14.5V  ·  Watch: <13.5V  ·  Action: <13.0V",
                    style = MaterialTheme.typography.labelSmall.copy(color = TextDim),
                )
            }
        }
    }
}

// ── MPG Content ───────────────────────────────────────────────────────────────

@Composable
fun MpgContent(data: List<MpgDataPoint>) {
    Column(Modifier.padding(horizontal = 20.dp)) {
        val avgMpg = data.map { it.mpg }.average().toFloat()
        val trend  = if (data.size >= 2 && data.last().mpg > data.first().mpg) "Improving" else "Declining"
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            StatSummaryCard("Avg MPG", "%.1f".format(avgMpg), StatusGreen, Modifier.weight(1f))
            StatSummaryCard("Trend", trend, if (trend == "Improving") StatusGreen else StatusAmber, Modifier.weight(1f))
        }
        Spacer(Modifier.height(16.dp))
        ActyCard(modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("MPG Over Time", style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(8.dp))
                AndroidView(
                    factory = { ctx -> buildMultiLineChart(ctx, yMin = 15f, yMax = 45f) },
                    update  = { chart ->
                        val entries = data.mapIndexed { i, p -> Entry(i.toFloat(), p.mpg) }
                        chart.data  = LineData(makeLightLineDataSet(entries, "MPG", AColor.parseColor("#10B981"), fill = true))
                        chart.invalidate()
                    },
                    modifier = Modifier.fillMaxWidth().height(160.dp),
                )
            }
        }
    }
}

// ── Anomalies Content ─────────────────────────────────────────────────────────

@Composable
fun AnomaliesContent() {
    Column(Modifier.padding(horizontal = 20.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            StatSummaryCard("Detected",  "${anomalyPoints.size}", StatusAmber,   Modifier.weight(1f))
            StatSummaryCard("Sessions",  "Last 7",                TextSecondary, Modifier.weight(1f))
        }
        Spacer(Modifier.height(16.dp))
        Text("Anomaly Timeline", style = MaterialTheme.typography.titleSmall.copy(color = TextSecondary))
        Spacer(Modifier.height(10.dp))
        anomalyPoints.forEach { (ts, label, sev) ->
            val color = when (sev) {
                InsightSeverity.CRITICAL -> StatusRed
                InsightSeverity.WARN     -> StatusAmber
                else                     -> TextDim
            }
            val bgColor = when (sev) {
                InsightSeverity.CRITICAL -> StatusRedBg
                InsightSeverity.WARN     -> StatusAmberBg
                else                     -> BgCardElevated
            }
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .shadow(3.dp, RoundedCornerShape(12.dp), spotColor = color.copy(alpha = 0.08f))
                    .clip(RoundedCornerShape(12.dp))
                    .background(bgColor)
                    .border(0.5.dp, color.copy(alpha = 0.25f), RoundedCornerShape(12.dp))
                    .padding(horizontal = 14.dp, vertical = 10.dp),
            ) {
                Row(
                    modifier          = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(
                        Modifier
                            .size(10.dp)
                            .clip(androidx.compose.foundation.shape.CircleShape)
                            .background(color)
                    )
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(label, style = MaterialTheme.typography.titleSmall.copy(color = TextPrimary))
                        Text("${ts}s into session", style = MaterialTheme.typography.labelSmall)
                    }
                    Text(
                        text  = if (sev == InsightSeverity.CRITICAL) "CRITICAL" else "WARN",
                        style = MaterialTheme.typography.labelSmall.copy(color = color),
                        modifier = Modifier
                            .clip(RoundedCornerShape(100.dp))
                            .background(color.copy(alpha = 0.10f))
                            .padding(horizontal = 8.dp, vertical = 3.dp),
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
        }
        Spacer(Modifier.height(8.dp))
        InterpretationCard(
            title    = "Isolation Forest Detection",
            body     = "3 anomalies detected across last 7 sessions. Isolation Forest (CPU ensemble, Tier 1) flagged lean LTFT spike and voltage dip. LSTM deep-dive pending for Tuesday's session.",
            severity = InsightSeverity.WARN,
        )
    }
}

// ── Shared sub-components ─────────────────────────────────────────────────────

@Composable
fun StatSummaryCard(label: String, value: String, color: Color, modifier: Modifier = Modifier) {
    ActyCard(modifier = modifier) {
        Column(Modifier.padding(14.dp)) {
            Text(label, style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(4.dp))
            Text(
                text  = value,
                style = MaterialTheme.typography.headlineSmall.copy(
                    color      = color,
                    fontWeight = FontWeight.Bold,
                ),
            )
        }
    }
}

@Composable
fun InterpretationCard(title: String, body: String, severity: InsightSeverity) {
    val (border, bg, tint) = when (severity) {
        InsightSeverity.OK       -> Triple(StatusGreenDim.copy(alpha = 0.3f), StatusGreenBg, StatusGreenDim)
        InsightSeverity.WARN     -> Triple(StatusAmber.copy(alpha = 0.3f),    StatusAmberBg, StatusAmber)
        InsightSeverity.CRITICAL -> Triple(StatusRed.copy(alpha = 0.35f),     StatusRedBg,   StatusRed)
        InsightSeverity.INFO     -> Triple(BgBorder, BgCardElevated,           TextSecondary)
    }
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .shadow(4.dp, RoundedCornerShape(14.dp), spotColor = tint.copy(alpha = 0.08f))
            .clip(RoundedCornerShape(14.dp))
            .background(bg)
            .border(0.5.dp, border, RoundedCornerShape(14.dp))
            .padding(16.dp),
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.AutoAwesome, null, tint = tint, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(6.dp))
                Text(title, style = MaterialTheme.typography.titleSmall.copy(color = tint))
            }
            Spacer(Modifier.height(6.dp))
            Text(body, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
fun LegendDot(color: Color, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier
                .size(8.dp)
                .clip(androidx.compose.foundation.shape.CircleShape)
                .background(color)
        )
        Spacer(Modifier.width(4.dp))
        Text(label, style = MaterialTheme.typography.labelSmall)
    }
}

// ── Chart helpers — light theme ───────────────────────────────────────────────

private fun buildMultiLineChart(
    ctx:  Context,
    yMin: Float = -20f,
    yMax: Float = 20f,
): LineChart {
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
            textColor    = AColor.argb(180, 71, 85, 105)   // slate-600 ~70%
            gridColor    = AColor.argb(30, 15, 23, 42)     // slate-900 ~12%
            axisMinimum  = yMin
            axisMaximum  = yMax
            setLabelCount(4, true)
            textSize     = 10f
        }
    }
}

private fun makeLightLineDataSet(
    entries: List<Entry>,
    label:   String,
    color:   Int,
    fill:    Boolean = false,
): LineDataSet {
    return LineDataSet(entries, label).apply {
        this.color = color
        setDrawCircles(false)
        lineWidth = 2.2f
        mode      = LineDataSet.Mode.CUBIC_BEZIER
        if (fill) {
            setDrawFilled(true)
            fillColor = color
            fillAlpha = 22
        }
        setDrawValues(false)
    }
}
