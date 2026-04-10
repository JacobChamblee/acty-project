package com.acty.ui.screens

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.acty.data.ActyPrefs
import com.acty.ui.theme.*

// ── OBDDevicesScreen ──────────────────────────────────────────────────────────
//
// Lists bonded Bluetooth devices. User taps one to set it as the active OBD
// adapter, stored in ActyPrefs.obdMacAddress / obdDeviceName.
// Requires BLUETOOTH_CONNECT permission on Android 12+.

data class BtDevice(
    val name: String,
    val address: String,
    val isLikelyObd: Boolean,   // heuristic: ELM327, OBD, VLINK, etc.
)

private fun isLikelyObdAdapter(name: String): Boolean {
    val n = name.lowercase()
    return listOf("elm327", "elm 327", "obd", "vlink", "obdii", "obd2",
                  "kiwi", "veepeak", "scantool", "carista", "bluedriver")
        .any { n.contains(it) }
}

private fun getBondedDevices(context: Context): List<BtDevice> {
    val hasPerm = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        ContextCompat.checkSelfPermission(
            context, Manifest.permission.BLUETOOTH_CONNECT
        ) == PackageManager.PERMISSION_GRANTED
    } else true

    if (!hasPerm) return emptyList()

    val btManager = context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
    val adapter   = btManager?.adapter ?: return emptyList()
    if (!adapter.isEnabled) return emptyList()

    return try {
        adapter.bondedDevices.orEmpty().map { dev ->
            BtDevice(
                name        = dev.name ?: "Unknown (${dev.address})",
                address     = dev.address,
                isLikelyObd = isLikelyObdAdapter(dev.name ?: ""),
            )
        }.sortedWith(compareByDescending<BtDevice> { it.isLikelyObd }.thenBy { it.name })
    } catch (_: SecurityException) {
        emptyList()
    }
}

// ── Screen ────────────────────────────────────────────────────────────────────

@Composable
fun OBDDevicesScreen(onBack: () -> Unit) {
    val context   = LocalContext.current
    val prefs     = remember { ActyPrefs(context) }

    var devices        by remember { mutableStateOf<List<BtDevice>>(emptyList()) }
    var permDenied     by remember { mutableStateOf(false) }
    var selectedMac    by remember { mutableStateOf(prefs.obdMacAddress) }
    var savedBanner    by remember { mutableStateOf(false) }

    // Load bonded devices
    LaunchedEffect(Unit) {
        val hasPerm = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S)
            ContextCompat.checkSelfPermission(context, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED
        else true

        if (!hasPerm) {
            permDenied = true
        } else {
            devices = getBondedDevices(context)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFFF8FAFC))
            .systemBarsPadding(),
    ) {
        // Top bar
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.Filled.ArrowBack, contentDescription = "Back", tint = TextPrimary)
            }
            Spacer(Modifier.width(4.dp))
            Column {
                Text(
                    "OBD Devices",
                    style = MaterialTheme.typography.titleLarge.copy(
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary,
                    ),
                )
                Text(
                    "Select your ELM327-compatible adapter",
                    style = MaterialTheme.typography.bodySmall.copy(color = TextDim),
                )
            }
        }

        HorizontalDivider(color = BgBorder, thickness = 0.5.dp)

        if (savedBanner) {
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 10.dp),
                color = Color(0xFFECFDF5),
                shape = RoundedCornerShape(10.dp),
                border = BorderStroke(0.5.dp, Color(0xFF6EE7B7)),
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Filled.CheckCircle, null, tint = Color(0xFF10B981), modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "Device saved. Open Capture to start a session.",
                        style = MaterialTheme.typography.bodySmall.copy(
                            color = Color(0xFF065F46),
                            fontWeight = FontWeight.Medium,
                        ),
                    )
                }
            }
        }

        if (permDenied) {
            PermissionDeniedCard()
        } else {
            val btManager = context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
            val btEnabled = btManager?.adapter?.isEnabled == true

            if (!btEnabled) {
                BluetoothOffCard()
            } else if (devices.isEmpty()) {
                NoPairedDevicesCard()
            } else {
                // Current device chip
                val currentName = prefs.obdDeviceName
                if (currentName.isNotBlank() && currentName != "No device selected") {
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 20.dp, vertical = 12.dp),
                        color = CactusBluePale,
                        shape = RoundedCornerShape(12.dp),
                        border = BorderStroke(0.5.dp, CactusBlue.copy(alpha = 0.3f)),
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Icon(Icons.Outlined.BluetoothConnected, null,
                                tint = CactusBlue, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Column {
                                Text("Active OBD Adapter",
                                    style = MaterialTheme.typography.labelSmall.copy(color = CactusBlue))
                                Text(currentName,
                                    style = MaterialTheme.typography.bodyMedium.copy(
                                        fontWeight = FontWeight.SemiBold, color = TextPrimary))
                            }
                        }
                    }
                }

                // Section label
                val obd = devices.filter { it.isLikelyObd }
                val other = devices.filter { !it.isLikelyObd }

                LazyColumn(
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 4.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    if (obd.isNotEmpty()) {
                        item {
                            SectionLabel("OBD-II Adapters (detected)")
                        }
                        items(obd) { dev ->
                            DeviceCard(
                                device      = dev,
                                isSelected  = dev.address == selectedMac,
                                onSelect    = {
                                    prefs.obdMacAddress  = dev.address
                                    prefs.obdDeviceName  = dev.name
                                    selectedMac          = dev.address
                                    savedBanner          = true
                                },
                            )
                        }
                    }
                    if (other.isNotEmpty()) {
                        item {
                            SectionLabel(if (obd.isEmpty()) "Paired Devices" else "Other Paired Devices")
                        }
                        items(other) { dev ->
                            DeviceCard(
                                device     = dev,
                                isSelected = dev.address == selectedMac,
                                onSelect   = {
                                    prefs.obdMacAddress = dev.address
                                    prefs.obdDeviceName = dev.name
                                    selectedMac         = dev.address
                                    savedBanner         = true
                                },
                            )
                        }
                    }
                    item {
                        PairingHintCard()
                        Spacer(Modifier.height(60.dp))
                    }
                }
            }
        }
    }
}

// ── Sub-components ────────────────────────────────────────────────────────────

@Composable
private fun SectionLabel(text: String) {
    Text(
        text  = text.uppercase(),
        style = MaterialTheme.typography.labelSmall.copy(
            color = TextDim, letterSpacing = 0.08.sp, fontWeight = FontWeight.Bold,
        ),
        modifier = Modifier.padding(top = 8.dp, bottom = 4.dp),
    )
}

@Composable
private fun DeviceCard(
    device:    BtDevice,
    isSelected: Boolean,
    onSelect:  () -> Unit,
) {
    val borderColor = if (isSelected) CactusBlue else BgBorder
    val bgColor     = if (isSelected) CactusBluePale else Color.White

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .clickable(onClick = onSelect),
        color  = bgColor,
        shape  = RoundedCornerShape(14.dp),
        border = BorderStroke(if (isSelected) 1.5.dp else 0.5.dp, borderColor),
        shadowElevation = if (isSelected) 2.dp else 0.dp,
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // Icon
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(if (device.isLikelyObd) CactusBluePale else Color(0xFFF1F5F9)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = if (device.isLikelyObd) Icons.Filled.DirectionsCar
                                  else Icons.Outlined.Bluetooth,
                    contentDescription = null,
                    tint     = if (device.isLikelyObd) CactusBlue else TextDim,
                    modifier = Modifier.size(22.dp),
                )
            }

            Spacer(Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    device.name,
                    style = MaterialTheme.typography.bodyMedium.copy(
                        fontWeight = FontWeight.SemiBold, color = TextPrimary,
                    ),
                )
                Text(
                    device.address,
                    style = MaterialTheme.typography.bodySmall.copy(
                        color = TextDim, fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                    ),
                )
                if (device.isLikelyObd) {
                    Spacer(Modifier.height(4.dp))
                    Surface(
                        color  = Color(0xFFECFDF5),
                        shape  = RoundedCornerShape(4.dp),
                        border = BorderStroke(0.5.dp, Color(0xFF6EE7B7)),
                    ) {
                        Text(
                            "OBD Adapter",
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            style    = MaterialTheme.typography.labelSmall.copy(
                                color      = Color(0xFF065F46),
                                fontWeight = FontWeight.SemiBold,
                            ),
                        )
                    }
                }
            }

            if (isSelected) {
                Icon(
                    Icons.Filled.CheckCircle,
                    contentDescription = "Selected",
                    tint     = CactusBlue,
                    modifier = Modifier.size(22.dp),
                )
            } else {
                Icon(
                    Icons.Outlined.RadioButtonUnchecked,
                    contentDescription = null,
                    tint     = BgBorder,
                    modifier = Modifier.size(22.dp),
                )
            }
        }
    }
}

@Composable
private fun PairingHintCard() {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 12.dp),
        color  = Color(0xFFFFFBEB),
        shape  = RoundedCornerShape(12.dp),
        border = BorderStroke(0.5.dp, Color(0xFFFDE68A)),
    ) {
        Row(modifier = Modifier.padding(14.dp)) {
            Icon(Icons.Outlined.Info, null, tint = Color(0xFFF59E0B), modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(10.dp))
            Column {
                Text(
                    "Don't see your adapter?",
                    style = MaterialTheme.typography.labelMedium.copy(
                        fontWeight = FontWeight.SemiBold, color = Color(0xFF78350F),
                    ),
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "Pair your ELM327 OBD-II adapter in Android Settings → Bluetooth first, " +
                    "then return here to select it. Most adapters default PIN: 1234 or 0000.",
                    style = MaterialTheme.typography.bodySmall.copy(color = Color(0xFF92400E)),
                )
            }
        }
    }
}

@Composable
private fun PermissionDeniedCard() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(32.dp)) {
            Icon(Icons.Outlined.BluetoothDisabled, null,
                tint = StatusAmber, modifier = Modifier.size(48.dp))
            Spacer(Modifier.height(16.dp))
            Text("Bluetooth Permission Required",
                style = MaterialTheme.typography.titleMedium.copy(
                    fontWeight = FontWeight.Bold, color = TextPrimary))
            Spacer(Modifier.height(8.dp))
            Text(
                "Grant Bluetooth permission in Settings → Apps → Cactus Insights → Permissions.",
                style = MaterialTheme.typography.bodySmall.copy(color = TextDim),
                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            )
        }
    }
}

@Composable
private fun BluetoothOffCard() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(32.dp)) {
            Icon(Icons.Outlined.BluetoothDisabled, null,
                tint = StatusAmber, modifier = Modifier.size(48.dp))
            Spacer(Modifier.height(16.dp))
            Text("Bluetooth is Off",
                style = MaterialTheme.typography.titleMedium.copy(
                    fontWeight = FontWeight.Bold, color = TextPrimary))
            Spacer(Modifier.height(8.dp))
            Text("Turn on Bluetooth to see paired devices.",
                style = MaterialTheme.typography.bodySmall.copy(color = TextDim),
                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            )
        }
    }
}

@Composable
private fun NoPairedDevicesCard() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(32.dp),
        ) {
            Icon(Icons.Outlined.Bluetooth, null,
                tint = CactusBlue, modifier = Modifier.size(48.dp))
            Spacer(Modifier.height(16.dp))
            Text("No Paired Devices",
                style = MaterialTheme.typography.titleMedium.copy(
                    fontWeight = FontWeight.Bold, color = TextPrimary))
            Spacer(Modifier.height(8.dp))
            Text(
                "Pair your ELM327 OBD-II adapter via Android Settings → Bluetooth, " +
                "then come back here to select it.",
                style = MaterialTheme.typography.bodySmall.copy(color = TextDim),
                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            )
            Spacer(Modifier.height(20.dp))
            PairingHintCard()
        }
    }
}
