package com.acty.model

import androidx.compose.ui.graphics.Color

// ── Vehicle ───────────────────────────────────────────────────────────────────

data class Vehicle(
    val id: String,
    val make: String,
    val model: String,
    val year: Int,
    val vin: String? = null,
    val obdMac: String? = null,
    val odometer: Int? = null,
    val drivetrain: String = "Unknown",
    val isActive: Boolean = false,
)

// ── Health & Scoring ──────────────────────────────────────────────────────────

data class VehicleHealth(
    val overallScore: Int = 0,          // 0–100
    val efficiencyScore: Int = 0,
    val smoothnessScore: Int = 0,
    val thermalScore: Int = 0,
    val chargingScore: Int = 0,
    val lastUpdated: Long = 0L,
)

data class MpgStats(
    val city: Float? = null,
    val highway: Float? = null,
    val combined: Float? = null,
    val trend: MpgTrend = MpgTrend.STABLE,
)

enum class MpgTrend { IMPROVING, STABLE, DECLINING }

// ── Insights ──────────────────────────────────────────────────────────────────

enum class InsightSeverity { INFO, OK, WARN, CRITICAL }

data class Insight(
    val id: String,
    val title: String,
    val body: String,
    val severity: InsightSeverity = InsightSeverity.INFO,
    val category: String = "General",
    val sessionId: String? = null,
    val timestamp: Long = System.currentTimeMillis(),
    val actionLabel: String? = null,
)

// ── DTC / Alerts ──────────────────────────────────────────────────────────────

enum class DtcStatus { CONFIRMED, PENDING, CLEARED }

data class DtcAlert(
    val code: String,
    val description: String,
    val status: DtcStatus = DtcStatus.CONFIRMED,
    val timestamp: Long = System.currentTimeMillis(),
)

data class ServiceAlert(
    val id: String,
    val title: String,
    val detail: String,
    val urgency: InsightSeverity = InsightSeverity.INFO,
)

// ── Session Summary ───────────────────────────────────────────────────────────

data class SessionSummary(
    val sessionId: String,
    val displayDate: String,      // e.g. "2026-03-21 15:42"
    val fileName: String,
    val sizeKb: Double,
    val synced: Boolean,
    val syncFailed: Boolean = false,  // sync was attempted but failed → show NOT SYNCED badge
    val durationMinutes: Int = 0,
    val sampleCount: Int = 0,
    val vehicleId: String? = null,
)

// ── Analytics / NeedleNest ────────────────────────────────────────────────────

data class LtftDataPoint(
    val timestamp: Long,
    val stft: Float,
    val ltft: Float,
)

data class ThermalDataPoint(
    val timestamp: Long,
    val coolantC: Float,
    val oilC: Float?,
    val catalystC: Float?,
)

data class VoltageDataPoint(
    val timestamp: Long,
    val voltage: Float,
)

data class MpgDataPoint(
    val sessionDate: Long,
    val mpg: Float,
)

enum class NeedleNestTab(val label: String) {
    LTFT("LTFT"),
    THERMAL("Thermal"),
    VOLTAGE("Voltage"),
    MPG("MPG"),
    ANOMALIES("Anomalies"),
}

// ── Onboarding ────────────────────────────────────────────────────────────────

data class OnboardingState(
    val step: Int = 0,
    val username: String = "",
    val email: String = "",
    val password: String = "",
    val region: String = "",
    val vehicleMake: String = "",
    val vehicleModel: String = "",
    val vehicleYear: String = "",
    val drivetrain: String = "",
)

// ── Settings / Account ────────────────────────────────────────────────────────

enum class SyncFrequency(val label: String) {
    PER_DRIVE("Per Drive"),
    DAILY("Daily"),
    WEEKLY("Weekly"),
    MANUAL("Manual"),
}

enum class RetentionPolicy(val label: String) {
    DAYS_30("30 Days"),
    DAYS_90("90 Days"),
    ONE_YEAR("1 Year"),
    FOREVER("Forever"),
}

data class AccountSettings(
    val username: String = "",
    val email: String = "",
    val alertDtcEnabled: Boolean = true,
    val alertLtftEnabled: Boolean = true,
    val alertServiceEnabled: Boolean = true,
    val alertChargingEnabled: Boolean = true,
    val ltftAlertThreshold: Float = 7.5f,
    val syncFrequency: SyncFrequency = SyncFrequency.PER_DRIVE,
    val syncOnWifiOnly: Boolean = true,
    val retentionPolicy: RetentionPolicy = RetentionPolicy.DAYS_90,
    val emailReportsEnabled: Boolean = false,
    val byokApiKey: String = "",
    val byokProvider: String = "",
)

// ── Oil Change / Maintenance ──────────────────────────────────────────────────

enum class OilChangeUrgency { OK, MONITOR, DUE_SOON, OVERDUE }

/**
 * Mirrors the output of oil_interval_advisor.py status().
 * In production, populated from the backend after session ingestion.
 */
data class OilChangeStatus(
    val urgency:                  OilChangeUrgency = OilChangeUrgency.OK,
    val pctThresholdUsed:         Int              = 0,    // 0–100
    val equivMilesRemaining:      Int              = 5000, // equivalent severity-miles left
    val actualMilesSinceChange:   Int              = 0,    // odometer miles
    val impliedIntervalMi:        String           = "5,000–7,000 miles",
    val drivingProfile:           String           = "Mixed suburban driving",
    val avgSeverityMult:          Float            = 1.0f, // 1.0 = ideal highway
    val dominantFactor:           String           = "baseline",
    val recommendation:           String           = "",
)

// ── Sharing ───────────────────────────────────────────────────────────────────

data class MechanicLink(
    val sessionId: String,
    val url: String,
    val expiresAt: Long,
    val isReadOnly: Boolean = true,
)
