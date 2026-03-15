#!/usr/bin/env python3
"""
acty_obd.py  (v3 — expanded PID registry + auto-probe)
-------------------------------------------------------
OBD-II PID reader for the VeePeak OBDCheck BLE dongle on Linux Mint.
Connects via classic Bluetooth RFCOMM serial (SPP profile) + ELM327 AT commands.

By default, probes the vehicle's supported PIDs first, then polls everything
your car actually supports — maximizing data capture automatically.

Usage:
    python3 acty_obd.py                              # probe + poll all supported PIDs
    python3 acty_obd.py --address 8C:DE:52:D9:7E:D1 # connect directly (skip scan)
    python3 acty_obd.py --pids RPM,SPEED,MAF        # poll specific PIDs only
    python3 acty_obd.py --no-probe                   # skip probe, use default set
    python3 acty_obd.py --interval 0.5               # faster polling
    python3 acty_obd.py --format json                # JSON output
    python3 acty_obd.py --no-log                     # terminal only, no file
    python3 acty_obd.py --dtc                        # read trouble codes and exit
    python3 acty_obd.py --list-pids                  # show full PID registry
"""

import argparse
import csv
import json
import re
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ─── DECODERS ────────────────────────────────────────────────────────────────

def _pct_a(data):
    """A * 100 / 255  →  percentage"""
    if len(data) < 1: return None
    return round(data[0] * 100 / 255, 1)

def _pct_ab(data):
    """(256A + B) * 100 / 65535  →  percentage (2-byte)"""
    if len(data) < 2: return None
    return round(((data[0] * 256) + data[1]) * 100 / 65535, 2)

def _temp(data):
    """A - 40  →  °C"""
    if len(data) < 1: return None
    return data[0] - 40

def _rpm(data):
    """(256A + B) / 4  →  RPM"""
    if len(data) < 2: return None
    return round(((data[0] * 256) + data[1]) / 4.0, 1)

def _speed(data):
    """A  →  km/h"""
    if len(data) < 1: return None
    return data[0]

def _fuel_trim(data):
    """(A - 128) * 100 / 128  →  %"""
    if len(data) < 1: return None
    return round((data[0] - 128) * 100 / 128, 2)

def _timing(data):
    """A/2 - 64  →  ° BTDC"""
    if len(data) < 1: return None
    return round(data[0] / 2 - 64, 1)

def _map_kpa(data):
    """A  →  kPa"""
    if len(data) < 1: return None
    return data[0]

def _maf(data):
    """(256A + B) / 100  →  g/s"""
    if len(data) < 2: return None
    return round(((data[0] * 256) + data[1]) / 100.0, 2)

def _fuel_pressure(data):
    """A * 3  →  kPa gauge"""
    if len(data) < 1: return None
    return data[0] * 3

def _fuel_pressure_abs(data):
    """(256A + B) * 0.079  →  kPa absolute"""
    if len(data) < 2: return None
    return round(((data[0] * 256) + data[1]) * 0.079, 1)

def _fuel_rail_pressure(data):
    """(256A + B) * 10  →  kPa gauge"""
    if len(data) < 2: return None
    return ((data[0] * 256) + data[1]) * 10

def _fuel_rail_pressure_abs(data):
    """(256A + B) * 10  →  kPa absolute"""
    if len(data) < 2: return None
    return ((data[0] * 256) + data[1]) * 10

def _o2_voltage(data):
    """A / 200  →  V"""
    if len(data) < 1: return None
    return round(data[0] / 200.0, 3)

def _o2_trim(data):
    """B: (B - 128) * 100 / 128  →  %  (A = voltage)"""
    if len(data) < 2: return None
    return round((data[1] - 128) * 100 / 128, 2)

def _o2_wideband_lambda(data):
    """(256A + B) / 32768  →  lambda ratio"""
    if len(data) < 2: return None
    return round(((data[0] * 256) + data[1]) / 32768.0, 4)

def _o2_wideband_current(data):
    """(256C + D) / 256 - 128  →  mA"""
    if len(data) < 4: return None
    return round(((data[2] * 256) + data[3]) / 256 - 128, 3)

def _battery(data):
    """(256A + B) / 1000  →  V"""
    if len(data) < 2: return None
    return round(((data[0] * 256) + data[1]) / 1000.0, 2)

def _distance(data):
    """(256A + B)  →  km"""
    if len(data) < 2: return None
    return (data[0] * 256) + data[1]

def _runtime(data):
    """(256A + B)  →  seconds"""
    if len(data) < 2: return None
    return (data[0] * 256) + data[1]

def _evap_pressure(data):
    """(256A + B) / 4 - 8192  →  Pa"""
    if len(data) < 2: return None
    return round(((data[0] * 256) + data[1]) / 4 - 8192, 1)

def _barometric(data):
    """A  →  kPa"""
    if len(data) < 1: return None
    return data[0]

def _catalyst_temp(data):
    """(256A + B) / 10 - 40  →  °C"""
    if len(data) < 2: return None
    return round(((data[0] * 256) + data[1]) / 10 - 40, 1)

def _equiv_ratio(data):
    """(256A + B) / 32768  →  lambda"""
    if len(data) < 2: return None
    return round(((data[0] * 256) + data[1]) / 32768.0, 4)

def _fuel_system_status(data):
    """Fuel system A status byte → human label"""
    if len(data) < 1: return None
    status_map = {
        0x01: "OL",           # Open loop - insufficient temp
        0x02: "CL",           # Closed loop - O2 sensor
        0x04: "OL-Drive",     # Open loop - load/decel
        0x08: "OL-Fault",     # Open loop - system fault
        0x10: "CL-Fault",     # Closed loop - O2 sensor fault
    }
    return status_map.get(data[0], f"0x{data[0]:02X}")

def _egr_pct(data):
    """A * 100 / 255  →  % commanded EGR"""
    if len(data) < 1: return None
    return round(data[0] * 100 / 255, 1)

def _egr_error(data):
    """B: (B - 128) * 100 / 128  →  % EGR error"""
    if len(data) < 2: return None
    return round((data[1] - 128) * 100 / 128, 2)

def _evap_purge(data):
    """A * 100 / 255  →  % commanded evap purge"""
    if len(data) < 1: return None
    return round(data[0] * 100 / 255, 1)

def _warmups(data):
    if len(data) < 1: return None
    return data[0]

def _accel_pedal(data):
    """A * 100 / 255  →  %"""
    if len(data) < 1: return None
    return round(data[0] * 100 / 255, 1)

def _throttle_actuator(data):
    """A * 100 / 255  →  %"""
    if len(data) < 1: return None
    return round(data[0] * 100 / 255, 1)

def _fuel_type(data):
    fuel_types = {
        0: "N/A", 1: "Gasoline", 2: "Methanol", 3: "Ethanol",
        4: "Diesel", 5: "LPG", 6: "CNG", 7: "Propane",
        8: "Electric", 9: "Bifuel Gas", 10: "Bifuel Methanol",
        11: "Bifuel Ethanol", 12: "Bifuel LPG", 13: "Bifuel CNG",
        14: "Bifuel Propane", 15: "Bifuel Electric",
        16: "Bifuel Gas/Electric", 17: "Hybrid Gas",
        18: "Hybrid Ethanol", 19: "Hybrid Diesel",
        20: "Hybrid Electric", 21: "Hybrid Mixed",
        22: "Hybrid Regen",
    }
    if len(data) < 1: return None
    return fuel_types.get(data[0], f"Unknown({data[0]})")

def _ethanol_pct(data):
    """A * 100 / 255  →  %"""
    if len(data) < 1: return None
    return round(data[0] * 100 / 255, 1)

def _abs_map(data):
    """(256A + B) * 10 / 256  →  kPa absolute"""
    if len(data) < 2: return None
    return round(((data[0] * 256) + data[1]) * 10 / 256, 1)

def _engine_friction(data):
    """(A - 125) * 100 / 255  →  %  (relative torque)"""
    if len(data) < 1: return None
    return round((data[0] - 125) * 100 / 255, 1)

def _driver_torque(data):
    """A - 125  →  %  (driver demanded torque)"""
    if len(data) < 1: return None
    return data[0] - 125

def _actual_torque(data):
    """A - 125  →  %"""
    if len(data) < 1: return None
    return data[0] - 125

def _ref_torque(data):
    """(256A + B)  →  Nm reference torque"""
    if len(data) < 2: return None
    return (data[0] * 256) + data[1]

def _boost_pressure(data):
    """(256A + B) * 0.03125  →  kPa  (sensor A commanded)"""
    if len(data) < 2: return None
    return round(((data[0] * 256) + data[1]) * 0.03125, 2)

def _vgt_pct(data):
    """Commanded VGT position %"""
    if len(data) < 1: return None
    return round(data[0] * 100 / 255, 1)

def _injection_timing(data):
    """(256A + B) / 128 - 210  →  ° crank"""
    if len(data) < 2: return None
    return round(((data[0] * 256) + data[1]) / 128 - 210, 2)

def _fuel_rate(data):
    """(256A + B) * 0.05  →  L/h"""
    if len(data) < 2: return None
    return round(((data[0] * 256) + data[1]) * 0.05, 2)

def _exhaust_flow(data):
    """(256A + B)  →  kg/h"""
    if len(data) < 2: return None
    return (data[0] * 256) + data[1]

def _odometer(data):
    """(A*2^24 + B*2^16 + C*2^8 + D) / 10  →  km"""
    if len(data) < 4: return None
    raw = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3]
    return round(raw / 10.0, 1)

def _trans_actual_gear(data):
    """B / 1000  →  gear ratio"""
    if len(data) < 2: return None
    return round(data[1] / 1000.0, 3)

def _trans_commanded_gear(data):
    """B: commanded gear"""
    if len(data) < 2: return None
    return data[1]

# ─── PID REGISTRY ────────────────────────────────────────────────────────────
# Format: name -> (mode_pid_hex, description, unit, decoder_fn)
# Organized by OBD-II PID number order (Mode 01 only for live data)

PID_REGISTRY = {
    # ── Monitor / system status ─────────────────────────────────────────────
    "FUEL_SYSTEM_STATUS":     ("0103", "Fuel system status",                     "",       _fuel_system_status),
    "ENGINE_LOAD":            ("0104", "Calculated engine load",                 "%",      _pct_a),
    "COOLANT_TEMP":           ("0105", "Engine coolant temperature",             "°C",     _temp),
    "SHORT_FUEL_TRIM_1":      ("0106", "Short term fuel trim — bank 1",          "%",      _fuel_trim),
    "LONG_FUEL_TRIM_1":       ("0107", "Long term fuel trim — bank 1",           "%",      _fuel_trim),
    "SHORT_FUEL_TRIM_2":      ("0108", "Short term fuel trim — bank 2",          "%",      _fuel_trim),
    "LONG_FUEL_TRIM_2":       ("0109", "Long term fuel trim — bank 2",           "%",      _fuel_trim),
    "FUEL_PRESSURE":          ("010A", "Fuel pressure (gauge)",                  "kPa",    _fuel_pressure),
    "INTAKE_MAP":             ("010B", "Intake manifold absolute pressure",       "kPa",    _map_kpa),
    "RPM":                    ("010C", "Engine RPM",                             "rpm",    _rpm),
    "SPEED":                  ("010D", "Vehicle speed",                          "km/h",   _speed),
    "TIMING_ADVANCE":         ("010E", "Ignition timing advance",                "°",      _timing),
    "INTAKE_TEMP":            ("010F", "Intake air temperature",                 "°C",     _temp),
    "MAF":                    ("0110", "MAF air flow rate",                      "g/s",    _maf),
    "THROTTLE_POS":           ("0111", "Absolute throttle position",             "%",      _pct_a),
    # ── Commanded / secondary throttle ────────────────────────────────────────
    "SEC_AIR_STATUS":         ("0112", "Commanded secondary air status",         "",       lambda d: {0x01:"Upstream",0x02:"Downstream",0x04:"Atmosphere",0x08:"Pump Off"}.get(d[0] if d else 0, "?")),
    "THROTTLE_POS_B":         ("0117", "Absolute throttle position B",           "%",      _pct_a),
    "THROTTLE_POS_C":         ("0118", "Absolute throttle position C",           "%",      _pct_a),
    "ACCEL_PEDAL_D":          ("0149", "Accelerator pedal position D",           "%",      _accel_pedal),
    "ACCEL_PEDAL_E":          ("014A", "Accelerator pedal position E",           "%",      _accel_pedal),
    "ACCEL_PEDAL_F":          ("014B", "Accelerator pedal position F",           "%",      _accel_pedal),
    "THROTTLE_ACTUATOR":      ("014C", "Commanded throttle actuator",            "%",      _throttle_actuator),
    # ── O2 sensors — narrow band (voltage) ───────────────────────────────────
    "O2_B1S1_V":              ("0114", "O2 sensor B1S1 voltage",                 "V",      _o2_voltage),
    "O2_B1S1_TRIM":           ("0114", "O2 sensor B1S1 short trim",              "%",      _o2_trim),
    "O2_B1S2_V":              ("0115", "O2 sensor B1S2 voltage",                 "V",      _o2_voltage),
    "O2_B1S2_TRIM":           ("0115", "O2 sensor B1S2 short trim",              "%",      _o2_trim),
    "O2_B2S1_V":              ("0118", "O2 sensor B2S1 voltage",                 "V",      _o2_voltage),
    "O2_B2S2_V":              ("0119", "O2 sensor B2S2 voltage",                 "V",      _o2_voltage),
    # ── O2 sensors — wide band (lambda + current) ────────────────────────────
    "O2_WB_B1S1_LAMBDA":      ("0124", "O2 wideband B1S1 equiv ratio",           "λ",      _o2_wideband_lambda),
    "O2_WB_B1S1_MA":          ("0124", "O2 wideband B1S1 current",               "mA",     _o2_wideband_current),
    "O2_WB_B1S2_LAMBDA":      ("0125", "O2 wideband B1S2 equiv ratio",           "λ",      _o2_wideband_lambda),
    "O2_WB_B2S1_LAMBDA":      ("0128", "O2 wideband B2S1 equiv ratio",           "λ",      _o2_wideband_lambda),
    "O2_WB_B2S2_LAMBDA":      ("0129", "O2 wideband B2S2 equiv ratio",           "λ",      _o2_wideband_lambda),
    # ── Fuel rail ─────────────────────────────────────────────────────────────
    "FUEL_RAIL_PRESSURE_VAC": ("0122", "Fuel rail pressure (vac referenced)",    "kPa",    _fuel_rail_pressure),
    "FUEL_RAIL_PRESSURE_WOT": ("0123", "Fuel rail pressure (WOT)",               "kPa",    _fuel_rail_pressure_abs),
    "FUEL_RAIL_ABS_PRESSURE": ("012A", "Fuel rail absolute pressure",            "kPa",    lambda d: ((d[0]*256)+d[1])*10 if len(d)>=2 else None),
    # ── EGR ──────────────────────────────────────────────────────────────────
    "EGR_COMMANDED":          ("012C", "Commanded EGR",                          "%",      _egr_pct),
    "EGR_ERROR":              ("012D", "EGR error",                              "%",      _egr_error),
    # ── Evap ──────────────────────────────────────────────────────────────────
    "EVAP_PURGE":             ("012E", "Commanded evap purge",                   "%",      _evap_purge),
    "FUEL_LEVEL":             ("012F", "Fuel tank level",                        "%",      _pct_a),
    "EVAP_VAPOR_PRESSURE":    ("0132", "Evap system vapor pressure",             "Pa",     _evap_pressure),
    # ── Since last clear ──────────────────────────────────────────────────────
    "WARMUPS_SINCE_CLEAR":    ("0130", "Warm-ups since codes cleared",           "count",  _warmups),
    "DIST_SINCE_CLEAR":       ("0131", "Distance since codes cleared",           "km",     _distance),
    "BAROMETRIC":             ("0133", "Barometric pressure",                    "kPa",    _barometric),
    # ── Catalyst ──────────────────────────────────────────────────────────────
    "CATALYST_TEMP_B1S1":     ("013C", "Catalyst temp B1S1",                    "°C",     _catalyst_temp),
    "CATALYST_TEMP_B2S1":     ("013D", "Catalyst temp B2S1",                    "°C",     _catalyst_temp),
    "CATALYST_TEMP_B1S2":     ("013E", "Catalyst temp B1S2",                    "°C",     _catalyst_temp),
    "CATALYST_TEMP_B2S2":     ("013F", "Catalyst temp B2S2",                    "°C",     _catalyst_temp),
    # ── Electrical / module ───────────────────────────────────────────────────
    "CONTROL_VOLTAGE":        ("0142", "Control module voltage",                 "V",      _battery),
    "ABS_LOAD":               ("0143", "Absolute load value",                    "%",      _pct_ab),
    "COMMANDED_EQUIV_RATIO":  ("0144", "Commanded equivalence ratio",            "λ",      _equiv_ratio),
    "REL_THROTTLE_POS":       ("0145", "Relative throttle position",             "%",      _pct_a),
    "AMBIENT_TEMP":           ("0146", "Ambient air temperature",                "°C",     _temp),
    "ABS_THROTTLE_POS_B":     ("0147", "Absolute throttle position B",           "%",      _pct_a),
    "ABS_THROTTLE_POS_C":     ("0148", "Absolute throttle position C",           "%",      _pct_a),
    # ── Run time / distance with MIL ─────────────────────────────────────────
    "RUN_TIME":               ("011F", "Engine run time",                        "s",      _runtime),
    "DIST_WITH_MIL":          ("0121", "Distance traveled with MIL on",          "km",     _distance),
    "TIME_WITH_MIL":          ("014D", "Time run with MIL on",                   "min",    _runtime),
    "TIME_SINCE_CLEAR":       ("014E", "Time since trouble codes cleared",        "min",    _runtime),
    # ── Fuel type / ethanol ───────────────────────────────────────────────────
    "FUEL_TYPE":              ("0151", "Fuel type",                              "",       _fuel_type),
    "ETHANOL_PCT":            ("0152", "Ethanol fuel percentage",                "%",      _ethanol_pct),
    # ── Absolute evap / O2 sensor ─────────────────────────────────────────────
    "EVAP_VAPOR_PRESSURE_ABS":("0153", "Evap system vapor pressure (abs)",       "kPa",    lambda d: round(((d[0]*256)+d[1])/200,3) if len(d)>=2 else None),
    "EVAP_VAPOR_PRESSURE_ALT":("0154", "Evap system vapor pressure (alt)",       "Pa",     lambda d: ((d[0]*256)+d[1])*0.005 if len(d)>=2 else None),
    # ── Short/long O2 sensor trim ─────────────────────────────────────────────
    "O2_SHORT_TRIM_B1":       ("0155", "Short term O2 trim B1",                  "%",      _fuel_trim),
    "O2_LONG_TRIM_B1":        ("0156", "Long term O2 trim B1",                   "%",      _fuel_trim),
    "O2_SHORT_TRIM_B2":       ("0157", "Short term O2 trim B2",                  "%",      _fuel_trim),
    "O2_LONG_TRIM_B2":        ("0158", "Long term O2 trim B2",                   "%",      _fuel_trim),
    # ── Fuel rail pressure (abs, wide range) ─────────────────────────────────
    "FUEL_RAIL_ABS_WIDE":     ("0159", "Fuel rail abs pressure (wide range)",    "kPa",    lambda d: ((d[0]*256)+d[1])*10 if len(d)>=2 else None),
    # ── Relative / relative accel ─────────────────────────────────────────────
    "REL_ACCEL_POS":          ("015A", "Relative accelerator pedal position",    "%",      _pct_a),
    "HYBRID_BATTERY_PCT":     ("015B", "Hybrid battery pack remaining life",     "%",      _pct_a),
    "ENGINE_OIL_TEMP":        ("015C", "Engine oil temperature",                 "°C",     _temp),
    "INJECTION_TIMING":       ("015D", "Fuel injection timing",                  "°",      _injection_timing),
    "FUEL_RATE":              ("015E", "Engine fuel rate",                        "L/h",    _fuel_rate),
    # ── Torque (SAE J1979-DA) ─────────────────────────────────────────────────
    "ENGINE_TORQUE_PCT":           ("0162", "Actual engine torque (% ref)",              "%",    _actual_torque),
    "ENGINE_REF_TORQUE":           ("0163", "Engine reference torque",                   "Nm",   _ref_torque),
    "ENGINE_PCT_TORQUE_B1":        ("0164", "Engine % torque at idle point 1",           "%",    lambda d: d[0]-125 if d else None),
    "ENGINE_PCT_TORQUE_B2":        ("0164", "Engine % torque at point 2",                "%",    lambda d: d[1]-125 if len(d)>1 else None),
    "ENGINE_PCT_TORQUE_B3":        ("0164", "Engine % torque at point 3",                "%",    lambda d: d[2]-125 if len(d)>2 else None),
    "ENGINE_PCT_TORQUE_B4":        ("0164", "Engine % torque at point 4",                "%",    lambda d: d[3]-125 if len(d)>3 else None),
    "DRIVER_TORQUE_PCT":           ("016D", "Driver demand engine torque (%)",           "%",    _driver_torque),
    # ── Auxiliary I/O ──────────────────────────────────────────────────────────
    "AUX_INPUT":                   ("016E", "Auxiliary input/output supported",          "",     lambda d: f"0x{d[0]:02X}" if d else None),
    # ── Mass air flow sensor ───────────────────────────────────────────────────
    "MAF_SENSOR_A":                ("0166", "Mass air flow sensor A",                   "g/s",  lambda d: round(((d[1]*256)+d[2])/32,2) if len(d)>=3 else None),
    "MAF_SENSOR_B":                ("0166", "Mass air flow sensor B",                   "g/s",  lambda d: round(((d[3]*256)+d[4])/32,2) if len(d)>=5 else None),
    # ── Exhaust gas recirculation temperature ──────────────────────────────────
    "EGR_TEMP_A":                  ("0168", "EGR temperature bank 1 sensor 1",          "°C",   lambda d: d[1]-40 if len(d)>1 else None),
    "EGR_TEMP_B":                  ("0168", "EGR temperature bank 1 sensor 2",          "°C",   lambda d: d[2]-40 if len(d)>2 else None),
    # ── Commanded diesel / throttle valve ──────────────────────────────────────
    "THROTTLE_VALVE_A":            ("016A", "Commanded throttle valve A",               "%",    lambda d: round(d[1]*100/255,1) if len(d)>1 else None),
    "THROTTLE_VALVE_B":            ("016A", "Commanded throttle valve B",               "%",    lambda d: round(d[3]*100/255,1) if len(d)>3 else None),
    # ── Fuel pressure control ──────────────────────────────────────────────────
    "FUEL_PRESSURE_CTRL_A":        ("016C", "Fuel pressure control system A",          "kPa",  lambda d: ((d[1]*256)+d[2])*0.03125 if len(d)>=3 else None),
    "FUEL_PRESSURE_CTRL_B":        ("016C", "Fuel pressure control system B",          "kPa",  lambda d: ((d[4]*256)+d[5])*0.03125 if len(d)>=6 else None),
    # ── Injection pressure control ─────────────────────────────────────────────
    "INJECTION_CTRL_PRESSURE_A":   ("016D", "Injection control pressure A",            "kPa",  lambda d: ((d[1]*256)+d[2])*0.03125 if len(d)>=3 else None),
    # ── Turbocharger / compressor ──────────────────────────────────────────────
    "TURBO_RPM_A":                 ("016F", "Turbocharger RPM A",                      "rpm",  lambda d: ((d[1]*256)+d[2])*64 if len(d)>=3 else None),
    "TURBO_RPM_B":                 ("016F", "Turbocharger RPM B",                      "rpm",  lambda d: ((d[3]*256)+d[4])*64 if len(d)>=5 else None),
    "TURBO_INLET_TEMP_A":          ("0171", "Turbocharger inlet temperature A",        "°C",   lambda d: d[1]-40 if len(d)>1 else None),
    "TURBO_INLET_TEMP_B":          ("0171", "Turbocharger inlet temperature B",        "°C",   lambda d: d[3]-40 if len(d)>3 else None),
    "CHARGE_AIR_COOLER_TEMP_A":    ("0172", "Charge air cooler temperature A",         "°C",   lambda d: d[1]-40 if len(d)>1 else None),
    "CHARGE_AIR_COOLER_TEMP_B":    ("0172", "Charge air cooler temperature B",         "°C",   lambda d: d[3]-40 if len(d)>3 else None),
    # ── Exhaust gas temperature (EGT) ─────────────────────────────────────────
    "EGT_BANK1_S1":                ("0173", "Exhaust gas temp bank 1 sensor 1",        "°C",   lambda d: round(((d[1]*256)+d[2])*0.1-40,1) if len(d)>=3 else None),
    "EGT_BANK1_S2":                ("0173", "Exhaust gas temp bank 1 sensor 2",        "°C",   lambda d: round(((d[3]*256)+d[4])*0.1-40,1) if len(d)>=5 else None),
    "EGT_BANK1_S3":                ("0173", "Exhaust gas temp bank 1 sensor 3",        "°C",   lambda d: round(((d[5]*256)+d[6])*0.1-40,1) if len(d)>=7 else None),
    "EGT_BANK1_S4":                ("0173", "Exhaust gas temp bank 1 sensor 4",        "°C",   lambda d: round(((d[7]*256)+d[8])*0.1-40,1) if len(d)>=9 else None),
    "EGT_BANK2_S1":                ("0174", "Exhaust gas temp bank 2 sensor 1",        "°C",   lambda d: round(((d[1]*256)+d[2])*0.1-40,1) if len(d)>=3 else None),
    "EGT_BANK2_S2":                ("0174", "Exhaust gas temp bank 2 sensor 2",        "°C",   lambda d: round(((d[3]*256)+d[4])*0.1-40,1) if len(d)>=5 else None),
    # ── Diesel particulate filter (DPF) ────────────────────────────────────────
    "DPF_PRESSURE_A":              ("0175", "DPF differential pressure A",             "kPa",  lambda d: round(((d[1]*256)+d[2])*0.03125,3) if len(d)>=3 else None),
    "DPF_PRESSURE_B":              ("0175", "DPF differential pressure B",             "kPa",  lambda d: round(((d[3]*256)+d[4])*0.03125,3) if len(d)>=5 else None),
    "DPF_TEMP_INLET_A":            ("0176", "DPF inlet temperature bank 1",            "°C",   lambda d: round(((d[1]*256)+d[2])*0.1-40,1) if len(d)>=3 else None),
    "DPF_TEMP_OUTLET_A":           ("0176", "DPF outlet temperature bank 1",           "°C",   lambda d: round(((d[3]*256)+d[4])*0.1-40,1) if len(d)>=5 else None),
    # ── NOx sensor ────────────────────────────────────────────────────────────
    "NOX_SENSOR_B1S1":             ("0183", "NOx sensor concentration B1S1",          "ppm",  lambda d: ((d[1]*256)+d[2]) if len(d)>=3 else None),
    "NOX_SENSOR_B1S2":             ("0183", "NOx sensor concentration B1S2",          "ppm",  lambda d: ((d[3]*256)+d[4]) if len(d)>=5 else None),
    "NOX_SENSOR_B2S1":             ("0183", "NOx sensor concentration B2S1",          "ppm",  lambda d: ((d[5]*256)+d[6]) if len(d)>=7 else None),
    "NOX_SENSOR_B2S2":             ("0183", "NOx sensor concentration B2S2",          "ppm",  lambda d: ((d[7]*256)+d[8]) if len(d)>=9 else None),
    # ── Manifold surface temperature ───────────────────────────────────────────
    "MANIFOLD_SURFACE_TEMP":       ("0184", "Manifold surface temperature",            "°C",   lambda d: round(((d[0]*256)+d[1])*0.03125-273,1) if len(d)>=2 else None),
    # ── NOx reagent (SCR / AdBlue) ────────────────────────────────────────────
    "NOX_REAGENT_SYSTEM":          ("0185", "NOx reagent system",                      "",     lambda d: f"0x{d[0]:02X}" if d else None),
    "NOX_REAGENT_PCT":             ("0186", "NOx reagent concentration",               "%",    lambda d: round(d[0]*100/255,1) if d else None),
    # ── Particulate matter / PM sensor ────────────────────────────────────────
    "PM_SENSOR_B1":                ("0187", "PM sensor bank 1",                        "mg/m³",lambda d: ((d[1]*256)+d[2]) if len(d)>=3 else None),
    "PM_SENSOR_B2":                ("0187", "PM sensor bank 2",                        "mg/m³",lambda d: ((d[3]*256)+d[4]) if len(d)>=5 else None),
    # ── Intake manifold abs pressure ──────────────────────────────────────────
    "INTAKE_MAP_WIDE_A":           ("0188", "Intake manifold absolute pressure (wide) A","kPa",lambda d: round(((d[1]*256)+d[2])*0.03125,2) if len(d)>=3 else None),
    "INTAKE_MAP_WIDE_B":           ("0188", "Intake manifold absolute pressure (wide) B","kPa",lambda d: round(((d[3]*256)+d[4])*0.03125,2) if len(d)>=5 else None),
    # ── SCR induce system ─────────────────────────────────────────────────────
    "SCR_INDUCE_SYSTEM":           ("0189", "SCR induce system",                       "",     lambda d: f"0x{d[0]:02X}" if d else None),
    # ── Aftertreatment system ─────────────────────────────────────────────────
    "AFTRTRMT_1_STATUS":           ("018A", "Run time for AECD #1-#5",                 "s",    lambda d: (d[0]<<24|d[1]<<16|d[2]<<8|d[3]) if len(d)>=4 else None),
    # ── Transmission ──────────────────────────────────────────────────────────
    "TRANS_ACTUAL_GEAR":           ("01A4", "Actual transmission gear ratio",          ":1",   lambda d: round(((d[2]*256)+d[3])/1000,3) if len(d)>=4 else None),
    "TRANS_COMMANDED_GEAR":        ("01A4", "Commanded transmission gear",             "",     lambda d: d[1] if len(d)>1 else None),
    "DIESEL_EXHAUST_FLUID_PCT":    ("01A5", "Diesel exhaust fluid sensor data",        "%",    lambda d: round(d[0]*100/255,1) if d else None),
    # ── Odometer ─────────────────────────────────────────────────────────────
    "ODOMETER":                    ("01A6", "Odometer",                                "km",   _odometer),
}

# Default set if user runs with --no-probe
DEFAULT_PIDS = [
    "RPM", "SPEED", "COOLANT_TEMP", "ENGINE_LOAD", "THROTTLE_POS",
    "INTAKE_TEMP", "MAF", "SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1",
    "TIMING_ADVANCE", "INTAKE_MAP", "FUEL_LEVEL",
]

# ─── BLUETOOTH CONNECTION ─────────────────────────────────────────────────────

RFCOMM_CHANNEL = 1

def bt_connect(address: str) -> socket.socket:
    subprocess.run(["bluetoothctl", "trust", address], capture_output=True, timeout=5)
    print(f"[BT] Opening RFCOMM socket → {address}  channel {RFCOMM_CHANNEL}...")
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    sock.settimeout(10.0)
    sock.connect((address, RFCOMM_CHANNEL))
    sock.settimeout(3.0)
    print("[BT] Connected ✓")
    return sock

# ─── ELM327 PROTOCOL ─────────────────────────────────────────────────────────

class ELM327:
    def __init__(self, sock):
        self.sock = sock

    def _send(self, cmd: str, timeout: float = 3.0) -> str:
        self.sock.settimeout(timeout)
        self.sock.sendall((cmd + "\r").encode())
        buf = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                chunk = self.sock.recv(256)
                if not chunk: break
                buf += chunk
                if b">" in buf: break
            except socket.timeout:
                break
        decoded = buf.decode("utf-8", errors="replace").replace("\r", "").replace(">", "").strip()
        if decoded.upper().startswith(cmd.upper()):
            decoded = decoded[len(cmd):].strip()
        return decoded

    def init(self):
        print("[ELM] Initializing...")
        cmds = [
            ("ATZ",   "Reset",           5.0),
            ("ATE0",  "Echo off",        2.0),
            ("ATL0",  "Linefeeds off",   2.0),
            ("ATS0",  "Spaces off",      2.0),
            ("ATH0",  "Headers off",     2.0),
            ("ATSP0", "Auto protocol",   2.0),
            ("ATAT1", "Adaptive timing", 2.0),
        ]
        for cmd, desc, t in cmds:
            resp = self._send(cmd, timeout=t)
            ok = "OK" in resp or "ELM327" in resp
            print(f"  {cmd:8s} {desc}: {'✓' if ok else repr(resp)}")
        print("[ELM] Ready ✓\n")

    def query(self, mode_pid: str) -> list | None:
        resp = self._send(mode_pid, timeout=2.0)
        if not resp: return None
        u = resp.upper()
        if any(x in u for x in ["NO DATA","ERROR","UNABLE","STOPPED","?"]): return None
        hex_str = u.replace(" ", "").replace("\n", "")
        mode_resp = f"4{mode_pid[1]}"
        pid_byte  = mode_pid[2:4].upper()
        prefix    = mode_resp + pid_byte
        idx = hex_str.find(prefix)
        data_hex = hex_str[idx + len(prefix):] if idx >= 0 else hex_str
        if not data_hex: return None
        try:
            return [int(data_hex[i:i+2], 16) for i in range(0, len(data_hex) - 1, 2)]
        except ValueError:
            return None

    def probe_supported_pids(self) -> set[str]:
        """Query mode 01 support bitmasks (PIDs 00,20,40,60,80,A0,C0) and return
        a set of supported mode_pid strings like {'010C', '010D', ...}."""
        supported = set()
        support_pids = ["0100","0120","0140","0160","0180","01A0","01C0"]
        for sp in support_pids:
            resp = self._send(sp, timeout=3.0)
            if not resp or any(x in resp.upper() for x in ["NO DATA","ERROR","UNABLE"]):
                continue
            hex_str = resp.upper().replace(" ", "")
            mode_resp = f"4{sp[1]}" + sp[2:4].upper()
            idx = hex_str.find(mode_resp)
            if idx < 0: continue
            data_hex = hex_str[idx + len(mode_resp):]
            if len(data_hex) < 8: continue
            try:
                bitmask = int(data_hex[:8], 16)
                base = int(sp[2:], 16)
                for bit in range(32):
                    if bitmask & (1 << (31 - bit)):
                        pid_num = base + bit + 1
                        supported.add(f"01{pid_num:02X}")
            except ValueError:
                continue
        return supported

    def get_dtcs(self) -> list:
        resp = self._send("03", timeout=5.0)
        if not resp or "NO DATA" in resp.upper(): return []
        codes = []
        hex_str = resp.upper().replace(" ", "").replace("\n", "")
        idx = hex_str.find("43")
        if idx >= 0: hex_str = hex_str[idx + 2:]
        prefix_map = {
            0:"P0",1:"P1",2:"P2",3:"P3",
            4:"C0",5:"C1",6:"B0",7:"U0"
        }
        for i in range(0, len(hex_str) - 3, 4):
            try:
                b1 = int(hex_str[i:i+2], 16)
                b2 = int(hex_str[i+2:i+4], 16)
            except ValueError:
                continue
            if b1 == 0 and b2 == 0: continue
            p = prefix_map.get((b1 >> 4) >> 1, "P")
            codes.append(f"{p}{(b1 & 0x3F):01X}{b2:02X}")
        return codes

# ─── LOGGER ──────────────────────────────────────────────────────────────────

class DataLogger:
    def __init__(self, fmt, log_file, pids):
        self.fmt = fmt
        self.log_file = log_file
        self.pids = pids
        self._csv_file = None
        self._csv_writer = None
        self._json_records = []

        if log_file and fmt == "csv":
            self._csv_file = open(log_file, "w", newline="")
            fields = ["timestamp", "elapsed_s"] + pids
            self._csv_writer = csv.DictWriter(self._csv_file, fieldnames=fields)
            self._csv_writer.writeheader()
            print(f"[LOG] CSV  → {log_file.resolve()}")
        elif log_file and fmt == "json":
            print(f"[LOG] JSON → {log_file.resolve()}")

    def write(self, record):
        if self.fmt == "csv":
            if self._csv_writer:
                self._csv_writer.writerow(record)
                self._csv_file.flush()
            parts = []
            for k, v in record.items():
                if k in ("timestamp","elapsed_s") or v is None: continue
                _, _, unit, _ = PID_REGISTRY[k]
                parts.append(f"{k}={v}{unit}")
            ts = record["timestamp"][11:23]
            print(f"[{ts}]  " + "  ".join(parts))
        elif self.fmt == "json":
            clean = {k:v for k,v in record.items() if v is not None}
            self._json_records.append(clean)
            if self.log_file:
                with open(self.log_file, "w") as f:
                    json.dump(self._json_records, f, indent=2)
            print(json.dumps(clean))

    def close(self):
        if self._csv_file: self._csv_file.close()

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Acty OBD-II — VeePeak OBDCheck BLE — expanded PID capture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--address", "-a", default="8C:DE:52:D9:7E:D1",
        help="Bluetooth MAC (default: your VeePeak)")
    parser.add_argument("--pids", "-p",
        help="Comma-separated PID names to poll (overrides probe)")
    parser.add_argument("--no-probe", action="store_true",
        help="Skip vehicle PID probe, use default 12-PID set")
    parser.add_argument("--interval", "-i", type=float, default=1.0,
        help="Poll interval in seconds (default: 1.0)")
    parser.add_argument("--format", "-f", choices=["csv","json"], default="csv")
    parser.add_argument("--no-log", action="store_true",
        help="Terminal output only — no file saved")
    parser.add_argument("--dtc", action="store_true",
        help="Read Diagnostic Trouble Codes and exit")
    parser.add_argument("--list-pids", action="store_true",
        help="Print full PID registry and exit")
    args = parser.parse_args()

    if args.list_pids:
        print(f"\n{'NAME':<28} {'PID':<6} {'UNIT':<8} DESCRIPTION")
        print("─" * 80)
        for name, (mpid, desc, unit, _) in sorted(PID_REGISTRY.items(), key=lambda x: x[1][0]):
            d = " *" if name in DEFAULT_PIDS else ""
            print(f"{name:<28} {mpid:<6} {unit:<8} {desc}{d}")
        print(f"\n* = default set  |  Total: {len(PID_REGISTRY)} PIDs defined")
        sys.exit(0)

    # ── Connect ───────────────────────────────────────────────────────────────
    print(f"[BT] Connecting to {args.address}...")
    try:
        sock = bt_connect(args.address)
    except OSError as e:
        print(f"\n[ERROR] {e}")
        print("  • Dongle plugged in? Ignition ON?")
        print("  • Try: sudo systemctl restart bluetooth")
        sys.exit(1)

    elm = ELM327(sock)
    elm.init()

    # ── DTC mode ──────────────────────────────────────────────────────────────
    if args.dtc:
        print("[DTC] Reading stored codes...")
        codes = elm.get_dtcs()
        if codes:
            print(f"  Found {len(codes)} code(s): {', '.join(codes)}")
        else:
            print("  No stored trouble codes.")
        sock.close()
        sys.exit(0)

    # ── Resolve PID list ──────────────────────────────────────────────────────
    if args.pids:
        pids = [p.strip().upper() for p in args.pids.split(",")]
        unknown = [p for p in pids if p not in PID_REGISTRY]
        if unknown:
            print(f"[ERROR] Unknown PIDs: {unknown}  (run --list-pids)")
            sys.exit(1)

    elif not args.no_probe:
        print("[PROBE] Querying vehicle supported PID bitmask...")
        supported_hex = elm.probe_supported_pids()
        print(f"[PROBE] Vehicle supports {len(supported_hex)} raw PIDs")

        # Match to our named registry — deduplicate by PID hex
        # (some names share a PID hex; include all matching names)
        seen_pids = set()
        pids = []
        for name, (mpid, _, _, _) in PID_REGISTRY.items():
            if mpid.upper() in supported_hex and mpid.upper() not in seen_pids:
                pids.append(name)
                seen_pids.add(mpid.upper())
            elif mpid.upper() in supported_hex:
                # Add duplicate-PID names (e.g. O2 voltage + trim from same PID)
                pids.append(name)

        # Deduplicate while preserving order
        seen_names = set()
        pids_dedup = []
        for p in pids:
            if p not in seen_names:
                pids_dedup.append(p)
                seen_names.add(p)
        pids = pids_dedup

        print(f"[PROBE] Matched {len(pids)} named PIDs in registry:")
        print(f"        {', '.join(pids)}\n")
    else:
        pids = DEFAULT_PIDS

    # ── Set up logging ────────────────────────────────────────────────────────
    log_file = None
    if not args.no_log:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = "json" if args.format == "json" else "csv"
        log_file = Path(f"acty_obd_{ts}.{ext}")

    logger = DataLogger(fmt=args.format, log_file=log_file, pids=pids)

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    running = True
    def _stop(sig, frame):
        nonlocal running
        print("\n[STOP] Stopping...")
        running = False
    signal.signal(signal.SIGINT, _stop)

    # ── Poll loop ─────────────────────────────────────────────────────────────
    print(f"[POLL] {len(pids)} PIDs  |  interval {args.interval}s  |  Ctrl+C to stop\n")

    start = time.monotonic()
    n = 0

    try:
        while running:
            loop_start = time.monotonic()
            record = {
                "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                "elapsed_s": round(time.monotonic() - start, 2),
            }
            for pid_name in pids:
                mpid, _, _, decoder = PID_REGISTRY[pid_name]
                try:
                    raw = elm.query(mpid)
                    record[pid_name] = decoder(raw) if raw is not None else None
                except Exception:
                    record[pid_name] = None
            logger.write(record)
            n += 1
            sleep = max(0, args.interval - (time.monotonic() - loop_start))
            if sleep > 0: time.sleep(sleep)
    finally:
        logger.close()
        try: sock.close()
        except Exception: pass
        total = time.monotonic() - start
        print(f"\n[DONE] {n} samples  |  {total:.1f}s")
        if log_file and log_file.exists():
            print(f"[DONE] Saved → {log_file.resolve()}")

if __name__ == "__main__":
    main()
