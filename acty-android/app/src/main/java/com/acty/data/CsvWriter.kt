package com.acty.data

import android.content.Context
import java.io.BufferedWriter
import java.io.File
import java.io.FileWriter
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/**
 * CsvWriter.kt
 * Writes OBD session data to CSV files using app-scoped external storage.
 * Output: <app-external>/data_capture/acty_obd_YYYYMMDD_HHMMSS_<sessionId>.csv
 *
 * Uses context.getExternalFilesDir(null) which:
 *  - Works on all Android versions without storage permissions
 *  - Survives app updates (cleared on uninstall)
 *  - Is accessible via file manager on Android 11+
 */
class CsvWriter(context: Context) {

    val dataDir: File = File(context.getExternalFilesDir(null), "data_capture")
        .also { it.mkdirs() }

    private var writer: BufferedWriter? = null
    private var currentFile: File? = null
    private var pidColumns: List<String> = emptyList()
    private var previousRowHash: String = ""
    private val rowHashes = mutableListOf<String>()

    var currentSessionId: String? = null
        private set
    var currentVehicleId: String? = null
        private set

    val currentFilePath: String? get() = currentFile?.absolutePath
    val currentFileName: String? get() = currentFile?.name

    fun open(sessionId: String, vehicleId: String, pids: List<String>, vin: String?) {
        currentSessionId = sessionId
        currentVehicleId = vehicleId
        previousRowHash = ""
        rowHashes.clear()
        pidColumns = pids

        val ts   = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"))
        val file = File(dataDir, "acty_obd_${ts}_$sessionId.csv")
        currentFile = file

        writer = BufferedWriter(FileWriter(file)).also { w ->
            val header = (listOf("timestamp", "elapsed_s", "VIN", "DTC_CONFIRMED", "DTC_PENDING", "prev_hash") + pids)
                .joinToString(",")
            w.write(header)
            w.newLine()
            w.flush()
        }
    }

    fun writeRow(
        timestamp:      String,
        elapsedSeconds: Double,
        vin:            String?,
        dtcConfirmed:   List<String>,
        dtcPending:     List<String>,
        pidValues:      Map<String, Double?>,
    ) {
        val w = writer ?: return
        val line = buildList {
            add(timestamp)
            add(elapsedSeconds.toString())
            add(vin ?: "")
            add(dtcConfirmed.joinToString("|"))
            add(dtcPending.joinToString("|"))
            add(previousRowHash)
            for (pid in pidColumns) add(pidValues[pid]?.toString() ?: "")
        }.joinToString(",")

        w.write(line)
        w.newLine()
        w.flush()

        val hash = sha256(line.toByteArray(Charsets.UTF_8))
        rowHashes.add(hash)
        previousRowHash = hash
    }

    fun close() {
        writer?.close()
        writer = null
    }

    fun currentCsvFile(): File? = currentFile

    fun getMerkleRoot(): String {
        if (rowHashes.isEmpty()) return ""
        var nodes = rowHashes.toMutableList()
        while (nodes.size > 1) {
            val next = mutableListOf<String>()
            var i = 0
            while (i < nodes.size) {
                val left  = nodes[i]
                val right = if (i + 1 < nodes.size) nodes[i + 1] else left
                next.add(sha256((left + right).toByteArray(Charsets.UTF_8)))
                i += 2
            }
            nodes = next
        }
        return nodes.first()
    }

    private fun sha256(data: ByteArray): String {
        val md     = java.security.MessageDigest.getInstance("SHA-256")
        val digest = md.digest(data)
        return digest.joinToString("") { "%02x".format(it) }
    }
}
