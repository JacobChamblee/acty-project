# Acty ProGuard rules

# ── Kotlin ────────────────────────────────────────────────────────────────────
-keepattributes *Annotation*
-keepclassmembers class ** { @kotlin.Metadata *; }
-keep class kotlin.** { *; }
-keep class kotlinx.** { *; }

# ── Jetpack Compose ───────────────────────────────────────────────────────────
-keep class androidx.compose.** { *; }
-keepclassmembers class * {
    @androidx.compose.runtime.Composable <methods>;
}

# ── AndroidX Lifecycle / ViewModel ────────────────────────────────────────────
-keep class androidx.lifecycle.** { *; }
-keepclassmembers class * extends androidx.lifecycle.ViewModel { <init>(...); }

# ── OkHttp / Okio ─────────────────────────────────────────────────────────────
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }
-keep interface okhttp3.** { *; }

# ── MPAndroidChart ────────────────────────────────────────────────────────────
-keep class com.github.mikephil.charting.** { *; }

# ── Acty data models (JSON serialization) ─────────────────────────────────────
-keep class com.acty.model.** { *; }
-keep class com.acty.data.** { *; }

# ── Ed25519 / Conscrypt (session signing) ─────────────────────────────────────
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
