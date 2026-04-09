package com.acty.ui.screens

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
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.acty.model.*
import com.acty.ui.SessionViewModel
import com.acty.ui.theme.*
import kotlin.math.cos
import kotlin.math.sin

// ── Sample data (replace with real ViewModel data) ────────────────────────────

private val sampleVehicle = Vehicle(
    id         = "gr86",
    make       = "Toyota",
    model      = "GR86",
    year       = 2024,
    vin        = "JF1ZNBB19P9751720",
    drivetrain = "RWD",
    isActive   = true,
)

private val sampleHealth = VehicleHealth(
    overallScore    = 84,
    efficiencyScore = 78,
    smoothnessScore = 91,
    thermalScore    = 88,
    chargingScore   = 95,
)

private val sampleInsights = listOf(
    Insight(
        id          = "1",
        title       = "LTFT lean drift detected",
        body        = "Long-term fuel trim is running −6.8% warm. MAF sensor cleaning improved trend — smoke test still pending.",
        severity    = InsightSeverity.WARN,
        category    = "Fuel System",
        actionLabel = "View Details",
    ),
    Insight(
        id       = "2",
        title    = "Thermal warmup nominal",
        body     = "Coolant reached 80°C in 4.2 min. Oil temp trailing by 3.1 min — within expected range.",
        severity = InsightSeverity.OK,
        category = "Thermal",
    ),
    Insight(
        id          = "3",
        title       = "Timing retard cluster",
        body        = "8 idle retard events (−18° peak) observed. Possible EVAP purge or early carbon deposits.",
        severity    = InsightSeverity.WARN,
        category    = "Ignition",
        actionLabel = "Investigate",
    ),
)

private val sampleMpg  = MpgStats(city = 24.3f, highway = 31.8f, trend = MpgTrend.IMPROVING)
private val sampleDtcs = listOf(DtcAlert("P0304", "Cylinder 4 misfire", DtcStatus.PENDING))

// Mirrors oil_interval_advisor.py status() — populated from backend after session ingest
private val sampleOilStatus = OilChangeStatus(
    urgency                = OilChangeUrgency.MONITOR,
    pctThresholdUsed       = 68,
    equivMilesRemaining    = 1600,
    actualMilesSinceChange = 3200,
    impliedIntervalMi      = "5,000–7,000 miles",
    drivingProfile         = "City / stop-and-go — elevated oil stress",
    avgSeverityMult        = 1.9f,
    dominantFactor         = "cold starts",
    recommendation         = "Oil at ~68% of severity threshold. Primary factor: cold starts. ~1,600 equivalent miles remaining.",
)

// ── HomeScreen ────────────────────────────────────────────────────────────────

@Composable
fun HomeScreen(
    viewModel: SessionViewModel,
    onStartCapture: () -> Unit,
    onViewSessions: () -> Unit,
) {
    val sessionState by viewModel.state.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors    = listOf(CactusBluePale, Color(0xFFF8FAFC), Color(0xFFF8FAFC)),
                    startY    = 0f,
                    endY      = 900f,
                )
            )
            .verticalScroll(rememberScrollState())
            .systemBarsPadding()
            .padding(bottom = 16.dp),
    ) {
        // ── Header ──────────────────────────────────────────
        HomeHeader(vehicle = sampleVehicle, isConnected = sessionState.isRunning)

        // ── Hero stats strip ─────────────────────────────────
        HeroStatsStrip(health = sampleHealth, mpg = sampleMpg)

        Spacer(Modifier.height(20.dp))

        // ── Health score ring ────────────────────────────────
        HealthScoreCard(health = sampleHealth)

        Spacer(Modifier.height(16.dp))

        // ── Session score row ────────────────────────────────
        SessionScoreRow(health = sampleHealth)

        Spacer(Modifier.height(20.dp))

        // ── MPG strip ────────────────────────────────────────
        MpgCard(mpg = sampleMpg)

        Spacer(Modifier.height(20.dp))

        // ── Insights ─────────────────────────────────────────
        SectionHeader(title = "Insights", subtitle = "${sampleInsights.size + 1} active")
        Spacer(Modifier.height(10.dp))
        OilChangeInsightCard(oil = sampleOilStatus)
        Spacer(Modifier.height(8.dp))
        sampleInsights.forEach { insight ->
            InsightCard(insight = insight)
            Spacer(Modifier.height(8.dp))
        }

        Spacer(Modifier.height(20.dp))

        // ── Pending DTCs ──────────────────────────────────────
        if (sampleDtcs.isNotEmpty()) {
            SectionHeader(title = "Pending Issues", subtitle = "${sampleDtcs.size} code(s)")
            Spacer(Modifier.height(10.dp))
            sampleDtcs.forEach { dtc ->
                DtcCard(dtc = dtc)
                Spacer(Modifier.height(8.dp))
            }
            Spacer(Modifier.height(20.dp))
        }

        // ── Quick actions ─────────────────────────────────────
        SectionHeader(title = "Quick Actions")
        Spacer(Modifier.height(10.dp))
        QuickActionsRow(
            onStartCapture = onStartCapture,
            onViewSessions = onViewSessions,
        )

        Spacer(Modifier.height(24.dp))
    }
}

// ── Header ────────────────────────────────────────────────────────────────────

@Composable
fun HomeHeader(vehicle: Vehicle, isConnected: Boolean) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                Brush.verticalGradient(
                    listOf(CactusBlueLight.copy(alpha = 0.45f), Color.Transparent),
                    startY = 0f, endY = 220f,
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
                    text  = "Cactus Insights",
                    style = MaterialTheme.typography.headlineMedium.copy(
                        color         = CactusBlue,
                        fontWeight    = FontWeight.Black,
                        letterSpacing = (-0.5).sp,
                    ),
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text  = "${vehicle.year} ${vehicle.make} ${vehicle.model}",
                        style = MaterialTheme.typography.bodyMedium.copy(color = TextSecondary),
                    )
                    Spacer(Modifier.width(8.dp))
                    // Connection badge
                    Row(
                        modifier = Modifier
                            .clip(RoundedCornerShape(100.dp))
                            .background(if (isConnected) StatusGreenBg else BgCardElevated)
                            .border(
                                0.5.dp,
                                if (isConnected) StatusGreenDim.copy(alpha = 0.5f) else BgBorder,
                                RoundedCornerShape(100.dp),
                            )
                            .padding(horizontal = 8.dp, vertical = 2.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Box(
                            modifier = Modifier
                                .size(5.dp)
                                .clip(CircleShape)
                                .background(if (isConnected) StatusGreen else TextDim)
                        )
                        Spacer(Modifier.width(4.dp))
                        Text(
                            text  = if (isConnected) "Live" else "Offline",
                            style = MaterialTheme.typography.labelSmall.copy(
                                color = if (isConnected) StatusGreenDim else TextDim,
                            ),
                        )
                    }
                }
            }
            // OBD adapter icon
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .shadow(4.dp, CircleShape, spotColor = CactusBlue.copy(alpha = 0.12f))
                    .clip(CircleShape)
                    .background(Color.White)
                    .border(1.dp, BgBorder, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector        = Icons.Filled.BluetoothConnected,
                    contentDescription = "OBD Adapter",
                    tint               = if (isConnected) StatusGreen else TextDim,
                    modifier           = Modifier.size(20.dp),
                )
            }
        }
    }
}

// ── Hero Stats Strip ──────────────────────────────────────────────────────────

@Composable
fun HeroStatsStrip(health: VehicleHealth, mpg: MpgStats) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        HeroStatChip(
            label    = "Health",
            value    = "${health.overallScore}",
            unit     = "/100",
            color    = when {
                health.overallScore >= 85 -> StatusGreen
                health.overallScore >= 60 -> StatusAmber
                else                      -> StatusRed
            },
            modifier = Modifier.weight(1f),
        )
        HeroStatChip(
            label    = "City MPG",
            value    = "%.1f".format(mpg.city),
            unit     = "mpg",
            color    = CactusBlue,
            modifier = Modifier.weight(1f),
        )
        HeroStatChip(
            label    = "Hwy MPG",
            value    = "%.1f".format(mpg.highway),
            unit     = "mpg",
            color    = CactusBlueMid,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
fun HeroStatChip(
    label:    String,
    value:    String,
    unit:     String,
    color:    Color,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .shadow(6.dp, RoundedCornerShape(14.dp), spotColor = color.copy(alpha = 0.12f))
            .clip(RoundedCornerShape(14.dp))
            .background(Color.White)
            .border(0.5.dp, color.copy(alpha = 0.15f), RoundedCornerShape(14.dp))
            .padding(horizontal = 12.dp, vertical = 10.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text  = label,
            style = MaterialTheme.typography.labelSmall.copy(color = TextDim),
        )
        Spacer(Modifier.height(2.dp))
        Row(verticalAlignment = Alignment.Bottom) {
            Text(
                text  = value,
                style = MaterialTheme.typography.headlineSmall.copy(
                    color      = color,
                    fontWeight = FontWeight.Black,
                ),
            )
            Spacer(Modifier.width(2.dp))
            Text(
                text     = unit,
                style    = MaterialTheme.typography.labelSmall.copy(color = TextDim),
                modifier = Modifier.padding(bottom = 3.dp),
            )
        }
    }
}

// ── Health Score Ring ─────────────────────────────────────────────────────────

@Composable
fun HealthScoreCard(health: VehicleHealth) {
    val animProgress by animateFloatAsState(
        targetValue   = health.overallScore / 100f,
        animationSpec = tween(1200, easing = FastOutSlowInEasing),
        label         = "healthAnim",
    )

    val scoreColor = when {
        health.overallScore >= 85 -> StatusGreen
        health.overallScore >= 60 -> StatusAmber
        else                      -> StatusRed
    }

    ActyCard(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
    ) {
        Column(
            modifier            = Modifier.padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Row(
                modifier              = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment     = Alignment.CenterVertically,
            ) {
                Text(
                    text  = "Vehicle Health",
                    style = MaterialTheme.typography.titleMedium.copy(color = TextSecondary),
                )
                Text(
                    text  = "Last session",
                    style = MaterialTheme.typography.labelSmall,
                )
            }

            Spacer(Modifier.height(24.dp))

            Box(contentAlignment = Alignment.Center) {
                Canvas(modifier = Modifier.size(160.dp)) {
                    val sweep       = animProgress * 270f
                    val startAngle  = 135f
                    val strokeWidth = 16.dp.toPx()
                    val inset       = strokeWidth / 2
                    val arcSize     = androidx.compose.ui.geometry.Size(
                        size.width - strokeWidth, size.height - strokeWidth
                    )

                    // Track (light gray on white)
                    drawArc(
                        color      = Color(0xFFE2E8F0),
                        startAngle = startAngle,
                        sweepAngle = 270f,
                        useCenter  = false,
                        style      = Stroke(strokeWidth, cap = StrokeCap.Round),
                        topLeft    = Offset(inset, inset),
                        size       = arcSize,
                    )
                    // Progress arc
                    drawArc(
                        brush      = Brush.sweepGradient(
                            listOf(scoreColor.copy(alpha = 0.5f), scoreColor),
                            center = Offset(size.width / 2, size.height / 2),
                        ),
                        startAngle = startAngle,
                        sweepAngle = sweep,
                        useCenter  = false,
                        style      = Stroke(strokeWidth, cap = StrokeCap.Round),
                        topLeft    = Offset(inset, inset),
                        size       = arcSize,
                    )
                }

                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        text  = "${health.overallScore}",
                        style = MaterialTheme.typography.displayMedium.copy(
                            color      = scoreColor,
                            fontWeight = FontWeight.Black,
                        ),
                    )
                    Text(
                        text  = "/100",
                        style = MaterialTheme.typography.bodySmall.copy(color = TextDim),
                    )
                }
            }

            Spacer(Modifier.height(16.dp))

            val label = when {
                health.overallScore >= 85 -> "Excellent"
                health.overallScore >= 70 -> "Good"
                health.overallScore >= 50 -> "Fair"
                else                      -> "Needs Attention"
            }
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(100.dp))
                    .background(scoreColor.copy(alpha = 0.10f))
                    .border(0.5.dp, scoreColor.copy(alpha = 0.35f), RoundedCornerShape(100.dp))
                    .padding(horizontal = 16.dp, vertical = 6.dp),
            ) {
                Text(
                    text  = label,
                    style = MaterialTheme.typography.labelLarge.copy(color = scoreColor),
                )
            }
        }
    }
}

// ── Session Score Row ─────────────────────────────────────────────────────────

@Composable
fun SessionScoreRow(health: VehicleHealth) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        MiniScoreCard(
            label    = "Efficiency",
            score    = health.efficiencyScore,
            icon     = Icons.Outlined.LocalGasStation,
            modifier = Modifier.weight(1f),
        )
        MiniScoreCard(
            label    = "Smoothness",
            score    = health.smoothnessScore,
            icon     = Icons.Outlined.Timeline,
            modifier = Modifier.weight(1f),
        )
        MiniScoreCard(
            label    = "Thermal",
            score    = health.thermalScore,
            icon     = Icons.Outlined.Thermostat,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
fun MiniScoreCard(label: String, score: Int, icon: ImageVector, modifier: Modifier = Modifier) {
    val color = when {
        score >= 85 -> StatusGreen
        score >= 60 -> StatusAmber
        else        -> StatusRed
    }
    ActyCard(modifier = modifier) {
        Column(
            modifier            = Modifier.padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape)
                    .background(color.copy(alpha = 0.10f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector        = icon,
                    contentDescription = label,
                    tint               = color,
                    modifier           = Modifier.size(16.dp),
                )
            }
            Text(
                text  = "$score",
                style = MaterialTheme.typography.headlineSmall.copy(
                    color      = color,
                    fontWeight = FontWeight.Bold,
                ),
            )
            Text(
                text     = label,
                style    = MaterialTheme.typography.labelSmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

// ── MPG Card ──────────────────────────────────────────────────────────────────

@Composable
fun MpgCard(mpg: MpgStats) {
    ActyCard(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(CactusBluePale),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector        = Icons.Outlined.LocalGasStation,
                    contentDescription = null,
                    tint               = CactusBlue,
                    modifier           = Modifier.size(20.dp),
                )
            }
            Spacer(Modifier.width(14.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text  = "Fuel Economy",
                    style = MaterialTheme.typography.titleSmall.copy(color = TextSecondary),
                )
                Row(
                    horizontalArrangement = Arrangement.spacedBy(20.dp),
                    modifier              = Modifier.padding(top = 4.dp),
                ) {
                    MpgStat(label = "City",    value = mpg.city)
                    MpgStat(label = "Highway", value = mpg.highway)
                }
            }
            val (trendIcon, trendColor) = when (mpg.trend) {
                MpgTrend.IMPROVING -> Icons.Filled.TrendingUp   to StatusGreen
                MpgTrend.DECLINING -> Icons.Filled.TrendingDown to StatusRed
                MpgTrend.STABLE    -> Icons.Filled.TrendingFlat to TextDim
            }
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .background(trendColor.copy(alpha = 0.08f))
                    .padding(6.dp),
            ) {
                Icon(
                    imageVector        = trendIcon,
                    contentDescription = "trend",
                    tint               = trendColor,
                    modifier           = Modifier.size(20.dp),
                )
            }
        }
    }
}

@Composable
fun MpgStat(label: String, value: Float?) {
    Column {
        Text(label, style = MaterialTheme.typography.labelSmall)
        Text(
            text  = if (value != null) "%.1f".format(value) else "—",
            style = MaterialTheme.typography.headlineSmall.copy(
                color      = TextPrimary,
                fontWeight = FontWeight.Bold,
            ),
        )
    }
}

// ── Insight Card ──────────────────────────────────────────────────────────────

@Composable
fun InsightCard(insight: Insight) {
    val (borderColor, bgColor, chipColor) = when (insight.severity) {
        InsightSeverity.OK       -> Triple(StatusGreenDim.copy(alpha = 0.3f), StatusGreenBg, StatusGreen)
        InsightSeverity.WARN     -> Triple(StatusAmber.copy(alpha = 0.35f),   StatusAmberBg, StatusAmber)
        InsightSeverity.CRITICAL -> Triple(StatusRed.copy(alpha = 0.4f),      StatusRedBg,   StatusRed)
        InsightSeverity.INFO     -> Triple(BgBorder, BgCardElevated,           TextSecondary)
    }
    val icon = when (insight.severity) {
        InsightSeverity.OK       -> Icons.Filled.CheckCircle
        InsightSeverity.WARN     -> Icons.Filled.Warning
        InsightSeverity.CRITICAL -> Icons.Filled.Error
        InsightSeverity.INFO     -> Icons.Outlined.Info
    }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .shadow(4.dp, RoundedCornerShape(14.dp), spotColor = chipColor.copy(alpha = 0.10f))
            .clip(RoundedCornerShape(14.dp))
            .background(bgColor)
            .border(0.5.dp, borderColor, RoundedCornerShape(14.dp))
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.Top) {
            Icon(
                imageVector        = icon,
                contentDescription = null,
                tint               = chipColor,
                modifier           = Modifier.size(20.dp),
            )
            Spacer(Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier              = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment     = Alignment.CenterVertically,
                ) {
                    Text(
                        text     = insight.title,
                        style    = MaterialTheme.typography.titleMedium.copy(color = TextPrimary),
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f),
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text  = insight.category,
                        style = MaterialTheme.typography.labelSmall.copy(color = chipColor),
                        modifier = Modifier
                            .clip(RoundedCornerShape(100.dp))
                            .background(chipColor.copy(alpha = 0.10f))
                            .padding(horizontal = 8.dp, vertical = 2.dp),
                    )
                }
                Spacer(Modifier.height(6.dp))
                Text(
                    text     = insight.body,
                    style    = MaterialTheme.typography.bodySmall,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis,
                )
                if (insight.actionLabel != null) {
                    Spacer(Modifier.height(10.dp))
                    Text(
                        text  = insight.actionLabel,
                        style = MaterialTheme.typography.labelMedium.copy(
                            color      = chipColor,
                            fontWeight = FontWeight.SemiBold,
                        ),
                        modifier = Modifier
                            .clip(RoundedCornerShape(100.dp))
                            .background(chipColor.copy(alpha = 0.10f))
                            .padding(horizontal = 12.dp, vertical = 5.dp),
                    )
                }
            }
        }
    }
}

// ── Oil Change Insight Card ───────────────────────────────────────────────────

@Composable
fun OilChangeInsightCard(oil: OilChangeStatus) {
    val (accentColor, bgColor, borderColor, badgeLabel) = when (oil.urgency) {
        OilChangeUrgency.OVERDUE   -> listOf(StatusRed,   StatusRedBg,   StatusRed.copy(alpha = 0.3f),   "Overdue")
        OilChangeUrgency.DUE_SOON  -> listOf(StatusRed,   StatusRedBg,   StatusRed.copy(alpha = 0.3f),   "Due Soon")
        OilChangeUrgency.MONITOR   -> listOf(StatusAmber, StatusAmberBg, StatusAmber.copy(alpha = 0.3f), "Monitor")
        OilChangeUrgency.OK        -> listOf(StatusGreen, StatusGreenBg, StatusGreenDim.copy(alpha = 0.3f), "Good")
    }
    @Suppress("UNCHECKED_CAST")
    val accent  = accentColor  as Color
    val bg      = bgColor      as Color
    val border  = borderColor  as Color
    val badge   = badgeLabel   as String

    val animPct by animateFloatAsState(
        targetValue   = oil.pctThresholdUsed / 100f,
        animationSpec = tween(900, easing = FastOutSlowInEasing),
        label         = "oilPct",
    )

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .shadow(4.dp, RoundedCornerShape(14.dp), spotColor = accent.copy(alpha = 0.10f))
            .clip(RoundedCornerShape(14.dp))
            .background(bg)
            .border(0.5.dp, border, RoundedCornerShape(14.dp))
            .padding(16.dp),
    ) {
        Column {
            // Header row
            Row(
                modifier              = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment     = Alignment.CenterVertically,
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(RoundedCornerShape(10.dp))
                            .background(accent.copy(alpha = 0.12f)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(
                            imageVector        = Icons.Outlined.OilBarrel,
                            contentDescription = "Oil Change",
                            tint               = accent,
                            modifier           = Modifier.size(18.dp),
                        )
                    }
                    Spacer(Modifier.width(10.dp))
                    Column {
                        Text(
                            text  = "Oil Change Estimate",
                            style = MaterialTheme.typography.titleMedium.copy(
                                color      = TextPrimary,
                                fontWeight = FontWeight.Bold,
                            ),
                        )
                        Text(
                            text  = "Severity-weighted · actual PID data",
                            style = MaterialTheme.typography.labelSmall.copy(color = TextDim),
                        )
                    }
                }
                Text(
                    text  = badge,
                    style = MaterialTheme.typography.labelSmall.copy(
                        color      = accent,
                        fontWeight = FontWeight.Bold,
                    ),
                    modifier = Modifier
                        .clip(RoundedCornerShape(100.dp))
                        .background(accent.copy(alpha = 0.12f))
                        .border(0.5.dp, accent.copy(alpha = 0.35f), RoundedCornerShape(100.dp))
                        .padding(horizontal = 10.dp, vertical = 4.dp),
                )
            }

            Spacer(Modifier.height(14.dp))

            // Progress bar
            Row(
                modifier              = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text  = "Oil Life Used",
                    style = MaterialTheme.typography.labelSmall.copy(color = TextSecondary),
                )
                Text(
                    text  = "${oil.pctThresholdUsed}%",
                    style = MaterialTheme.typography.labelSmall.copy(
                        color      = accent,
                        fontWeight = FontWeight.Bold,
                    ),
                )
            }
            Spacer(Modifier.height(6.dp))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(7.dp)
                    .clip(RoundedCornerShape(100.dp))
                    .background(Color(0xFFE2E8F0)),
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth(animPct)
                        .fillMaxHeight()
                        .clip(RoundedCornerShape(100.dp))
                        .background(
                            Brush.horizontalGradient(
                                listOf(accent.copy(alpha = 0.6f), accent)
                            )
                        ),
                )
            }

            Spacer(Modifier.height(12.dp))

            // Stats grid
            Row(
                modifier              = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                listOf(
                    "Since change" to "${oil.actualMilesSinceChange.toLocaleString()} mi",
                    "Est. remaining" to "${oil.equivMilesRemaining.toLocaleString()} eq. mi",
                ).forEach { (label, value) ->
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(8.dp))
                            .background(Color.White.copy(alpha = 0.65f))
                            .padding(horizontal = 10.dp, vertical = 7.dp),
                    ) {
                        Text(label, style = MaterialTheme.typography.labelSmall.copy(color = TextDim))
                        Spacer(Modifier.height(2.dp))
                        Text(value, style = MaterialTheme.typography.labelMedium.copy(
                            color      = TextPrimary,
                            fontWeight = FontWeight.Bold,
                        ))
                    }
                }
            }

            Spacer(Modifier.height(8.dp))

            Row(
                modifier              = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                listOf(
                    "Severity" to "${oil.avgSeverityMult}× vs. ideal",
                    "Top factor" to oil.dominantFactor,
                ).forEach { (label, value) ->
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(8.dp))
                            .background(Color.White.copy(alpha = 0.65f))
                            .padding(horizontal = 10.dp, vertical = 7.dp),
                    ) {
                        Text(label, style = MaterialTheme.typography.labelSmall.copy(color = TextDim))
                        Spacer(Modifier.height(2.dp))
                        Text(value, style = MaterialTheme.typography.labelMedium.copy(
                            color      = TextPrimary,
                            fontWeight = FontWeight.Bold,
                        ))
                    }
                }
            }

            Spacer(Modifier.height(10.dp))

            // Implied interval footer
            Text(
                text  = "Implied interval for your driving style: ${oil.impliedIntervalMi}",
                style = MaterialTheme.typography.bodySmall.copy(color = TextSecondary),
            )
        }
    }
}

// Helper — Int.toLocaleString for Kotlin (no java.text dependency needed)
private fun Int.toLocaleString(): String {
    val s = this.toString()
    return buildString {
        s.forEachIndexed { i, c ->
            if (i > 0 && (s.length - i) % 3 == 0) append(',')
            append(c)
        }
    }
}

// ── DTC Card ─────────────────────────────────────────────────────────────────

@Composable
fun DtcCard(dtc: DtcAlert) {
    val (borderColor, statusLabel, labelColor) = when (dtc.status) {
        DtcStatus.CONFIRMED -> Triple(StatusRed.copy(alpha = 0.3f),   "CONFIRMED", StatusRed)
        DtcStatus.PENDING   -> Triple(StatusAmber.copy(alpha = 0.3f), "PENDING",   StatusAmber)
        DtcStatus.CLEARED   -> Triple(BgBorder,                       "CLEARED",   TextDim)
    }
    val bgColor = when (dtc.status) {
        DtcStatus.CONFIRMED -> StatusRedBg
        DtcStatus.PENDING   -> StatusAmberBg
        DtcStatus.CLEARED   -> BgCardElevated
    }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .shadow(4.dp, RoundedCornerShape(14.dp), spotColor = labelColor.copy(alpha = 0.08f))
            .clip(RoundedCornerShape(14.dp))
            .background(bgColor)
            .border(0.5.dp, borderColor, RoundedCornerShape(14.dp))
            .padding(horizontal = 16.dp, vertical = 12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(labelColor.copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector        = Icons.Outlined.Warning,
                    contentDescription = null,
                    tint               = labelColor,
                    modifier           = Modifier.size(18.dp),
                )
            }
            Spacer(Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text  = dtc.code,
                        style = MaterialTheme.typography.titleMedium.copy(
                            color      = TextPrimary,
                            fontWeight = FontWeight.Bold,
                        ),
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text  = statusLabel,
                        style = MaterialTheme.typography.labelSmall.copy(color = labelColor),
                        modifier = Modifier
                            .clip(RoundedCornerShape(100.dp))
                            .background(labelColor.copy(alpha = 0.10f))
                            .padding(horizontal = 8.dp, vertical = 2.dp),
                    )
                }
                Text(
                    text  = dtc.description,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Icon(
                imageVector        = Icons.Filled.ChevronRight,
                contentDescription = null,
                tint               = TextDim,
                modifier           = Modifier.size(18.dp),
            )
        }
    }
}

// ── Quick Actions ─────────────────────────────────────────────────────────────

@Composable
fun QuickActionsRow(onStartCapture: () -> Unit, onViewSessions: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Start Capture — primary CTA (blue gradient)
        Box(
            modifier = Modifier
                .weight(1f)
                .shadow(8.dp, RoundedCornerShape(16.dp), spotColor = CactusBlue.copy(alpha = 0.25f))
                .clip(RoundedCornerShape(16.dp))
                .background(Brush.linearGradient(listOf(CactusBlue, CactusBlueMid)))
                .clickable(onClick = onStartCapture)
                .padding(vertical = 18.dp),
            contentAlignment = Alignment.Center,
        ) {
            Row(
                verticalAlignment     = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(Icons.Filled.FiberManualRecord, null, tint = Color.White, modifier = Modifier.size(16.dp))
                Text(
                    text  = "Capture",
                    style = MaterialTheme.typography.titleSmall.copy(
                        color      = Color.White,
                        fontWeight = FontWeight.Bold,
                    ),
                )
            }
        }

        // View Sessions — secondary
        Box(
            modifier = Modifier
                .weight(1f)
                .shadow(4.dp, RoundedCornerShape(16.dp), spotColor = Color.Black.copy(alpha = 0.05f))
                .clip(RoundedCornerShape(16.dp))
                .background(Color.White)
                .border(1.dp, BgBorder, RoundedCornerShape(16.dp))
                .clickable(onClick = onViewSessions)
                .padding(vertical = 18.dp),
            contentAlignment = Alignment.Center,
        ) {
            Row(
                verticalAlignment     = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(Icons.Outlined.ListAlt, null, tint = TextSecondary, modifier = Modifier.size(16.dp))
                Text(
                    text  = "Sessions",
                    style = MaterialTheme.typography.titleSmall.copy(color = TextSecondary),
                )
            }
        }
    }
}

// ── Shared Components ─────────────────────────────────────────────────────────

@Composable
fun SectionHeader(title: String, subtitle: String? = null, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment     = Alignment.Bottom,
    ) {
        Text(
            text  = title,
            style = MaterialTheme.typography.headlineSmall.copy(
                fontWeight = FontWeight.Bold,
                color      = TextPrimary,
            ),
        )
        if (subtitle != null) {
            Text(
                text  = subtitle,
                style = MaterialTheme.typography.bodySmall.copy(color = CactusBlue),
            )
        }
    }
}

@Composable
fun ActyCard(
    modifier: Modifier = Modifier,
    content:  @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier = modifier
            .shadow(
                elevation     = 8.dp,
                shape         = RoundedCornerShape(18.dp),
                spotColor     = CactusBlue.copy(alpha = 0.07f),
                ambientColor  = Color.Black.copy(alpha = 0.03f),
            )
            .clip(RoundedCornerShape(18.dp))
            .background(Color(0xF2FFFFFF))  // white 95% — subtle glass
            .border(0.5.dp, Color(0xFFE2E8F0), RoundedCornerShape(18.dp)),
        content = content,
    )
}
