package com.acty.ui

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
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
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.acty.data.AuthManager
import com.acty.ui.navigation.ActyNavHost
import com.acty.ui.navigation.Screen
import com.acty.ui.theme.*

data class NavItem(
    val screen:       Screen,
    val label:        String,
    val icon:         ImageVector,
    val iconSelected: ImageVector = icon,
    val isCenterFab:  Boolean = false,
)

class MainActivity : ComponentActivity() {

    private val viewModel: SessionViewModel by viewModels()

    // BT permission request
    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        // After permissions granted, check if BT still needs enabling
        if (results.values.all { it }) {
            requestBluetoothEnable()
        }
    }

    // BT enable request
    private val btEnableLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { /* user accepted or declined — UI will reflect adapter state */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Let Compose handle all window insets (edge-to-edge)
        WindowCompat.setDecorFitsSystemWindows(window, false)

        // Ask permissions then enable BT
        ensureBluetooth()

        setContent {
            ActyTheme {
                ActyScaffold(
                    viewModel       = viewModel,
                    onRequestBtEnable = { requestBluetoothEnable() },
                )
            }
        }
    }

    override fun onStart() { super.onStart(); viewModel.bindService(this) }
    override fun onStop()  { super.onStop();  viewModel.unbindService(this) }

    private fun ensureBluetooth() {
        val needed = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            listOf(
                Manifest.permission.BLUETOOTH_CONNECT,
                Manifest.permission.BLUETOOTH_SCAN,
            )
        } else {
            listOf(
                Manifest.permission.BLUETOOTH,
                Manifest.permission.BLUETOOTH_ADMIN,
            )
        }
        val missing = needed.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            permissionLauncher.launch(missing.toTypedArray())
        } else {
            requestBluetoothEnable()
        }
    }

    fun requestBluetoothEnable() {
        val btManager = getSystemService(BLUETOOTH_SERVICE) as? BluetoothManager ?: return
        val btAdapter = btManager.adapter ?: return
        if (!btAdapter.isEnabled) {
            @Suppress("DEPRECATION")
            btEnableLauncher.launch(Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE))
        }
    }
}

// ── Root scaffold ──────────────────────────────────────────────────────────────
//
// Uses Material3 Scaffold + NavigationBar which correctly handles
// WindowInsets (edge-to-edge, gesture nav, 3-button nav) on all API levels.

@Composable
fun ActyScaffold(
    viewModel:          SessionViewModel,
    onRequestBtEnable:  () -> Unit = {},
) {
    val navController = rememberNavController()
    val navBackStack  by navController.currentBackStackEntryAsState()
    val currentRoute  = navBackStack?.destination?.route
    val sessionState  by viewModel.state.collectAsStateWithLifecycle()
    val haptic        = LocalHapticFeedback.current
    val context       = LocalContext.current

    // Determine start destination from persisted session
    val startDestination = remember {
        if (AuthManager(context).isLoggedIn()) Screen.Home.route else Screen.Login.route
    }

    val navItems = listOf(
        NavItem(Screen.Home,       "Home",      Icons.Outlined.Home,             Icons.Filled.Home),
        NavItem(Screen.NeedleNest, "Analytics", Icons.Outlined.BarChart,         Icons.Filled.BarChart),
        NavItem(Screen.Capture,    "Capture",   Icons.Filled.FiberManualRecord,  isCenterFab = true),
        NavItem(Screen.Sessions,   "Sessions",  Icons.Outlined.ListAlt,          Icons.Filled.ListAlt),
        NavItem(Screen.Account,    "Account",   Icons.Outlined.Person,           Icons.Filled.Person),
    )

    // Only show bottom nav on top-level app screens (not auth screens)
    val topLevelRoutes = navItems.map { it.screen.route }.toSet()
    val showNav = currentRoute in topLevelRoutes

    // Show any capture/BT error as a snackbar
    val snackbarHostState = remember { SnackbarHostState() }
    val event by viewModel.events.collectAsStateWithLifecycle()
    LaunchedEffect(event) {
        val e = event
        if (e is com.acty.model.SessionEvent.Error) {
            snackbarHostState.showSnackbar(e.message, duration = SnackbarDuration.Long)
            viewModel.clearEvent()
        }
    }

    Scaffold(
        // Scaffold manages top/bottom inset padding automatically
        contentWindowInsets = WindowInsets(0),
        snackbarHost        = { SnackbarHost(snackbarHostState) },
        bottomBar = {
            if (showNav) {
                CactusBottomNav(
                    items        = navItems,
                    currentRoute = currentRoute,
                    isCapturing  = sessionState.isRunning,
                    onNavigate   = { item ->
                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        navController.navigate(item.screen.route) {
                            popUpTo(navController.graph.findStartDestination().id) {
                                saveState = true
                            }
                            launchSingleTop = true
                            restoreState    = true
                        }
                    },
                    onCaptureFab = {
                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        if (sessionState.isRunning) {
                            viewModel.stopCapture(context)
                        } else {
                            navController.navigate(Screen.Capture.route) {
                                launchSingleTop = true
                            }
                        }
                    },
                    onRequestBtEnable = onRequestBtEnable,
                )
            }
        },
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)   // Scaffold provides correct padding for nav bar + status bar
                .background(BgDeep)
        ) {
            ActyNavHost(
                navController    = navController,
                sessionViewModel = viewModel,
                startDestination = startDestination,
            )
        }
    }
}

// ── Bottom navigation bar ──────────────────────────────────────────────────────
//
// NavigationBar is a Material3 component that automatically adds
// WindowInsets.navigationBars padding below the bar content, so it
// always sits above gesture handles / 3-button nav on every device.

@Composable
fun CactusBottomNav(
    items:             List<NavItem>,
    currentRoute:      String?,
    isCapturing:       Boolean,
    onNavigate:        (NavItem) -> Unit,
    onCaptureFab:      () -> Unit,
    onRequestBtEnable: () -> Unit,
) {
    NavigationBar(
        containerColor      = Color(0xF8FFFFFF),  // white 97% — frosted glass feel
        contentColor        = CactusBlue,
        tonalElevation      = 0.dp,
        windowInsets        = WindowInsets.navigationBars,  // explicit — places bar above gesture nav
        modifier            = Modifier
            .fillMaxWidth()
            .shadow(
                elevation    = 12.dp,
                shape        = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp),
                clip         = false,
                ambientColor = Color.Black.copy(alpha = 0.06f),
                spotColor    = CactusBlue.copy(alpha = 0.08f),
            )
            .clip(RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp))
            .border(
                width = 0.5.dp,
                color = Color(0xFFE2E8F0),
                shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp),
            ),
    ) {
        items.forEach { item ->
            if (item.isCenterFab) {
                // Center capture FAB — sits inside NavigationBar, raised above the bar
                NavigationBarItem(
                    selected = false,
                    onClick  = {},
                    icon     = {
                        CenterCaptureFab(
                            isCapturing       = isCapturing,
                            onClick           = onCaptureFab,
                            onRequestBtEnable = onRequestBtEnable,
                        )
                    },
                    label    = null,
                    colors   = NavigationBarItemDefaults.colors(
                        indicatorColor = Color.Transparent,
                    ),
                )
            } else {
                val selected = currentRoute == item.screen.route
                NavigationBarItem(
                    selected = selected,
                    onClick  = { onNavigate(item) },
                    icon     = {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            if (selected) {
                                Box(
                                    Modifier
                                        .size(4.dp)
                                        .clip(CircleShape)
                                        .background(CactusBlue)
                                )
                                Spacer(Modifier.height(2.dp))
                            } else {
                                Spacer(Modifier.height(6.dp))
                            }
                            Icon(
                                imageVector        = if (selected) item.iconSelected else item.icon,
                                contentDescription = item.label,
                                modifier           = Modifier.size(22.dp),
                            )
                        }
                    },
                    label = {
                        Text(
                            text  = item.label,
                            style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                        )
                    },
                    colors = NavigationBarItemDefaults.colors(
                        selectedIconColor       = CactusBlue,
                        selectedTextColor       = CactusBlue,
                        unselectedIconColor     = TextDim,
                        unselectedTextColor     = TextDim,
                        indicatorColor          = CactusBluePale,
                    ),
                    alwaysShowLabel = true,
                )
            }
        }
    }
}

// ── Center Capture FAB ────────────────────────────────────────────────────────

@Composable
fun CenterCaptureFab(
    isCapturing:       Boolean,
    onClick:           () -> Unit,
    onRequestBtEnable: () -> Unit = {},
) {
    val fabScale by animateFloatAsState(
        targetValue   = if (isCapturing) 1.08f else 1f,
        animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy),
        label         = "fabScale",
    )

    val fabGradient = if (isCapturing)
        Brush.radialGradient(listOf(Color(0xFFEF4444), Color(0xFFDC2626)))
    else
        Brush.radialGradient(listOf(CactusBlueMid, CactusBlue))

    val shadowColor = if (isCapturing) Color(0xFFEF4444) else CactusBlue

    Box(
        modifier = Modifier
            .size(56.dp)
            .scale(fabScale)
            .shadow(
                elevation    = 14.dp,
                shape        = CircleShape,
                ambientColor = shadowColor.copy(alpha = 0.20f),
                spotColor    = shadowColor.copy(alpha = 0.35f),
            )
            .clip(CircleShape)
            .background(fabGradient)
            .border(
                width = 1.5.dp,
                brush = fabGradient,
                shape = CircleShape,
            )
            .clickable(
                interactionSource = remember { MutableInteractionSource() },
                indication        = null,
                onClick           = onClick,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector        = if (isCapturing) Icons.Filled.Stop else Icons.Filled.FiberManualRecord,
            contentDescription = if (isCapturing) "Stop capture" else "Start capture",
            tint               = Color.White,
            modifier           = Modifier.size(26.dp),
        )
    }
}
