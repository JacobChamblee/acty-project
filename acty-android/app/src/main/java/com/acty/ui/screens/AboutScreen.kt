package com.acty.ui.screens

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.acty.ui.theme.*

// ── AboutScreen ───────────────────────────────────────────────────────────────

@Composable
fun AboutScreen(onBack: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BgDeep)
            .verticalScroll(rememberScrollState())
            .systemBarsPadding()
            .padding(bottom = 32.dp),
    ) {
        // ── Header with back ─────────────────────────────────
        AboutHeader(onBack = onBack)

        Spacer(Modifier.height(20.dp))

        // ── Mission statement ────────────────────────────────
        MissionCard()

        Spacer(Modifier.height(20.dp))

        // ── Security features ────────────────────────────────
        SectionHeader(title = "Security Architecture")
        Spacer(Modifier.height(10.dp))
        SecurityCard()

        Spacer(Modifier.height(20.dp))

        // ── ML Pipeline ──────────────────────────────────────
        SectionHeader(title = "ML Diagnostic Pipeline")
        Spacer(Modifier.height(10.dp))
        MlPipelineCard()

        Spacer(Modifier.height(20.dp))

        // ── Data commitment ──────────────────────────────────
        DataCommitmentCard()

        Spacer(Modifier.height(20.dp))

        // ── Footer ───────────────────────────────────────────
        AboutFooter()
    }
}

// ── About Header ──────────────────────────────────────────────────────────────

@Composable
fun AboutHeader(onBack: () -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                Brush.verticalGradient(
                    listOf(ActyRedContainer.copy(alpha = 0.6f), Color.Transparent)
                )
            )
            .padding(horizontal = 20.dp, vertical = 20.dp),
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack, modifier = Modifier.size(32.dp)) {
                    Icon(Icons.Filled.ArrowBack, "Back", tint = TextSecondary)
                }
                Spacer(Modifier.width(8.dp))
                Text(
                    text  = "About Cactus",
                    style = MaterialTheme.typography.headlineMedium.copy(fontWeight = FontWeight.Black),
                )
            }
            Spacer(Modifier.height(16.dp))

            // Cactus branding
            Box(
                modifier = Modifier.fillMaxWidth(),
                contentAlignment = Alignment.Center,
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    // Cactus logo placeholder — styled text since vector is embedded in launcher
                    Box(
                        modifier = Modifier
                            .size(80.dp)
                            .clip(RoundedCornerShape(24.dp))
                            .background(
                                Brush.radialGradient(
                                    listOf(ActyRedContainer, BgDeep)
                                )
                            )
                            .border(1.dp, ActyRed.copy(alpha = 0.4f), RoundedCornerShape(24.dp)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text("🌵", fontSize = 40.sp)
                    }
                    Spacer(Modifier.height(12.dp))
                    Text(
                        text  = "Cactus",
                        style = MaterialTheme.typography.displaySmall.copy(
                            fontWeight = FontWeight.Black,
                            color      = TextPrimary,
                        ),
                    )
                    Text(
                        text  = "by Acty Labs",
                        style = MaterialTheme.typography.bodyMedium.copy(color = TextSecondary),
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(
                        text  = "Continuous Automotive Condition & Telemetry Unified System",
                        style = MaterialTheme.typography.bodySmall.copy(
                            color     = TextDim,
                            textAlign = TextAlign.Center,
                        ),
                        textAlign = TextAlign.Center,
                    )
                }
            }
        }
    }
}

// ── Mission Card ──────────────────────────────────────────────────────────────

@Composable
fun MissionCard() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .clip(RoundedCornerShape(18.dp))
            .background(
                Brush.linearGradient(
                    listOf(ActyRedContainer.copy(alpha = 0.8f), BgCard)
                )
            )
            .border(0.5.dp, ActyRed.copy(alpha = 0.3f), RoundedCornerShape(18.dp))
            .padding(20.dp),
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Shield, null, tint = ActyRed, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text("Our Mission", style = MaterialTheme.typography.titleLarge.copy(color = ActyRed))
            }
            Spacer(Modifier.height(12.dp))
            Text(
                text  = "Your car data belongs to you — not advertisers, data brokers, or insurance companies.",
                style = MaterialTheme.typography.bodyLarge.copy(color = TextPrimary, fontWeight = FontWeight.Medium),
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text  = "Acty captures, signs, and stores OBD-II telemetry with owner-generated cryptographic keys. " +
                        "Every record is hash-chained and Ed25519-signed at the point of capture. We can't read your data. " +
                        "We don't sell it. We never will — it's architecturally impossible.",
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

// ── Security Card ─────────────────────────────────────────────────────────────

@Composable
fun SecurityCard() {
    ActyCard(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
    ) {
        Column(Modifier.padding(20.dp)) {
            SecurityFeature(
                icon    = Icons.Outlined.Lock,
                title   = "AES-256-GCM Encryption",
                body    = "All session data encrypted with owner-generated key before leaving device.",
                color   = AccentCyan,
            )
            FeatureDivider()
            SecurityFeature(
                icon    = Icons.Outlined.Verified,
                title   = "Ed25519 Signing",
                body    = "Per-record cryptographic signature using ATECC608B hardware secure element. Private key never exported.",
                color   = StatusGreen,
            )
            FeatureDivider()
            SecurityFeature(
                icon    = Icons.Outlined.Link,
                title   = "Hash-Chain Integrity",
                body    = "SHA256(seq + timestamp + PIDs + prev_hash) per record. Tampering breaks the chain.",
                color   = StatusAmber,
            )
            FeatureDivider()
            SecurityFeature(
                icon    = Icons.Outlined.Schedule,
                title   = "RFC 3161 Timestamping",
                body    = "DigiCert TSA anchor provides court-admissible timestamps on session manifests.",
                color   = AccentPurple,
            )
            FeatureDivider()
            SecurityFeature(
                icon    = Icons.Outlined.AccountTree,
                title   = "Merkle Root Verification",
                body    = "Session manifest = Merkle root of all record hashes, signed at session end. Verify at verify.acty-labs.com",
                color   = StatusBlue,
            )
        }
    }
}

@Composable
fun SecurityFeature(icon: ImageVector, title: String, body: String, color: Color) {
    Row(Modifier.padding(vertical = 8.dp)) {
        Box(
            modifier = Modifier
                .size(36.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(color.copy(alpha = 0.12f)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(icon, null, tint = color, modifier = Modifier.size(18.dp))
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleSmall.copy(color = TextPrimary, fontWeight = FontWeight.SemiBold))
            Text(body, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
fun FeatureDivider() {
    HorizontalDivider(
        modifier  = Modifier.padding(vertical = 2.dp),
        color     = BgBorder,
        thickness = 0.5.dp,
    )
}

// ── ML Pipeline Card ──────────────────────────────────────────────────────────

@Composable
fun MlPipelineCard() {
    ActyCard(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
    ) {
        Column(Modifier.padding(20.dp)) {
            Text(
                text  = "Six-stage diagnostic pipeline",
                style = MaterialTheme.typography.bodySmall.copy(color = TextSecondary),
            )
            Spacer(Modifier.height(16.dp))

            val stages = listOf(
                Triple("Isolation Forest", "CPU sync · <2s", StatusGreen),
                Triple("LSTM Autoencoder / TFT", "GPU async · temporal anomaly", AccentCyan),
                Triple("XGBoost / Random Forest", "CPU sync · predictive maintenance", StatusAmber),
                Triple("RAG + FSM", "GPU embedding · FSM-grounded AI", AccentPurple),
                Triple("Federated Learning", "Flower · ε≤1.0 differential privacy", StatusBlue),
                Triple("Ed25519 Report Signing", "YubiHSM/ATECC608B · tamper-evident", StatusGreen),
            )

            stages.forEachIndexed { i, (title, subtitle, color) ->
                PipelineStep(
                    step     = i + 1,
                    title    = title,
                    subtitle = subtitle,
                    color    = color,
                    isLast   = i == stages.size - 1,
                )
            }
        }
    }
}

@Composable
fun PipelineStep(step: Int, title: String, subtitle: String, color: Color, isLast: Boolean) {
    Row {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Box(
                modifier = Modifier
                    .size(28.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(color.copy(alpha = 0.15f))
                    .border(0.5.dp, color.copy(alpha = 0.4f), RoundedCornerShape(8.dp)),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text  = "$step",
                    style = MaterialTheme.typography.labelLarge.copy(color = color, fontWeight = FontWeight.Bold),
                )
            }
            if (!isLast) {
                Box(
                    modifier = Modifier
                        .width(1.dp)
                        .height(24.dp)
                        .background(BgBorder)
                )
            }
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.padding(bottom = if (!isLast) 24.dp else 0.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall.copy(color = TextPrimary))
            Text(subtitle, style = MaterialTheme.typography.labelSmall.copy(color = color))
        }
    }
}

// ── Data Commitment Card ──────────────────────────────────────────────────────

@Composable
fun DataCommitmentCard() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .clip(RoundedCornerShape(18.dp))
            .background(StatusGreenBg)
            .border(0.5.dp, StatusGreenDim, RoundedCornerShape(18.dp))
            .padding(20.dp),
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.Handshake, null, tint = StatusGreen, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text("Our Commitments", style = MaterialTheme.typography.titleMedium.copy(color = StatusGreen))
            }
            Spacer(Modifier.height(12.dp))
            listOf(
                "No data brokerage — ever",
                "No VC funding — no investor pressure to monetize data",
                "Owner-encrypted — we cannot decrypt your sessions",
                "Bootstrapped by conviction — privacy is the product",
                "Court-admissible reports via hash-chain + RFC 3161",
                "Provisional patent pending on cryptographic chain",
            ).forEach { item ->
                Row(Modifier.padding(vertical = 3.dp), verticalAlignment = Alignment.Top) {
                    Icon(Icons.Filled.Check, null, tint = StatusGreen, modifier = Modifier.size(14.dp).padding(top = 1.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(item, style = MaterialTheme.typography.bodySmall.copy(color = TextPrimary))
                }
            }
        }
    }
}

// ── About Footer ──────────────────────────────────────────────────────────────

@Composable
fun AboutFooter() {
    Column(
        modifier            = Modifier.fillMaxWidth().padding(horizontal = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text("Cactus v0.1.0", style = MaterialTheme.typography.bodySmall.copy(color = TextDim))
        Text("© 2026 Acty Labs — JacobChamblee/acty-project", style = MaterialTheme.typography.labelSmall.copy(color = TextDim))
        Text("acty-labs.com", style = MaterialTheme.typography.labelSmall.copy(color = AccentCyan))
    }
}
