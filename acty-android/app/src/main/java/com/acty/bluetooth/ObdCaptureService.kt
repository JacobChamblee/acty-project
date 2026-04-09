package com.acty.bluetooth

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Binder
import android.os.IBinder
import android.util.Log
import androidx.annotation.RequiresPermission
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import com.acty.R
import com.acty.ActyConfig
import com.acty.data.CsvWriter
import com.acty.data.SessionSigner
import com.acty.data.SyncManager
import com.acty.model.PidReading
import com.acty.model.SessionEvent
import com.acty.model.SessionState
import com.acty.ui.MainActivity
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import java.io.File
import java.io.IOException
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.UUID
import kotlin.coroutines.coroutineContext

/**
 * ObdCaptureService.kt
 * Foreground service that manages the Bluetooth RFCOMM connection,
 * ELM327 command layer, PID poll loop, CSV writing, and WiFi sync trigger.
 * Keeps running with screen off during a drive session.
 */
class ObdCaptureService : Service() {

    companion object {
        private const val TAG = "ObdCaptureService"
        private const val NOTIF_CHANNEL = "acty_capture"
        private const val NOTIF_ID = 1001
        private const val RPM_HISTORY_SIZE = 60   // 60 seconds of RPM for chart
        // VeePeak OBDCheck BLE — classic BT SPP UUID
        private val SPP_UUID: UUID = UUID.fromString(ActyConfig.BT_UUID)

        // Intent actions for binding commands
        const val ACTION_START = "com.acty.START_CAPTURE"
        const val ACTION_STOP  = "com.acty.STOP_CAPTURE"
    }

    // ── Binder for UI binding ─────────────────────────────────────────────

    inner class LocalBinder : Binder() {
        fun getService() = this@ObdCaptureService
    }
    private val binder = LocalBinder()
    override fun onBind(intent: Intent): IBinder = binder

    // ── State / event flows ───────────────────────────────────────────────

    private val _state = MutableStateFlow(SessionState())
    val state = _state.asStateFlow()

    private val _events = MutableSharedFlow<SessionEvent>(extraBufferCapacity = 8)
    val events = _events.asSharedFlow()

    // ── Internals ─────────────────────────────────────────────────────────

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var captureJob: Job? = null
    private var socket: BluetoothSocket? = null
    private lateinit var csvWriter: CsvWriter
    private lateinit var syncManager: SyncManager
    private val sessionSigner by lazy { SessionSigner(this) }
    private val rpmHistory = ArrayDeque<Float>(RPM_HISTORY_SIZE)

    private var sessionId: String = UUID.randomUUID().toString()
    private var vehicleId: String = "unknown_vehicle"

    override fun onCreate() {
        super.onCreate()
        csvWriter = CsvWriter(this)
        syncManager = SyncManager(this)
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                val address = intent.getStringExtra("address") ?: run {
                    serviceScope.launch {
                        _events.emit(SessionEvent.Error(
                            "No OBD adapter configured. Go to Account → My Vehicles to pair one."
                        ))
                    }
                    stopSelf()
                    return START_NOT_STICKY
                }
                vehicleId = intent.getStringExtra("vehicle_id") ?: "unknown_vehicle"
                startCapture(address)
            }
            ACTION_STOP -> stopCapture()
        }
        return START_NOT_STICKY
    }

    // ── Start/stop ────────────────────────────────────────────────────────

    fun startCapture(address: String) {
        if (_state.value.isRunning) return
        sessionId = UUID.randomUUID().toString()
        startForeground(NOTIF_ID, buildNotification("Connecting to dongle…"))
        captureJob = serviceScope.launch {
            if (ActivityCompat.checkSelfPermission(
                    this@ObdCaptureService,
                    Manifest.permission.BLUETOOTH_CONNECT,
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                updateStatus("Bluetooth permission not granted")
                _events.emit(SessionEvent.Error(
                    "Bluetooth permission required. Grant it in Android Settings → Apps → Cactus Insights → Permissions."
                ))
                stopSelf()
                return@launch
            }
            @Suppress("MissingPermission")
            runSession(address)
        }
    }

    fun stopCapture() {
        captureJob?.cancel()
        captureJob = null
    }

    @RequiresPermission(Manifest.permission.BLUETOOTH_CONNECT)
    private suspend fun runSession(address: String) {
        updateStatus("Connecting to $address…")

        // ── Bluetooth connect ─────────────────────────────────────────────
        val btAdapter = BluetoothAdapter.getDefaultAdapter()
        val device: BluetoothDevice = btAdapter.getRemoteDevice(address)
        val sock = try {
            device.createRfcommSocketToServiceRecord(SPP_UUID).also {
                btAdapter.cancelDiscovery()
                it.connect()
            }
        } catch (e: IOException) {
            Log.e(TAG, "BT connect failed: ${e.message}")
            updateStatus("Connection failed: ${e.message}")
            _events.emit(SessionEvent.Error("Bluetooth connection failed: ${e.message}"))
            stopSelf()
            return
        }
        socket = sock

        val elm = ELM327(sock.inputStream, sock.outputStream)
        updateStatus("Initializing ELM327…")
        elm.init()

        // ── VIN query ─────────────────────────────────────────────────────
        updateStatus("Querying VIN…")
        val vin = elm.getVin()
        Log.d(TAG, "VIN: ${vin ?: "not available"}")

        // ── PID probe ─────────────────────────────────────────────────────
        updateStatus("Probing supported PIDs…")
        val supportedHex = elm.probeSupportedPids()
        val pids = if (supportedHex.isEmpty()) {
            PidRegistry.DEFAULT_PIDS
        } else {
            PidRegistry.ALL.entries
                .filter { it.value.modePid.uppercase() in supportedHex }
                .map { it.key }
                .distinct()
                .ifEmpty { PidRegistry.DEFAULT_PIDS }
        }
        Log.d(TAG, "Using ${pids.size} PIDs")

        // ── Open CSV ──────────────────────────────────────────────────────
        csvWriter.open(sessionId, vehicleId, pids, vin)
        val sessionStart = System.currentTimeMillis()
        val ts0 = System.nanoTime()

        _state.value = SessionState(
            sessionId = sessionId,
            isRunning = true,
            vin = vin,
            csvPath = csvWriter.currentFilePath,
            statusMessage = "Capturing…"
        )
        _events.emit(SessionEvent.Started)
        updateNotification("Capturing — VIN: ${vin ?: "unknown"}")

        // ── Poll loop ─────────────────────────────────────────────────────
        var sampleCount = 0
        var dtcConfirmed: List<String> = emptyList()
        var dtcPending: List<String> = emptyList()
        try {
            while (coroutineContext.isActive) {
                val loopStart = System.nanoTime()
                val timestamp = LocalDateTime.now()
                    .format(DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS"))
                val elapsedS = (System.nanoTime() - ts0) / 1_000_000_000.0

                if (sampleCount % ActyConfig.DTC_POLL_INTERVAL_CYCLES == 0) {
                    dtcConfirmed = elm.getDtcs()
                    dtcPending = elm.getPendingDtcs()
                }

                val pidValues = mutableMapOf<String, Double?>()
                val readings = mutableMapOf<String, PidReading>()

                for (pidName in pids) {
                    val def = PidRegistry.ALL[pidName] ?: continue
                    val raw = elm.query(def.modePid)
                    val value = if (raw != null) def.decoder(raw) else null
                    pidValues[pidName] = value
                    readings[pidName] = PidReading(pidName, value, def.unit)
                }

                csvWriter.writeRow(timestamp, elapsedS, vin, dtcConfirmed, dtcPending, pidValues)
                sampleCount++

                // Update RPM history for chart
                val rpm = pidValues["RPM"]?.toFloat()
                if (rpm != null) {
                    if (rpmHistory.size >= RPM_HISTORY_SIZE) rpmHistory.removeFirst()
                    rpmHistory.addLast(rpm)
                }

                val elapsed = (System.currentTimeMillis() - sessionStart) / 1000L
                _state.value = _state.value.copy(
                    elapsedSeconds = elapsed,
                    sampleCount = sampleCount,
                    pidReadings = readings,
                    rpmHistory = rpmHistory.toList()
                )

                // Pace to POLL_INTERVAL_MS
                val loopMs = (System.nanoTime() - loopStart) / 1_000_000L
                val sleep = ActyConfig.DEFAULT_POLL_RATE_MS - loopMs
                if (sleep > 0) delay(sleep)
            }
        } catch (e: CancellationException) {
            Log.d(TAG, "Capture job cancelled")
        } catch (e: Exception) {
            Log.e(TAG, "Capture error: ${e.message}")
            _events.emit(SessionEvent.Error(e.message ?: "Unknown capture error"))
        } finally {
            csvWriter.close()

            // Write .sig manifest along with CSV
            csvWriter.currentCsvFile()?.let { csvFile ->
                val sigFile = File(csvFile.parentFile, csvFile.nameWithoutExtension + ".sig")
                val merkleRoot = csvWriter.getMerkleRoot()
                val signed = sessionSigner.signSession(csvFile, sigFile, sessionId, vehicleId, merkleRoot)
                if (!signed) {
                    Log.w(TAG, "Failed to sign session ${sessionId}")
                    _events.emit(SessionEvent.Error("Signing failed for session ${sessionId}"))
                }
            }

            try { sock.close() } catch (_: Exception) {}
            socket = null

            _state.value = _state.value.copy(isRunning = false, statusMessage = "Session saved")
            _events.emit(SessionEvent.Stopped)

            // Trigger WiFi sync after session ends
            triggerSync()
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
        }
    }

    // ── WiFi sync ─────────────────────────────────────────────────────────

    private fun triggerSync() {
        // Read wifi-only setting from prefs; default to WiFi-only for safety
        val prefs    = com.acty.data.ActyPrefs(this)
        val wifiOnly = prefs.syncWifiOnly
        if (wifiOnly && !syncManager.isOnWifi()) {
            Log.d(TAG, "WiFi-only mode, not on WiFi — sync deferred")
            return
        }
        if (!syncManager.isNetworkAvailable()) {
            Log.d(TAG, "No network — sync deferred")
            return
        }
        serviceScope.launch {
            syncManager.syncPendingFiles(
                wifiOnly  = wifiOnly,
                vehicleId = vehicleId,
            ) { fileName, success ->
                serviceScope.launch {
                    if (success) _events.emit(SessionEvent.SyncComplete(fileName))
                    else _events.emit(SessionEvent.SyncFailed(fileName, "Upload failed"))
                }
            }
        }
    }

    // ── Notification ──────────────────────────────────────────────────────

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            NOTIF_CHANNEL,
            "Acty OBD Capture",
            NotificationManager.IMPORTANCE_LOW
        ).apply { description = "Active OBD capture session" }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private fun buildNotification(text: String): Notification {
        val intent = Intent(this, MainActivity::class.java)
        val pi = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE)
        return NotificationCompat.Builder(this, NOTIF_CHANNEL)
            .setContentTitle("Acty — OBD Capture")
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentIntent(pi)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(text: String) {
        val nm = getSystemService(NotificationManager::class.java)
        nm.notify(NOTIF_ID, buildNotification(text))
    }

    private fun updateStatus(msg: String) {
        _state.value = _state.value.copy(statusMessage = msg)
    }

    override fun onDestroy() {
        serviceScope.cancel()
        csvWriter.close()
        try { socket?.close() } catch (_: Exception) {}
        super.onDestroy()
    }
}
