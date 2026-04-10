package com.acty.ui.navigation

import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.acty.ui.SessionViewModel
import androidx.navigation.NavType
import androidx.navigation.navArgument
import com.acty.ui.screens.AboutScreen
import com.acty.ui.screens.AccountScreen
import com.acty.ui.screens.CaptureScreen
import com.acty.ui.screens.HomeScreen
import com.acty.ui.screens.InsightsScreen
import com.acty.ui.screens.LoginScreen
import com.acty.ui.screens.NeedleNestScreen
import com.acty.ui.screens.OBDDevicesScreen
import com.acty.ui.screens.RegisterScreen
import com.acty.ui.screens.SessionsScreen
import com.acty.ui.screens.SharingScreen

sealed class Screen(val route: String) {
    object Login       : Screen("login")
    object Register    : Screen("register")
    object Home        : Screen("home")
    object NeedleNest  : Screen("needlenest")
    object Capture     : Screen("capture")
    object Sessions    : Screen("sessions")
    object Account     : Screen("account")
    object About       : Screen("about")
    object OBDDevices  : Screen("obd_devices")
    object Sharing     : Screen("sharing/{sessionId}") {
        fun go(sessionId: String) = "sharing/$sessionId"
    }
    object Insights    : Screen("insights/{filename}") {
        fun go(filename: String) = "insights/${android.net.Uri.encode(filename)}"
    }
}

private val TRANSITION_MS = 250

@Composable
fun ActyNavHost(
    navController:    NavHostController,
    sessionViewModel: SessionViewModel,
    startDestination: String,
) {
    // Helper: navigate to the main app and clear the entire back stack (used after auth)
    fun NavHostController.toMain() {
        navigate(Screen.Home.route) {
            popUpTo(0) { inclusive = true }
            launchSingleTop = true
        }
    }

    // Helper: navigate to login and clear entire back stack (used on sign-out)
    fun NavHostController.toLogin() {
        navigate(Screen.Login.route) {
            popUpTo(0) { inclusive = true }
            launchSingleTop = true
        }
    }

    NavHost(
        navController    = navController,
        startDestination = startDestination,
        enterTransition  = { fadeIn(tween(TRANSITION_MS)) },
        exitTransition   = { fadeOut(tween(TRANSITION_MS)) },
        popEnterTransition  = { fadeIn(tween(TRANSITION_MS)) },
        popExitTransition   = { fadeOut(tween(TRANSITION_MS)) },
    ) {
        // ── Auth screens (no bottom nav) ──────────────────────
        composable(Screen.Login.route) {
            LoginScreen(
                onLoginSuccess       = { navController.toMain() },
                onNavigateToRegister = {
                    navController.navigate(Screen.Register.route) {
                        launchSingleTop = true
                    }
                },
            )
        }
        composable(Screen.Register.route) {
            RegisterScreen(
                onRegisterSuccess = { navController.toMain() },
                onNavigateToLogin = { navController.popBackStack() },
            )
        }

        // ── Main app screens (bottom nav shown) ───────────────
        composable(Screen.Home.route) {
            HomeScreen(
                viewModel      = sessionViewModel,
                onStartCapture = { navController.navigate(Screen.Capture.route) },
                onViewSessions = { navController.navigate(Screen.Sessions.route) },
            )
        }
        composable(Screen.NeedleNest.route) {
            NeedleNestScreen(viewModel = sessionViewModel)
        }
        composable(Screen.Capture.route) {
            CaptureScreen(viewModel = sessionViewModel)
        }
        composable(Screen.Sessions.route) {
            SessionsScreen(
                viewModel      = sessionViewModel,
                onShare        = { id -> navController.navigate(Screen.Sharing.go(id)) },
                onAnalyze      = { filename -> navController.navigate(Screen.Insights.go(filename)) },
                onManageDevices = { navController.navigate(Screen.OBDDevices.route) },
            )
        }
        composable(Screen.OBDDevices.route) {
            OBDDevicesScreen(onBack = { navController.popBackStack() })
        }
        composable(
            route     = Screen.Insights.route,
            arguments = listOf(navArgument("filename") { type = NavType.StringType }),
        ) { backStack ->
            val filename = backStack.arguments?.getString("filename") ?: ""
            InsightsScreen(
                sessionFilename = filename,
                onBack          = { navController.popBackStack() },
            )
        }
        composable(Screen.Account.route) {
            AccountScreen(
                onAbout    = { navController.navigate(Screen.About.route) },
                onSignOut  = { navController.toLogin() },
            )
        }
        composable(Screen.About.route) {
            AboutScreen(onBack = { navController.popBackStack() })
        }
        composable(Screen.Sharing.route) { backStack ->
            val sessionId = backStack.arguments?.getString("sessionId") ?: ""
            SharingScreen(
                sessionId = sessionId,
                onBack    = { navController.popBackStack() },
            )
        }
    }
}
