package com.acty.ui

import android.app.Application
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.acty.bluetooth.ObdCaptureService
import com.acty.data.ActyPrefs
import com.acty.model.SessionEvent
import com.acty.model.SessionState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class SessionViewModel(app: Application) : AndroidViewModel(app) {

    private val prefs = ActyPrefs(app)

    private var service: ObdCaptureService? = null
    private val _state = MutableStateFlow(SessionState())
    val state: StateFlow<SessionState> = _state.asStateFlow()

    private val _events = MutableStateFlow<SessionEvent?>(null)
    val events: StateFlow<SessionEvent?> = _events.asStateFlow()

    // Read saved MAC from prefs; fallback to empty string (user must configure)
    var targetAddress: String
        get() = prefs.obdMacAddress
        set(v) { prefs.obdMacAddress = v }

    var vehicleId: String
        get() = prefs.activeVehicle()?.id ?: "unknown_vehicle"
        set(_) { /* set via prefs directly */ }

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName, binder: IBinder) {
            val svc = (binder as ObdCaptureService.LocalBinder).getService()
            service = svc
            viewModelScope.launch { svc.state.collect  { _state.value  = it } }
            viewModelScope.launch { svc.events.collect { _events.value = it } }
        }
        override fun onServiceDisconnected(name: ComponentName) { service = null }
    }

    fun bindService(context: Context) {
        Intent(context, ObdCaptureService::class.java).also {
            context.bindService(it, connection, Context.BIND_AUTO_CREATE)
        }
    }

    fun unbindService(context: Context) {
        try { context.unbindService(connection) } catch (_: Exception) {}
    }

    fun startCapture(context: Context) {
        val mac = targetAddress
        if (mac.isBlank()) {
            // No device configured — surface this as an error event
            _events.value = SessionEvent.Error("No OBD adapter selected. Go to Account → My Vehicles to pair one.")
            return
        }
        Intent(context, ObdCaptureService::class.java).also { intent ->
            intent.action = ObdCaptureService.ACTION_START
            intent.putExtra("address",    mac)
            intent.putExtra("vehicle_id", vehicleId)
            context.startForegroundService(intent)
        }
    }

    fun stopCapture(context: Context) {
        Intent(context, ObdCaptureService::class.java).also { intent ->
            intent.action = ObdCaptureService.ACTION_STOP
            context.startService(intent)
        }
    }

    fun clearEvent() { _events.value = null }
}
