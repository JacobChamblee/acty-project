package com.acty

object ActyConfig {
    const val API_BASE = "https://api.acty-labs.com"
    const val VERIFY_BASE = "https://verify.acty-labs.com"

    // Supabase — matches values in frontend/.env
    const val SUPABASE_URL      = "https://vfkruktodsetjqhgxgxs.supabase.co"
    const val SUPABASE_ANON_KEY = "sb_publishable_IrJsreczMRvmYVWW_Liy1g_0vgoZ4zT"
    // Deep-link scheme registered in AndroidManifest for OAuth callback
    const val OAUTH_REDIRECT    = "com.acty.app://auth/callback"
    const val KEYSTORE_ALIAS = "acty_device_key"
    const val BT_UUID = "00001101-0000-1000-8000-00805F9B34FB"
    const val OBD_RFCOMM_CHANNEL = 1
    const val DEFAULT_POLL_RATE_MS = 1000L
    const val DTC_POLL_INTERVAL_CYCLES = 30
    const val LTFT_WARNING_THRESHOLD = 7.5
    const val LTFT_ACTION_THRESHOLD = 10.0
    const val VOLTAGE_WARNING = 13.5
    const val VOLTAGE_ACTION = 13.0
}
