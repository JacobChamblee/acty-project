package com.acty.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.compose.material3.Typography

// ── Cactus Insights Brand Colors ──────────────────────────────────────────────

val CactusBlue       = Color(0xFF1E40AF)  // primary brand blue
val CactusBlueMid    = Color(0xFF3B82F6)  // secondary / lighter blue
val CactusBlueLight  = Color(0xFFDBEAFE)  // blue-200 container
val CactusBluePale   = Color(0xFFEFF6FF)  // blue-50 page tint
val CactusAmber      = Color(0xFFF59E0B)  // amber accent / CTA

// ── Aliases (used by all screens — remapped to light equivalents) ──────────────

val ActyRed          = CactusBlue
val ActyRedDark      = Color(0xFF1E3A8A)
val ActyRedGlow      = Color(0x441E40AF)
val ActyRedContainer = CactusBlueLight
val ActyRedSurface   = CactusBluePale

// ── Background Spectrum — Airy Light ──────────────────────────────────────────

val BgDeep           = Color(0xFFF8FAFC)  // slate-50 — app base
val BgSurface        = Color(0xFFFFFFFF)  // white surface
val BgCard           = Color(0xFFFFFFFF)  // white card
val BgCardElevated   = Color(0xFFF1F5F9)  // slate-100 elevated
val BgBorder         = Color(0xFFE2E8F0)  // slate-200
val BgBorderSubtle   = Color(0xFFF1F5F9)  // slate-100 subtle

// ── Status Colors ─────────────────────────────────────────────────────────────

val StatusGreen      = Color(0xFF10B981)  // emerald-500
val StatusGreenDim   = Color(0xFF059669)  // emerald-600
val StatusGreenBg    = Color(0xFFECFDF5)  // emerald-50
val StatusAmber      = Color(0xFFF59E0B)  // amber-500
val StatusAmberBg    = Color(0xFFFFFBEB)  // amber-50
val StatusRed        = Color(0xFFEF4444)  // red-500
val StatusRedBg      = Color(0xFFFEF2F2)  // red-50
val StatusBlue       = Color(0xFF3B82F6)  // blue-500
val StatusBlueBg     = Color(0xFFEFF6FF)  // blue-50

// ── Text — Dark on Light ──────────────────────────────────────────────────────

val TextPrimary      = Color(0xFF0F172A)  // slate-900
val TextSecondary    = Color(0xFF475569)  // slate-600
val TextDim          = Color(0xFF94A3B8)  // slate-400
val TextHint         = Color(0xFFCBD5E1)  // slate-300

// ── Accent ────────────────────────────────────────────────────────────────────

val AccentCyan       = CactusBlueMid
val AccentPurple     = Color(0xFF8B5CF6)  // violet-500

// ── Color Scheme ──────────────────────────────────────────────────────────────

private val CactusColorScheme = lightColorScheme(
    primary              = CactusBlue,
    onPrimary            = Color.White,
    primaryContainer     = CactusBlueLight,
    onPrimaryContainer   = Color(0xFF1E3A8A),
    secondary            = StatusGreen,
    onSecondary          = Color.White,
    secondaryContainer   = StatusGreenBg,
    onSecondaryContainer = Color(0xFF065F46),
    tertiary             = CactusAmber,
    onTertiary           = Color.White,
    tertiaryContainer    = Color(0xFFFEF3C7),
    onTertiaryContainer  = Color(0xFF92400E),
    error                = StatusRed,
    onError              = Color.White,
    errorContainer       = StatusRedBg,
    onErrorContainer     = Color(0xFF991B1B),
    background           = BgDeep,
    onBackground         = TextPrimary,
    surface              = BgSurface,
    onSurface            = TextPrimary,
    surfaceVariant       = BgCardElevated,
    onSurfaceVariant     = TextSecondary,
    surfaceContainer     = BgCard,
    surfaceContainerHigh = BgCardElevated,
    outline              = BgBorder,
    outlineVariant       = BgBorderSubtle,
    inverseSurface       = Color(0xFF1E293B),
    inverseOnSurface     = Color(0xFFF8FAFC),
    scrim                = Color(0x55000000),
)

// ── Typography ────────────────────────────────────────────────────────────────

val ActyTypography = Typography(
    displayLarge = TextStyle(
        fontSize      = 72.sp,
        fontWeight    = FontWeight.Black,
        letterSpacing = (-2).sp,
        color         = TextPrimary,
    ),
    displayMedium = TextStyle(
        fontSize      = 48.sp,
        fontWeight    = FontWeight.Bold,
        letterSpacing = (-1.5).sp,
        color         = TextPrimary,
    ),
    displaySmall = TextStyle(
        fontSize      = 36.sp,
        fontWeight    = FontWeight.Bold,
        letterSpacing = (-1).sp,
        color         = TextPrimary,
    ),
    headlineLarge = TextStyle(
        fontSize      = 28.sp,
        fontWeight    = FontWeight.Bold,
        letterSpacing = (-0.5).sp,
        color         = TextPrimary,
    ),
    headlineMedium = TextStyle(
        fontSize      = 22.sp,
        fontWeight    = FontWeight.SemiBold,
        color         = TextPrimary,
    ),
    headlineSmall = TextStyle(
        fontSize      = 18.sp,
        fontWeight    = FontWeight.SemiBold,
        color         = TextPrimary,
    ),
    titleLarge = TextStyle(
        fontSize   = 16.sp,
        fontWeight = FontWeight.SemiBold,
        color      = TextPrimary,
    ),
    titleMedium = TextStyle(
        fontSize   = 14.sp,
        fontWeight = FontWeight.Medium,
        color      = TextPrimary,
    ),
    titleSmall = TextStyle(
        fontSize      = 12.sp,
        fontWeight    = FontWeight.Medium,
        letterSpacing = 0.3.sp,
        color         = TextSecondary,
    ),
    bodyLarge = TextStyle(
        fontSize   = 16.sp,
        fontWeight = FontWeight.Normal,
        color      = TextPrimary,
    ),
    bodyMedium = TextStyle(
        fontSize   = 14.sp,
        fontWeight = FontWeight.Normal,
        color      = TextSecondary,
    ),
    bodySmall = TextStyle(
        fontSize   = 12.sp,
        fontWeight = FontWeight.Normal,
        color      = TextSecondary,
    ),
    labelLarge = TextStyle(
        fontSize      = 12.sp,
        fontWeight    = FontWeight.SemiBold,
        letterSpacing = 0.5.sp,
        color         = TextPrimary,
    ),
    labelMedium = TextStyle(
        fontSize      = 11.sp,
        fontWeight    = FontWeight.Medium,
        letterSpacing = 0.5.sp,
        color         = TextSecondary,
    ),
    labelSmall = TextStyle(
        fontSize      = 10.sp,
        fontWeight    = FontWeight.Medium,
        letterSpacing = 0.8.sp,
        color         = TextDim,
    ),
)

// ── Theme Composable ──────────────────────────────────────────────────────────

@Composable
fun ActyTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = CactusColorScheme,
        typography  = ActyTypography,
        content     = content,
    )
}
