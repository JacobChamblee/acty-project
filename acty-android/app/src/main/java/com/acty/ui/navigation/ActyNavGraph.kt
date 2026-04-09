package com.acty.ui.navigation

import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.runtime.Composable
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.acty.ui.SessionViewModel
import com.acty.ui.screens.AboutScreen
import com.acty.ui.screens.AccountScreen
import com.acty.ui.screens.CaptureScreen
import com.acty.ui.screens.HomeScreen
import com.acty.ui.screens.NeedleNestScreen
import com.acty.ui.screens.SessionsScreen
import com.acty.ui.screens.SharingScreen

sealed class Screen(val route: String) {
    object Home       : Screen("home")
    object NeedleNest : Screen("needlenest")
    object Capture    : Screen("capture")
    object Sessions   : Screen("sessions")
    object Account    : Screen("account")
    object About      : Screen("about")
    object Sharing    : Screen("sharing/{sessionId}") {
        fun go(sessionId: String) = "sharing/$sessionId"
    }
}

private val TRANSITION_MS = 250

@Composable
fun ActyNavHost(
    navController: NavHostController,
    sessionViewModel: SessionViewModel,
) {
    NavHost(
        navController    = navController,
        startDestination = Screen.Home.route,
        enterTransition  = { fadeIn(tween(TRANSITION_MS)) },
        exitTransition   = { fadeOut(tween(TRANSITION_MS)) },
        popEnterTransition  = { fadeIn(tween(TRANSITION_MS)) },
        popExitTransition   = { fadeOut(tween(TRANSITION_MS)) },
    ) {
        composable(Screen.Home.route) {
            HomeScreen(
                viewModel    = sessionViewModel,
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
                viewModel  = sessionViewModel,
                onShare    = { id -> navController.navigate(Screen.Sharing.go(id)) },
            )
        }
        composable(Screen.Account.route) {
            AccountScreen(
                onAbout = { navController.navigate(Screen.About.route) }
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
