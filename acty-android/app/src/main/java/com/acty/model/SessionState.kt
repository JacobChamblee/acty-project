package com.acty.model

/**
 * Shared data models for session state and PID readings.
 */

data class PidReading(
    val name: String,
    val value: Double?,
    val unit: String
)

data class SessionState(
    val sessionId: String? = null,
    val isRunning: Boolean = false,
    val vin: String? = null,
    val vehicleName: String? = null,
    val elapsedSeconds: Long = 0L,
    val sampleCount: Int = 0,
    val pidReadings: Map<String, PidReading> = emptyMap(),
    val rpmHistory: List<Float> = emptyList(),  // last N RPM values for chart
    val csvPath: String? = null,
    val statusMessage: String = "Ready"
)

sealed class SessionEvent {
    object Started : SessionEvent()
    object Stopped : SessionEvent()
    data class Error(val message: String) : SessionEvent()
    data class SyncStarted(val fileName: String) : SessionEvent()
    data class SyncComplete(val fileName: String) : SessionEvent()
    data class SyncFailed(val fileName: String, val reason: String) : SessionEvent()
}
