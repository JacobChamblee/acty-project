package com.acty.bluetooth

/**
 * PidRegistry.kt
 * Direct port of PID_REGISTRY from acty_obd_capture.py.
 * Format: name -> PidDef(modePid, description, unit, decoder)
 */
data class PidDef(
    val modePid: String,          // e.g. "010C"
    val description: String,
    val unit: String,
    val decoder: (ByteArray) -> Double?
)

object PidRegistry {

    // ── Decoders ──────────────────────────────────────────────────────────────

    private fun pctA(d: ByteArray)       = if (d.isEmpty()) null else (d[0].toUByte().toDouble() * 100.0 / 255.0).round(1)
    private fun temp(d: ByteArray)       = if (d.isEmpty()) null else (d[0].toUByte().toDouble() - 40.0)
    private fun rpm(d: ByteArray)        = if (d.size < 2) null else ((d[0].toUByte().toInt() * 256 + d[1].toUByte().toInt()) / 4.0).round(1)
    private fun speed(d: ByteArray)      = if (d.isEmpty()) null else d[0].toUByte().toDouble()
    private fun fuelTrim(d: ByteArray)   = if (d.isEmpty()) null else ((d[0].toUByte().toDouble() - 128.0) * 100.0 / 128.0).round(2)
    private fun timing(d: ByteArray)     = if (d.isEmpty()) null else (d[0].toUByte().toDouble() / 2.0 - 64.0).round(1)
    private fun mapKpa(d: ByteArray)     = if (d.isEmpty()) null else d[0].toUByte().toDouble()
    private fun maf(d: ByteArray)        = if (d.size < 2) null else ((d[0].toUByte().toInt() * 256 + d[1].toUByte().toInt()) / 100.0).round(2)
    private fun battery(d: ByteArray)    = if (d.size < 2) null else ((d[0].toUByte().toInt() * 256 + d[1].toUByte().toInt()) / 1000.0).round(2)
    private fun distance(d: ByteArray)   = if (d.size < 2) null else (d[0].toUByte().toInt() * 256 + d[1].toUByte().toInt()).toDouble()
    private fun runtime(d: ByteArray)    = if (d.size < 2) null else (d[0].toUByte().toInt() * 256 + d[1].toUByte().toInt()).toDouble()
    private fun barometric(d: ByteArray) = if (d.isEmpty()) null else d[0].toUByte().toDouble()
    private fun catalystTemp(d: ByteArray) = if (d.size < 2) null else ((d[0].toUByte().toInt() * 256 + d[1].toUByte().toInt()) / 10.0 - 40.0).round(1)
    private fun pctAb(d: ByteArray)      = if (d.size < 2) null else ((d[0].toUByte().toInt() * 256 + d[1].toUByte().toInt()).toDouble() * 100.0 / 65535.0).round(2)
    private fun equivRatio(d: ByteArray) = if (d.size < 2) null else ((d[0].toUByte().toInt() * 256 + d[1].toUByte().toInt()) / 32768.0).round(4)
    private fun accelPedal(d: ByteArray) = if (d.isEmpty()) null else (d[0].toUByte().toDouble() * 100.0 / 255.0).round(1)
    private fun warmups(d: ByteArray)    = if (d.isEmpty()) null else d[0].toUByte().toDouble()
    private fun evapPurge(d: ByteArray)  = if (d.isEmpty()) null else (d[0].toUByte().toDouble() * 100.0 / 255.0).round(1)
    private fun egr(d: ByteArray)        = if (d.isEmpty()) null else (d[0].toUByte().toDouble() * 100.0 / 255.0).round(1)
    private fun o2Voltage(d: ByteArray)  = if (d.isEmpty()) null else (d[0].toUByte().toDouble() / 200.0).round(3)
    private fun fuelLevel(d: ByteArray)  = if (d.isEmpty()) null else (d[0].toUByte().toDouble() * 100.0 / 255.0).round(1)
    private fun odometer(d: ByteArray)   = if (d.size < 4) null else {
        val raw = (d[0].toUByte().toInt() shl 24) or (d[1].toUByte().toInt() shl 16) or
                  (d[2].toUByte().toInt() shl 8)  or d[3].toUByte().toInt()
        (raw / 10.0).round(1)
    }

    private fun Double.round(places: Int): Double {
        val factor = Math.pow(10.0, places.toDouble())
        return Math.round(this * factor) / factor
    }

    // ── Registry ──────────────────────────────────────────────────────────────

    val ALL: Map<String, PidDef> = mapOf(
        "ENGINE_LOAD"         to PidDef("0104", "Calculated engine load",            "%",    ::pctA),
        "COOLANT_TEMP"        to PidDef("0105", "Engine coolant temperature",        "°C",   ::temp),
        "SHORT_FUEL_TRIM_1"   to PidDef("0106", "Short term fuel trim — bank 1",     "%",    ::fuelTrim),
        "LONG_FUEL_TRIM_1"    to PidDef("0107", "Long term fuel trim — bank 1",      "%",    ::fuelTrim),
        "SHORT_FUEL_TRIM_2"   to PidDef("0108", "Short term fuel trim — bank 2",     "%",    ::fuelTrim),
        "LONG_FUEL_TRIM_2"    to PidDef("0109", "Long term fuel trim — bank 2",      "%",    ::fuelTrim),
        "INTAKE_MAP"          to PidDef("010B", "Intake manifold pressure",          "kPa",  ::mapKpa),
        "RPM"                 to PidDef("010C", "Engine RPM",                        "rpm",  ::rpm),
        "SPEED"               to PidDef("010D", "Vehicle speed",                     "km/h", ::speed),
        "TIMING_ADVANCE"      to PidDef("010E", "Ignition timing advance",           "°",    ::timing),
        "INTAKE_TEMP"         to PidDef("010F", "Intake air temperature",            "°C",   ::temp),
        "MAF"                 to PidDef("0110", "MAF air flow rate",                 "g/s",  ::maf),
        "THROTTLE_POS"        to PidDef("0111", "Absolute throttle position",        "%",    ::pctA),
        "O2_B1S1_V"           to PidDef("0114", "O2 sensor B1S1 voltage",            "V",    ::o2Voltage),
        "O2_B1S2_V"           to PidDef("0115", "O2 sensor B1S2 voltage",            "V",    ::o2Voltage),
        "WARMUPS_SINCE_CLEAR" to PidDef("0130", "Warm-ups since codes cleared",      "",     ::warmups),
        "DIST_SINCE_CLEAR"    to PidDef("0131", "Distance since codes cleared",      "km",   ::distance),
        "FUEL_LEVEL"          to PidDef("012F", "Fuel tank level",                   "%",    ::fuelLevel),
        "EVAP_PURGE"          to PidDef("012E", "Commanded evap purge",              "%",    ::evapPurge),
        "BAROMETRIC"          to PidDef("0133", "Barometric pressure",               "kPa",  ::barometric),
        "CATALYST_TEMP_B1S1"  to PidDef("013C", "Catalyst temp B1S1",               "°C",   ::catalystTemp),
        "CATALYST_TEMP_B1S2"  to PidDef("013E", "Catalyst temp B1S2",               "°C",   ::catalystTemp),
        "CONTROL_VOLTAGE"     to PidDef("0142", "Control module voltage",            "V",    ::battery),
        "ABS_LOAD"            to PidDef("0143", "Absolute load value",               "%",    ::pctAb),
        "COMMANDED_EQUIV_RATIO" to PidDef("0144", "Commanded equivalence ratio",     "λ",    ::equivRatio),
        "REL_THROTTLE_POS"    to PidDef("0145", "Relative throttle position",        "%",    ::pctA),
        "AMBIENT_TEMP"        to PidDef("0146", "Ambient air temperature",           "°C",   ::temp),
        "ACCEL_PEDAL_D"       to PidDef("0149", "Accelerator pedal position D",      "%",    ::accelPedal),
        "THROTTLE_ACTUATOR"   to PidDef("014C", "Commanded throttle actuator",       "%",    ::accelPedal),
        "ENGINE_RUNTIME"      to PidDef("011F", "Time since engine start",           "s",    ::runtime),
        "EGR_COMMANDED"       to PidDef("012C", "Commanded EGR",                     "%",    ::egr),
        "ODOMETER"            to PidDef("01A6", "Odometer",                          "km",   ::odometer),
        "O2_WB_B1S1_LAMBDA"   to PidDef("0124", "O2 wideband B1S1 equiv ratio",      "λ",   { d ->
            if (d.size < 2) null else ((d[0].toUByte().toInt() * 256 + d[1].toUByte().toInt()) / 32768.0).round(4)
        }),
        "PM_SENSOR_B1"        to PidDef("0187", "PM sensor bank 1",                 "mg/m³", { d ->
            if (d.size < 3) null else (d[1].toUByte().toInt() * 256 + d[2].toUByte().toInt()).toDouble()
        }),
    )

    // Default set for --no-probe equivalent
    val DEFAULT_PIDS = listOf(
        "RPM", "SPEED", "COOLANT_TEMP", "ENGINE_LOAD", "THROTTLE_POS",
        "INTAKE_TEMP", "MAF", "SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1",
        "TIMING_ADVANCE", "INTAKE_MAP", "FUEL_LEVEL", "CONTROL_VOLTAGE"
    )
}
