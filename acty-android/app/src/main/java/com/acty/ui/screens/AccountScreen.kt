package com.acty.ui.screens

import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.content.Intent
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import com.acty.data.ActyPrefs
import com.acty.data.SyncManager
import com.acty.data.VehicleEntry
import com.acty.model.*
import com.acty.ui.theme.*
import java.io.File

// ── AccountScreen ─────────────────────────────────────────────────────────────

@Composable
fun AccountScreen(onAbout: () -> Unit) {
    val context     = LocalContext.current
    val prefs       = remember { ActyPrefs(context) }
    val syncManager = remember { SyncManager(context) }

    var settings       by remember { mutableStateOf(
        AccountSettings(
            username       = "jacob_acty",
            email          = "jacob@acty-labs.com",
            byokApiKey     = prefs.byokApiKey,
            byokProvider   = prefs.byokProvider,
            syncOnWifiOnly = prefs.syncWifiOnly,
        )
    )}
    var vehicles       by remember { mutableStateOf(prefs.loadVehicles()) }
    var showByokSheet  by remember { mutableStateOf(false) }
    var showAddVehicle by remember { mutableStateOf(false) }
    var showBtPicker   by remember { mutableStateOf(false) }
    var btPickerTarget by remember { mutableStateOf<String?>(null) } // vehicle id being edited, null = new

    fun refreshVehicles() { vehicles = prefs.loadVehicles() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(Color(0xFFF5F3FF), Color(0xFFF8FAFC)),
                    startY = 0f, endY = 600f,
                )
            )
            .verticalScroll(rememberScrollState())
            .systemBarsPadding()
            .padding(bottom = 24.dp),
    ) {
        AccountHeader(username = settings.username, email = settings.email)

        Spacer(Modifier.height(20.dp))

        // ── Vehicle section ──────────────────────────────────
        AccountSection(title = "My Vehicles") {
            if (vehicles.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 20.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        "No vehicles added yet",
                        style = MaterialTheme.typography.bodySmall.copy(color = TextDim),
                    )
                }
            } else {
                vehicles.forEachIndexed { idx, v ->
                    VehicleRow(
                        vehicle  = v,
                        onSetActive = {
                            prefs.setActiveVehicle(v.id)
                            refreshVehicles()
                        },
                        onPickBt = {
                            btPickerTarget = v.id
                            showBtPicker   = true
                        },
                    )
                    if (idx < vehicles.lastIndex) {
                        HorizontalDivider(color = BgBorder, thickness = 0.5.dp,
                            modifier = Modifier.padding(horizontal = 16.dp))
                    }
                }
                HorizontalDivider(color = BgBorder, thickness = 0.5.dp,
                    modifier = Modifier.padding(horizontal = 16.dp))
            }
            SettingAction(
                icon    = Icons.Outlined.Add,
                label   = "Add Vehicle",
                tint    = CactusBlue,
                onClick = { showAddVehicle = true },
            )
        }

        Spacer(Modifier.height(16.dp))

        // ── Alerts section ───────────────────────────────────
        AccountSection(title = "Alerts") {
            ToggleRow("DTC Codes",         settings.alertDtcEnabled)      { settings = settings.copy(alertDtcEnabled = it) }
            ToggleRow("LTFT Threshold",    settings.alertLtftEnabled)      { settings = settings.copy(alertLtftEnabled = it) }
            ToggleRow("Service Reminders", settings.alertServiceEnabled)   { settings = settings.copy(alertServiceEnabled = it) }
            ToggleRow("Charging Alerts",   settings.alertChargingEnabled)  { settings = settings.copy(alertChargingEnabled = it) }

            if (settings.alertLtftEnabled) {
                Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("LTFT Alert Threshold", style = MaterialTheme.typography.bodyMedium.copy(color = TextPrimary))
                        Text("±%.1f%%".format(settings.ltftAlertThreshold),
                            style = MaterialTheme.typography.titleSmall.copy(color = CactusBlue))
                    }
                    Slider(
                        value         = settings.ltftAlertThreshold,
                        onValueChange = { settings = settings.copy(ltftAlertThreshold = it) },
                        valueRange    = 5f..15f,
                        steps         = 9,
                        colors        = SliderDefaults.colors(
                            thumbColor         = CactusBlue,
                            activeTrackColor   = CactusBlue,
                            inactiveTrackColor = BgBorder,
                        ),
                    )
                    Text("Normal ±7.5%  ·  Action ±10%",
                        style = MaterialTheme.typography.labelSmall.copy(color = TextDim))
                }
            }
        }

        Spacer(Modifier.height(16.dp))

        // ── Sync section ─────────────────────────────────────
        AccountSection(title = "Sync & Storage") {
            DropdownRow(
                label    = "Sync Frequency",
                selected = settings.syncFrequency.label,
                options  = SyncFrequency.entries.map { it.label },
                onSelect = { label ->
                    val sel = SyncFrequency.entries.first { it.label == label }
                    settings = settings.copy(syncFrequency = sel)
                    prefs.syncFrequencyLabel = label
                },
            )
            ToggleRow("Wi-Fi Only", settings.syncOnWifiOnly) {
                settings = settings.copy(syncOnWifiOnly = it)
                prefs.syncWifiOnly = it
            }
            DropdownRow(
                label    = "Data Retention",
                selected = settings.retentionPolicy.label,
                options  = RetentionPolicy.entries.map { it.label },
                onSelect = { label ->
                    val sel = RetentionPolicy.entries.first { it.label == label }
                    settings = settings.copy(retentionPolicy = sel)
                },
            )
            ToggleRow("Email Reports", settings.emailReportsEnabled) {
                settings = settings.copy(emailReportsEnabled = it)
            }
        }

        Spacer(Modifier.height(16.dp))

        // ── LLM / BYOK section ───────────────────────────────
        AccountSection(title = "AI & BYOK") {
            SettingRow(
                icon    = Icons.Outlined.Key,
                label   = "API Key",
                detail  = if (settings.byokApiKey.isNotEmpty())
                    "●●●● " + settings.byokApiKey.takeLast(4)
                else
                    "Not configured",
                onClick = { showByokSheet = true },
                tint    = AccentPurple,
            )
            SettingRow(
                icon    = Icons.Outlined.Psychology,
                label   = "LLM Provider",
                detail  = settings.byokProvider.ifEmpty { "Acty Default (Ollama)" },
                onClick = { showByokSheet = true },
                tint    = AccentPurple,
            )
        }

        Spacer(Modifier.height(16.dp))

        // ── Privacy section ──────────────────────────────────
        AccountSection(title = "Privacy") {
            PrivacyDashboardRow()
            SettingAction(
                icon    = Icons.Outlined.DownloadForOffline,
                label   = "Export All Session Data",
                onClick = {
                    // Share entire data_capture directory contents
                    val files = syncManager.dataDir.listFiles { f ->
                        f.name.endsWith(".csv") || f.name.endsWith(".sig")
                    } ?: emptyArray()
                    val uris = files.map {
                        FileProvider.getUriForFile(context, "${context.packageName}.provider", it)
                    }
                    if (uris.isNotEmpty()) {
                        val intent = Intent(Intent.ACTION_SEND_MULTIPLE).apply {
                            type = "text/plain"
                            putParcelableArrayListExtra(Intent.EXTRA_STREAM, ArrayList(uris))
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        }
                        context.startActivity(Intent.createChooser(intent, "Export All Sessions"))
                    }
                },
            )
            SettingAction(
                icon    = Icons.Outlined.DeleteSweep,
                label   = "Clear Local Data",
                tint    = StatusRed,
                onClick = { /* confirm dialog before deleting */ },
            )
        }

        Spacer(Modifier.height(16.dp))

        // ── App section ──────────────────────────────────────
        AccountSection(title = "App") {
            SettingAction(icon = Icons.Outlined.Info,       label = "About Cactus",        onClick = onAbout)
            SettingAction(icon = Icons.Outlined.BugReport,  label = "Diagnostics & Logs",  onClick = {})
            SettingRow(
                icon    = Icons.Outlined.VerifiedUser,
                label   = "App Version",
                detail  = "0.1.0 — build 1",
                onClick = {},
            )
        }
    }

    // ── Sheets ────────────────────────────────────────────────────────────────

    if (showByokSheet) {
        ByokBottomSheet(
            currentKey      = settings.byokApiKey,
            currentProvider = settings.byokProvider,
            onSave          = { key, provider ->
                // Persist both — key encrypted, provider plain
                prefs.byokApiKey  = key
                prefs.byokProvider = provider
                settings = settings.copy(byokApiKey = key, byokProvider = provider)
                showByokSheet = false
            },
            onDismiss = { showByokSheet = false },
        )
    }

    if (showAddVehicle) {
        AddVehicleSheet(
            onSave = { entry ->
                val updated = prefs.loadVehicles().toMutableList()
                // If this is the first vehicle, mark it active
                val withActive = if (updated.isEmpty()) entry.copy(isActive = true) else entry
                updated.add(withActive)
                prefs.saveVehicles(updated)
                // Save its MAC as the active OBD address too (if populated)
                if (withActive.isActive && withActive.obdMac.isNotBlank()) {
                    prefs.obdMacAddress  = withActive.obdMac
                    prefs.obdDeviceName  = "${withActive.year} ${withActive.make} ${withActive.model}"
                }
                refreshVehicles()
                showAddVehicle = false
            },
            onDismiss = { showAddVehicle = false },
            onPickBt  = {
                btPickerTarget = null   // new vehicle
                showBtPicker   = true
            },
        )
    }

    if (showBtPicker) {
        BluetoothPickerSheet(
            onPick = { device ->
                val mac  = device.address
                val name = device.name ?: mac
                if (btPickerTarget != null) {
                    // Update existing vehicle's OBD MAC
                    val updated = prefs.loadVehicles().map { v ->
                        if (v.id == btPickerTarget) v.copy(obdMac = mac) else v
                    }
                    prefs.saveVehicles(updated)
                    // If this vehicle is active, update global OBD MAC
                    val active = updated.firstOrNull { it.id == btPickerTarget }
                    if (active?.isActive == true) {
                        prefs.obdMacAddress = mac
                        prefs.obdDeviceName = name
                    }
                    refreshVehicles()
                } else {
                    // Being called from AddVehicleSheet — return to caller
                    prefs.obdMacAddress = mac
                    prefs.obdDeviceName = name
                }
                showBtPicker = false
            },
            onDismiss = { showBtPicker = false },
        )
    }
}

// ── Account Header ────────────────────────────────────────────────────────────

@Composable
fun AccountHeader(username: String, email: String) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(Brush.verticalGradient(listOf(AccentPurple.copy(alpha = 0.10f), Color.Transparent)))
            .padding(horizontal = 20.dp, vertical = 20.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(56.dp)
                    .shadow(8.dp, CircleShape, spotColor = CactusBlue.copy(alpha = 0.15f))
                    .clip(CircleShape)
                    .background(Brush.radialGradient(listOf(CactusBlueMid, CactusBlue))),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text  = username.take(1).uppercase(),
                    style = MaterialTheme.typography.headlineSmall.copy(
                        color      = Color.White,
                        fontWeight = FontWeight.Bold,
                    ),
                )
            }
            Spacer(Modifier.width(16.dp))
            Column {
                Text("Account",
                    style = MaterialTheme.typography.headlineMedium.copy(fontWeight = FontWeight.Black))
                Text("@$username",
                    style = MaterialTheme.typography.bodyMedium.copy(color = TextSecondary))
                Text(email, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

// ── Section Wrapper ───────────────────────────────────────────────────────────

@Composable
fun AccountSection(title: String, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.padding(horizontal = 20.dp)) {
        Text(
            text     = title.uppercase(),
            style    = MaterialTheme.typography.labelSmall.copy(color = TextDim),
            modifier = Modifier.padding(bottom = 8.dp, start = 4.dp),
        )
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .shadow(6.dp, RoundedCornerShape(16.dp), spotColor = Color.Black.copy(alpha = 0.04f))
                .clip(RoundedCornerShape(16.dp))
                .background(Color.White)
                .border(0.5.dp, BgBorder, RoundedCornerShape(16.dp)),
            content  = content,
        )
    }
}

// ── Vehicle Row ───────────────────────────────────────────────────────────────

@Composable
fun VehicleRow(vehicle: VehicleEntry, onSetActive: () -> Unit, onPickBt: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onSetActive)
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(36.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(if (vehicle.isActive) CactusBluePale else BgCardElevated),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                Icons.Outlined.DirectionsCar, null,
                tint     = if (vehicle.isActive) CactusBlue else TextDim,
                modifier = Modifier.size(18.dp),
            )
        }
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Text("${vehicle.year} ${vehicle.make} ${vehicle.model}",
                style = MaterialTheme.typography.titleMedium)
            Text(
                text  = if (vehicle.obdMac.isNotBlank()) vehicle.obdMac else "No OBD adapter",
                style = MaterialTheme.typography.bodySmall.copy(color = TextDim),
            )
        }
        if (vehicle.isActive) {
            Text(
                "ACTIVE",
                style    = MaterialTheme.typography.labelSmall.copy(color = StatusGreenDim),
                modifier = Modifier
                    .clip(RoundedCornerShape(100.dp))
                    .background(StatusGreenBg)
                    .padding(horizontal = 8.dp, vertical = 3.dp),
            )
            Spacer(Modifier.width(8.dp))
        }
        // Pair OBD button
        IconButton(onClick = onPickBt, modifier = Modifier.size(36.dp)) {
            Icon(Icons.Outlined.Bluetooth, null,
                tint     = if (vehicle.obdMac.isNotBlank()) CactusBlue else TextDim,
                modifier = Modifier.size(18.dp))
        }
        Icon(Icons.Filled.ChevronRight, null, tint = TextDim, modifier = Modifier.size(18.dp))
    }
}

// ── Setting rows ──────────────────────────────────────────────────────────────

@Composable
fun ToggleRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onChange(!checked) }
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium.copy(color = TextPrimary),
            modifier = Modifier.weight(1f))
        Switch(
            checked         = checked,
            onCheckedChange = onChange,
            colors          = SwitchDefaults.colors(
                checkedThumbColor   = Color.White,
                checkedTrackColor   = CactusBlue,
                uncheckedThumbColor = TextDim,
                uncheckedTrackColor = BgBorder,
            ),
        )
    }
}

@Composable
fun SettingRow(
    icon:    ImageVector,
    label:   String,
    detail:  String,
    onClick: () -> Unit,
    tint:    Color = TextSecondary,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, tint = tint, modifier = Modifier.size(20.dp))
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.bodyMedium.copy(color = TextPrimary))
            Text(detail, style = MaterialTheme.typography.bodySmall)
        }
        Icon(Icons.Filled.ChevronRight, null, tint = TextDim, modifier = Modifier.size(18.dp))
    }
}

@Composable
fun SettingAction(
    icon:    ImageVector,
    label:   String,
    tint:    Color = TextSecondary,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, tint = tint, modifier = Modifier.size(20.dp))
        Spacer(Modifier.width(14.dp))
        Text(
            text     = label,
            style    = MaterialTheme.typography.bodyMedium.copy(
                color = if (tint == StatusRed) StatusRed else TextPrimary
            ),
            modifier = Modifier.weight(1f),
        )
        Icon(Icons.Filled.ChevronRight, null, tint = TextDim, modifier = Modifier.size(18.dp))
    }
}

@Composable
fun DropdownRow(label: String, selected: String, options: List<String>, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { expanded = true }
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(label, style = MaterialTheme.typography.bodyMedium.copy(color = TextPrimary),
                modifier = Modifier.weight(1f))
            Text(selected, style = MaterialTheme.typography.bodySmall.copy(color = CactusBlue))
            Spacer(Modifier.width(4.dp))
            Icon(Icons.Filled.ArrowDropDown, null, tint = TextDim, modifier = Modifier.size(18.dp))
        }
        DropdownMenu(
            expanded         = expanded,
            onDismissRequest = { expanded = false },
            modifier         = Modifier.background(Color.White),
        ) {
            options.forEach { opt ->
                DropdownMenuItem(
                    text    = { Text(opt, style = MaterialTheme.typography.bodyMedium.copy(
                        color = if (opt == selected) CactusBlue else TextPrimary)) },
                    onClick = { onSelect(opt); expanded = false },
                )
            }
        }
    }
}

// ── Privacy Dashboard ─────────────────────────────────────────────────────────

@Composable
fun PrivacyDashboardRow() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(StatusGreenBg)
            .border(0.5.dp, StatusGreenDim.copy(alpha = 0.4f), RoundedCornerShape(12.dp))
            .padding(12.dp),
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.Shield, null, tint = StatusGreenDim, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(8.dp))
                Text("Privacy Dashboard",
                    style = MaterialTheme.typography.titleSmall.copy(color = StatusGreenDim))
            }
            Spacer(Modifier.height(8.dp))
            PrivacyBullet("Stored locally",       "CSV + Ed25519 sig, owner-encrypted")
            PrivacyBullet("Synced to backend",    "Encrypted in transit, TLS 1.3")
            PrivacyBullet("Shared anonymously",   "None — regional opt-in off")
            PrivacyBullet("Sold to third parties","Never. Architectural invariant.")
        }
    }
}

@Composable
fun PrivacyBullet(label: String, value: String) {
    Row(Modifier.padding(vertical = 2.dp)) {
        Text("·  ", style = MaterialTheme.typography.bodySmall.copy(color = TextDim))
        Text("$label: ", style = MaterialTheme.typography.bodySmall.copy(color = TextSecondary))
        Text(value, style = MaterialTheme.typography.bodySmall.copy(color = TextPrimary, fontWeight = FontWeight.Medium))
    }
}

// ── Add Vehicle Sheet ─────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddVehicleSheet(
    onSave:   (VehicleEntry) -> Unit,
    onDismiss: () -> Unit,
    onPickBt: () -> Unit,
) {
    val context = LocalContext.current
    val prefs   = remember { ActyPrefs(context) }

    var make       by remember { mutableStateOf("") }
    var model      by remember { mutableStateOf("") }
    var year       by remember { mutableStateOf("") }
    var drivetrain by remember { mutableStateOf("") }
    var obdMac     by remember { mutableStateOf(prefs.obdMacAddress) }
    var obdName    by remember { mutableStateOf(prefs.obdDeviceName) }

    // Refresh picked BT device when sheet re-enters composition
    LaunchedEffect(Unit) {
        obdMac  = prefs.obdMacAddress
        obdName = prefs.obdDeviceName
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor   = Color.White,
        dragHandle       = {
            Box(
                Modifier
                    .padding(vertical = 12.dp)
                    .size(width = 40.dp, height = 4.dp)
                    .clip(RoundedCornerShape(100.dp))
                    .background(BgBorder)
            )
        },
    ) {
        Column(
            modifier            = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp)
                .padding(bottom = 40.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text("Add Vehicle",
                style = MaterialTheme.typography.headlineSmall.copy(fontWeight = FontWeight.Bold))

            @Composable
            fun Field(label: String, value: String, onChange: (String) -> Unit, numeric: Boolean = false) {
                OutlinedTextField(
                    value         = value,
                    onValueChange = onChange,
                    modifier      = Modifier.fillMaxWidth(),
                    label         = { Text(label) },
                    singleLine    = true,
                    keyboardOptions = if (numeric)
                        androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Number)
                    else
                        androidx.compose.foundation.text.KeyboardOptions.Default,
                    colors        = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor   = CactusBlue,
                        unfocusedBorderColor = BgBorder,
                        focusedLabelColor    = CactusBlue,
                        focusedTextColor     = TextPrimary,
                        unfocusedTextColor   = TextPrimary,
                        unfocusedContainerColor = Color.White,
                        focusedContainerColor   = Color.White,
                    ),
                    shape = RoundedCornerShape(12.dp),
                )
            }

            Field("Make (e.g. Toyota)",  make,  { make  = it })
            Field("Model (e.g. GR86)",   model, { model = it })
            Field("Year (e.g. 2024)",    year,  { year  = it }, numeric = true)
            Field("Drivetrain (e.g. RWD)", drivetrain, { drivetrain = it })

            // OBD adapter picker
            Column {
                Text("OBD Adapter", style = MaterialTheme.typography.titleSmall.copy(color = TextSecondary))
                Spacer(Modifier.height(6.dp))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .shadow(3.dp, RoundedCornerShape(12.dp))
                        .clip(RoundedCornerShape(12.dp))
                        .background(Color.White)
                        .border(0.5.dp, if (obdMac.isNotBlank()) CactusBlue.copy(alpha = 0.4f) else BgBorder, RoundedCornerShape(12.dp))
                        .clickable(onClick = onPickBt)
                        .padding(horizontal = 14.dp, vertical = 14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        Icons.Outlined.Bluetooth, null,
                        tint     = if (obdMac.isNotBlank()) CactusBlue else TextDim,
                        modifier = Modifier.size(20.dp),
                    )
                    Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            text  = if (obdMac.isNotBlank()) obdName else "Tap to scan for OBD adapter",
                            style = MaterialTheme.typography.bodyMedium.copy(color = TextPrimary),
                        )
                        if (obdMac.isNotBlank()) {
                            Text(obdMac, style = MaterialTheme.typography.bodySmall.copy(color = TextDim))
                        }
                    }
                    Icon(Icons.Filled.ChevronRight, null, tint = TextDim, modifier = Modifier.size(18.dp))
                }
            }

            // Save
            val canSave = make.isNotBlank() && model.isNotBlank() && year.isNotBlank()
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .shadow(if (canSave) 6.dp else 0.dp, RoundedCornerShape(14.dp),
                        spotColor = CactusBlue.copy(alpha = 0.2f))
                    .clip(RoundedCornerShape(14.dp))
                    .background(if (canSave) Brush.linearGradient(listOf(CactusBlue, CactusBlueMid))
                        else Brush.linearGradient(listOf(BgCardElevated, BgCardElevated)))
                    .clickable(enabled = canSave) {
                        onSave(
                            VehicleEntry(
                                make       = make.trim(),
                                model      = model.trim(),
                                year       = year.trim().toIntOrNull() ?: 2020,
                                drivetrain = drivetrain.trim(),
                                obdMac     = obdMac.trim(),
                            )
                        )
                    }
                    .padding(vertical = 16.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    "Save Vehicle",
                    style = MaterialTheme.typography.titleMedium.copy(
                        color      = if (canSave) Color.White else TextDim,
                        fontWeight = FontWeight.Bold,
                    ),
                )
            }
        }
    }
}

// ── Bluetooth Device Picker Sheet ─────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BluetoothPickerSheet(
    onPick:    (BluetoothDevice) -> Unit,
    onDismiss: () -> Unit,
) {
    val bondedDevices: List<BluetoothDevice> = remember {
        try {
            BluetoothAdapter.getDefaultAdapter()
                ?.bondedDevices
                ?.toList()
                ?: emptyList()
        } catch (_: SecurityException) { emptyList() }
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor   = Color.White,
        dragHandle = {
            Box(
                Modifier
                    .padding(vertical = 12.dp)
                    .size(width = 40.dp, height = 4.dp)
                    .clip(RoundedCornerShape(100.dp))
                    .background(BgBorder)
            )
        },
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp)
                .padding(bottom = 40.dp),
        ) {
            Text("Select OBD Adapter",
                style = MaterialTheme.typography.headlineSmall.copy(fontWeight = FontWeight.Bold))
            Spacer(Modifier.height(4.dp))
            Text(
                "Paired Bluetooth devices — make sure your OBD dongle is powered on.",
                style = MaterialTheme.typography.bodySmall,
            )
            Spacer(Modifier.height(16.dp))

            if (bondedDevices.isEmpty()) {
                Box(
                    modifier         = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(14.dp))
                        .background(BgCardElevated)
                        .padding(24.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(Icons.Outlined.BluetoothDisabled, null,
                            tint = TextDim, modifier = Modifier.size(36.dp))
                        Spacer(Modifier.height(8.dp))
                        Text("No paired devices found",
                            style = MaterialTheme.typography.bodyMedium.copy(color = TextSecondary))
                        Text(
                            "Pair your OBD adapter in Android Bluetooth Settings first.",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Spacer(Modifier.height(12.dp))
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(12.dp))
                                .background(Brush.linearGradient(listOf(CactusBlue, CactusBlueMid)))
                                .clickable { onDismiss() }
                                .padding(horizontal = 20.dp, vertical = 12.dp),
                        ) {
                            Text("Open Bluetooth Settings",
                                style = MaterialTheme.typography.labelLarge.copy(color = Color.White))
                        }
                    }
                }
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    bondedDevices.forEach { device ->
                        val name = try { device.name ?: device.address } catch (_: SecurityException) { device.address }
                        val addr = device.address

                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .shadow(4.dp, RoundedCornerShape(14.dp))
                                .clip(RoundedCornerShape(14.dp))
                                .background(Color.White)
                                .border(0.5.dp, BgBorder, RoundedCornerShape(14.dp))
                                .clickable { onPick(device) }
                                .padding(horizontal = 16.dp, vertical = 14.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(40.dp)
                                    .clip(RoundedCornerShape(12.dp))
                                    .background(CactusBluePale),
                                contentAlignment = Alignment.Center,
                            ) {
                                Icon(Icons.Outlined.Bluetooth, null,
                                    tint = CactusBlue, modifier = Modifier.size(20.dp))
                            }
                            Spacer(Modifier.width(14.dp))
                            Column(Modifier.weight(1f)) {
                                Text(name, style = MaterialTheme.typography.titleMedium)
                                Text(addr, style = MaterialTheme.typography.bodySmall.copy(color = TextDim))
                            }
                            Icon(Icons.Filled.ChevronRight, null,
                                tint = TextDim, modifier = Modifier.size(18.dp))
                        }
                    }
                }
            }
        }
    }
}

// ── BYOK Bottom Sheet ─────────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ByokBottomSheet(
    currentKey:      String,
    currentProvider: String,
    onSave:          (String, String) -> Unit,
    onDismiss:       () -> Unit,
) {
    var apiKey   by remember { mutableStateOf(currentKey) }
    var provider by remember { mutableStateOf(currentProvider.ifEmpty { "openai" }) }
    var showKey  by remember { mutableStateOf(false) }
    val providers = listOf("openai", "anthropic", "acty-default")

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor   = Color.White,
        dragHandle = {
            Box(
                Modifier
                    .padding(vertical = 12.dp)
                    .size(width = 40.dp, height = 4.dp)
                    .clip(RoundedCornerShape(100.dp))
                    .background(BgBorder)
            )
        },
    ) {
        Column(
            modifier            = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp)
                .padding(bottom = 40.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("BYOK — Bring Your Own Key",
                style = MaterialTheme.typography.headlineSmall.copy(fontWeight = FontWeight.Bold))
            Text(
                "Your API key is stored in Android EncryptedSharedPreferences using AES-256-GCM. Cactus never transmits it.",
                style = MaterialTheme.typography.bodySmall,
            )

            Text("Provider", style = MaterialTheme.typography.titleSmall.copy(color = TextSecondary))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                providers.forEach { p ->
                    val sel = provider == p
                    Text(
                        text  = p,
                        style = MaterialTheme.typography.labelMedium.copy(
                            color = if (sel) Color.White else TextSecondary),
                        modifier = Modifier
                            .shadow(if (sel) 4.dp else 0.dp, RoundedCornerShape(100.dp),
                                spotColor = CactusBlue.copy(alpha = 0.15f))
                            .clip(RoundedCornerShape(100.dp))
                            .background(if (sel) CactusBlue else Color.White)
                            .border(0.5.dp, if (sel) CactusBlue else BgBorder, RoundedCornerShape(100.dp))
                            .clickable { provider = p }
                            .padding(horizontal = 14.dp, vertical = 8.dp),
                    )
                }
            }

            OutlinedTextField(
                value                = apiKey,
                onValueChange        = { apiKey = it },
                modifier             = Modifier.fillMaxWidth(),
                label                = { Text("API Key") },
                visualTransformation = if (showKey) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    IconButton(onClick = { showKey = !showKey }) {
                        Icon(
                            if (showKey) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                            null, tint = TextSecondary,
                        )
                    }
                },
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor      = CactusBlue,
                    unfocusedBorderColor    = BgBorder,
                    focusedLabelColor       = CactusBlue,
                    focusedTextColor        = TextPrimary,
                    unfocusedTextColor      = TextPrimary,
                    unfocusedContainerColor = Color.White,
                    focusedContainerColor   = Color.White,
                ),
                shape      = RoundedCornerShape(14.dp),
                singleLine = true,
            )

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .shadow(6.dp, RoundedCornerShape(14.dp), spotColor = CactusBlue.copy(alpha = 0.18f))
                    .clip(RoundedCornerShape(14.dp))
                    .background(Brush.linearGradient(listOf(CactusBlue, CactusBlueMid)))
                    .clickable { onSave(apiKey.trim(), provider) }
                    .padding(vertical = 16.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text("Save Key",
                    style = MaterialTheme.typography.titleMedium.copy(
                        color = Color.White, fontWeight = FontWeight.Bold))
            }
        }
    }
}
