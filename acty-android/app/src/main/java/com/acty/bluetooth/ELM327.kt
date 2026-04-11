package com.acty.bluetooth

import android.util.Log
import java.io.InputStream
import java.io.OutputStream

/**
 * ELM327.kt
 * AT command layer over an RFCOMM socket InputStream/OutputStream.
 * Direct port of the ELM327 class from acty_obd_capture.py.
 */
class ELM327(
    private val input: InputStream,
    private val output: OutputStream
) {
    companion object {
        private const val TAG = "ELM327"
        private const val PROMPT = '>'
        private const val TIMEOUT_MS = 3000L
        private const val VIN_TIMEOUT_MS = 5000L
    }

    // ── Low-level send/receive ─────────────────────────────────────────────

    fun send(cmd: String, timeoutMs: Long = TIMEOUT_MS): String {
        val cmdBytes = (cmd + "\r").toByteArray(Charsets.US_ASCII)
        output.write(cmdBytes)
        output.flush()

        val buf = StringBuilder()
        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            if (input.available() > 0) {
                val b = input.read()
                if (b == -1) break
                val c = b.toChar()
                if (c == PROMPT) break
                buf.append(c)
            } else {
                Thread.sleep(10)
            }
        }

        var result = buf.toString()
            .replace("\r", "")
            .replace(">", "")
            .trim()

        // Strip echo — if response starts with the command, strip it
        if (result.uppercase().startsWith(cmd.uppercase())) {
            result = result.substring(cmd.length).trim()
        }
        return result
    }

    // ── Initialization sequence (matches Python init()) ────────────────────

    fun init(): Boolean {
        val cmds = listOf(
            "ATZ"   to 5000L,   // Reset
            "ATE0"  to 2000L,   // Echo off
            "ATL0"  to 2000L,   // Linefeeds off
            "ATS0"  to 2000L,   // Spaces off
            "ATH0"  to 2000L,   // Headers off
            "ATSP0" to 2000L,   // Auto protocol
            "ATAT1" to 2000L,   // Adaptive timing
        )
        for ((cmd, timeout) in cmds) {
            val resp = send(cmd, timeout)
            val ok = "OK" in resp.uppercase() || "ELM327" in resp.uppercase()
            Log.d(TAG, "  $cmd: ${if (ok) "✓" else resp}")
            if (cmd == "ATZ" && resp.isBlank()) {
                Log.w(TAG, "ATZ got no response — continuing anyway")
            }
        }
        Log.d(TAG, "ELM327 ready")
        return true
    }

    // ── Mode 01 PID query ─────────────────────────────────────────────────

    fun query(modePid: String): ByteArray? {
        val resp = send(modePid)
        if (resp.isBlank()) return null
        val u = resp.uppercase().replace(" ", "").replace("\n", "")
        val badTokens = listOf("NODATA", "ERROR", "UNABLE", "STOPPED", "?")
        if (badTokens.any { it in u }) return null

        val modeResp = "4${modePid[1]}"
        val pidByte  = modePid.substring(2, 4).uppercase()
        val prefix   = modeResp + pidByte

        val dataHex = if (prefix in u) {
            u.substring(u.indexOf(prefix) + prefix.length)
        } else u

        if (dataHex.isEmpty()) return null
        return try {
            ByteArray(dataHex.length / 2) { i ->
                dataHex.substring(i * 2, i * 2 + 2).toInt(16).toByte()
            }
        } catch (e: NumberFormatException) {
            null
        }
    }

    // ── Mode 09 VIN query ─────────────────────────────────────────────────

    fun getVin(): String? {
        val resp = send("0902", VIN_TIMEOUT_MS)
        if (resp.isBlank()) return null
        val u = resp.uppercase().replace(" ", "").replace("\n", "")
        val badTokens = listOf("NODATA", "ERROR", "UNABLE", "?")
        if (badTokens.any { it in u }) return null

        val hex = if ("4902" in u) u.substring(u.indexOf("4902") + 4) else u
        return try {
            // Decode bytes to ASCII string, then regex-extract 17-char VIN
            val sb = StringBuilder()
            var i = 0
            while (i + 1 < hex.length) {
                val b = hex.substring(i, i + 2).toInt(16)
                if (b in 0x20..0x7E) sb.append(b.toChar())
                i += 2
            }
            val vinRegex = Regex("[A-HJ-NPR-Z0-9]{17}")
            vinRegex.find(sb.toString().uppercase())?.value
        } catch (e: Exception) {
            Log.w(TAG, "VIN parse error: ${e.message}")
            null
        }
    }

    // ── Mode 01 PID support probe ─────────────────────────────────────────

    fun probeSupportedPids(): Set<String> {
        val supported = mutableSetOf<String>()
        val supportPids = listOf("0100", "0120", "0140", "0160", "0180", "01A0", "01C0")

        for (sp in supportPids) {
            val resp = send(sp, 3000L)
            if (resp.isBlank() || listOf("NODATA", "ERROR", "UNABLE").any { it in resp.uppercase() }) continue

            val hexStr = resp.uppercase().replace(" ", "")
            val modeResp = "4${sp[1]}${sp.substring(2, 4).uppercase()}"
            val idx = hexStr.indexOf(modeResp)
            if (idx < 0) continue
            val dataHex = hexStr.substring(idx + modeResp.length)
            if (dataHex.length < 8) continue

            try {
                val bitmask = dataHex.substring(0, 8).toLong(16)
                val base = sp.substring(2).toInt(16)
                for (bit in 0 until 32) {
                    if (bitmask and (1L shl (31 - bit)) != 0L) {
                        val pidNum = base + bit + 1
                        supported.add("01${pidNum.toString(16).uppercase().padStart(2, '0')}")
                    }
                }
            } catch (e: NumberFormatException) {
                continue
            }
        }
        Log.d(TAG, "Probe found ${supported.size} supported PIDs")
        return supported
    }

    // ── Adapter type detection ────────────────────────────────────────────
    //
    // Sends ATI, AT@1, and AT@2 then maps the combined response to a known
    // adapter_type string. Must be called AFTER init() completes.

    fun detectAdapterType(): String {
        val ati = send("ATI",  2000L).uppercase()
        val at1 = send("AT@1", 2000L).uppercase()
        val at2 = send("AT@2", 2000L).uppercase()
        Log.d(TAG, "Adapter detection — ATI=$ati  AT@1=$at1  AT@2=$at2")

        return when {
            "VGATE" in at1 && ("PRO 2S" in at1 || "ICAR PRO" in at1) -> "vgate_icar_pro_2s"
            "VEEPEAK" in ati || "VEEPEAK" in at1 || "VEEPEAK" in at2  -> "veepeak_ble"
            "VGATE" in at1 && ("BLE" in at1 || "4.0" in at1)          -> "vgate_ble_4"
            "VGATE" in at1                                              -> "vgate_icar_pro_2s"
            "BAFX" in ati  || "BAFX" in at1                            -> "bafx"
            "OBDLINK" in ati || "OBDLINK" in at1                       -> "obdlink_cx"
            else                                                         -> "unknown"
        }
    }

    // ── Mode 03 DTC read ──────────────────────────────────────────────────

    fun getDtcs(): List<String> {
        return parseDtcs(send("03", 5000L), "43")
    }

    fun getPendingDtcs(): List<String> {
        return parseDtcs(send("07", 5000L), "47")
    }

    private fun parseDtcs(resp: String, prefix: String): List<String> {
        if (resp.isBlank() || "NO DATA" in resp.uppercase()) return emptyList()

        val codes = mutableListOf<String>()
        val hexStr = resp.uppercase().replace(" ", "").replace("\n", "")
        var hex = if (prefix in hexStr) hexStr.substring(hexStr.indexOf(prefix) + 2) else hexStr

        val prefixMap = mapOf(0 to "P0", 1 to "P1", 2 to "P2", 3 to "P3",
                              4 to "C0", 5 to "C1", 6 to "B0", 7 to "U0")
        var i = 0
        while (i + 3 < hex.length) {
            try {
                val b1 = hex.substring(i, i + 2).toInt(16)
                val b2 = hex.substring(i + 2, i + 4).toInt(16)
                if (b1 != 0 || b2 != 0) {
                    val p = prefixMap[(b1 shr 4) shr 1] ?: "P"
                    codes.add("$p${(b1 and 0x3F).toString(16).uppercase()}${b2.toString(16).uppercase().padStart(2, '0')}")
                }
            } catch (e: NumberFormatException) { /* skip */ }
            i += 4
        }
        return codes
    }
}
