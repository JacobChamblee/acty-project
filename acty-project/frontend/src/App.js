import { useState, useEffect, useCallback } from "react";
import {
  View, Text, ScrollView, RefreshControl, TouchableOpacity,
  StyleSheet, ActivityIndicator, Dimensions, StatusBar, Platform,
} from "react-native";

// ── CONFIG — change this to your machine's LAN IP ─────────────────────────────
const API_BASE = "http://192.168.68.138:8765";

// ── theme ─────────────────────────────────────────────────────────────────────
const C = {
  bg:       "#0F1117",
  card:     "#1A1D27",
  cardBrd:  "#2A2D3A",
  accent:   "#3B82F6",
  green:    "#22C55E",
  yellow:   "#EAB308",
  red:      "#EF4444",
  textPri:  "#F1F5F9",
  textSec:  "#94A3B8",
  textMute: "#475569",
};

const W = Dimensions.get("window").width;

// ── helpers ───────────────────────────────────────────────────────────────────
function healthColor(score) {
  if (score >= 80) return C.green;
  if (score >= 50) return C.yellow;
  return C.red;
}

function severityColor(sev) {
  return sev === "critical" ? C.red : C.yellow;
}

function severityIcon(sev) {
  return sev === "critical" ? "🔴" : "⚠️";
}

function Sparkline({ data = [], color = C.accent, height = 36 }) {
  if (!data.length) return null;
  const w = (W - 80) / 2;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = height - ((v - min) / range) * height;
    return `${x},${y}`;
  });

  return (
    <View style={{ height, width: w }}>
      {/* SVG-like using positioned views — RN doesn't have SVG built-in */}
      {data.map((v, i) => {
        if (i === 0) return null;
        const x1 = ((i - 1) / (data.length - 1)) * w;
        const x2 = (i / (data.length - 1)) * w;
        const y1 = height - ((data[i - 1] - min) / range) * (height - 4);
        const y2 = height - ((v - min) / range) * (height - 4);
        const lineW = Math.sqrt(Math.pow(x2 - x1, 2) + Math.pow(y2 - y1, 2));
        const angle = Math.atan2(y2 - y1, x2 - x1) * (180 / Math.PI);
        return (
          <View
            key={i}
            style={{
              position: "absolute",
              left: x1,
              top: y1,
              width: lineW,
              height: 1.5,
              backgroundColor: color,
              opacity: 0.85,
              transform: [{ rotate: `${angle}deg` }],
              transformOrigin: "0 0",
            }}
          />
        );
      })}
    </View>
  );
}

// ── components ────────────────────────────────────────────────────────────────

function HealthRing({ score }) {
  const color = healthColor(score);
  const label = score >= 80 ? "Good" : score >= 50 ? "Fair" : "Poor";
  return (
    <View style={styles.ringWrap}>
      <View style={[styles.ring, { borderColor: color }]}>
        <Text style={[styles.ringScore, { color }]}>{score}</Text>
        <Text style={[styles.ringLabel, { color: C.textSec }]}>{label}</Text>
      </View>
      <Text style={styles.ringTitle}>Health Score</Text>
    </View>
  );
}

function StatCard({ label, value, unit, sparkline, pidColor }) {
  return (
    <View style={styles.statCard}>
      <Text style={styles.statLabel}>{label}</Text>
      <View style={styles.statRow}>
        <Text style={styles.statValue}>{value ?? "—"}</Text>
        {unit ? <Text style={styles.statUnit}> {unit}</Text> : null}
      </View>
      {sparkline && sparkline.length > 2 && (
        <Sparkline data={sparkline} color={pidColor || C.accent} height={32} />
      )}
    </View>
  );
}

function AlertCard({ alert }) {
  const color = severityColor(alert.severity);
  return (
    <View style={[styles.alertCard, { borderLeftColor: color }]}>
      <View style={styles.alertHeader}>
        <Text style={styles.alertIcon}>{severityIcon(alert.severity)}</Text>
        <Text style={[styles.alertLabel, { color }]}>{alert.label}</Text>
        <View style={[styles.alertBadge, { backgroundColor: color + "22" }]}>
          <Text style={[styles.alertBadgeText, { color }]}>
            {alert.value}{alert.unit}
          </Text>
        </View>
      </View>
      <Text style={styles.alertMsg}>{alert.message}</Text>
    </View>
  );
}

function SectionHeader({ title }) {
  return <Text style={styles.sectionHeader}>{title}</Text>;
}

// ── main screen ───────────────────────────────────────────────────────────────

export default function App() {
  const [data,        setData]        = useState(null);
  const [loading,     setLoading]     = useState(true);
  const [refreshing,  setRefreshing]  = useState(false);
  const [error,       setError]       = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchInsights = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/insights`, { timeout: 10000 });
      if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
      const json = await resp.json();
      setData(json);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (e) {
      setError(e.message || "Could not reach Acty server");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchInsights(); }, []);

  // ── loading state ────────────────────────────────────────────────────────
  if (loading) {
    return (
      <View style={styles.centered}>
        <StatusBar barStyle="light-content" backgroundColor={C.bg} />
        <ActivityIndicator size="large" color={C.accent} />
        <Text style={styles.loadingText}>Connecting to Acty...</Text>
        <Text style={styles.loadingSubtext}>{API_BASE}</Text>
      </View>
    );
  }

  // ── error state ──────────────────────────────────────────────────────────
  if (error) {
    return (
      <View style={styles.centered}>
        <StatusBar barStyle="light-content" backgroundColor={C.bg} />
        <Text style={styles.errorIcon}>⚡</Text>
        <Text style={styles.errorTitle}>Can't reach server</Text>
        <Text style={styles.errorMsg}>{error}</Text>
        <Text style={styles.errorHint}>
          Make sure you're on home WiFi{"\n"}and server.py is running on your PC
        </Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => fetchInsights()}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const { summary, alerts, sparklines, health_score } = data;
  const s = summary;

  return (
    <View style={styles.root}>
      <StatusBar barStyle="light-content" backgroundColor={C.bg} />

      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.appTitle}>⚡ Acty</Text>
          <Text style={styles.appSub}>
            {s.session_date} · {s.duration_min} min
            {lastUpdated ? ` · ${lastUpdated}` : ""}
          </Text>
        </View>
        <TouchableOpacity
          style={styles.refreshBtn}
          onPress={() => fetchInsights(true)}
          disabled={refreshing}
        >
          <Text style={styles.refreshText}>{refreshing ? "..." : "↻"}</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scroll}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => fetchInsights(true)}
            tintColor={C.accent}
          />
        }
      >
        {/* Health score */}
        <View style={styles.healthRow}>
          <HealthRing score={health_score} />
          <View style={styles.healthMeta}>
            <Text style={styles.healthMetaLine}>
              📍 {s.sample_count} samples
            </Text>
            <Text style={styles.healthMetaLine}>
              🏁 {s.max_speed_kmh} km/h peak
            </Text>
            <Text style={styles.healthMetaLine}>
              🔥 {s.max_rpm?.toLocaleString()} rpm peak
            </Text>
            <Text style={styles.healthMetaLine}>
              ⚡ {alerts.length} alert{alerts.length !== 1 ? "s" : ""}
            </Text>
          </View>
        </View>

        {/* Alerts */}
        {alerts.length > 0 && (
          <>
            <SectionHeader title="🚨 Alerts" />
            {alerts.map((a, i) => <AlertCard key={i} alert={a} />)}
          </>
        )}
        {alerts.length === 0 && (
          <View style={styles.allGoodCard}>
            <Text style={styles.allGoodText}>✅ No anomalies detected</Text>
            <Text style={styles.allGoodSub}>All systems within normal range</Text>
          </View>
        )}

        {/* Key stats */}
        <SectionHeader title="📊 Session Stats" />
        <View style={styles.statGrid}>
          <StatCard
            label="Avg RPM"
            value={s.avg_rpm?.toLocaleString()}
            unit="rpm"
            sparkline={sparklines?.RPM}
            pidColor="#818CF8"
          />
          <StatCard
            label="Avg Speed"
            value={s.avg_speed_kmh}
            unit="km/h"
            sparkline={sparklines?.SPEED}
            pidColor={C.accent}
          />
          <StatCard
            label="Coolant"
            value={s.avg_coolant_c}
            unit="°C"
            sparkline={sparklines?.COOLANT_TEMP}
            pidColor={s.max_coolant_c > 100 ? C.red : C.green}
          />
          <StatCard
            label="Engine Load"
            value={s.avg_engine_load}
            unit="%"
            sparkline={sparklines?.ENGINE_LOAD}
            pidColor={C.yellow}
          />
          <StatCard
            label="LTFT B1"
            value={s.ltft_b1 != null ? (s.ltft_b1 > 0 ? `+${s.ltft_b1}` : s.ltft_b1) : null}
            unit="%"
            sparkline={sparklines?.LONG_FUEL_TRIM_1}
            pidColor={Math.abs(s.ltft_b1 || 0) > 8 ? C.red : C.green}
          />
          <StatCard
            label="Timing"
            value={s.avg_timing}
            unit="°"
            sparkline={sparklines?.TIMING_ADVANCE}
            pidColor="#F472B6"
          />
          <StatCard
            label="MAF"
            value={s.avg_maf}
            unit="g/s"
            sparkline={sparklines?.MAF}
            pidColor="#34D399"
          />
          <StatCard
            label="Battery"
            value={s.battery_v}
            unit="V"
            pidColor={s.battery_v < 13 ? C.red : C.green}
          />
        </View>

        {/* Time moving */}
        {s.pct_time_moving != null && (
          <>
            <SectionHeader title="🛣️ Drive Profile" />
            <View style={styles.profileCard}>
              <View style={styles.profileBar}>
                <View style={[styles.profileFill, { width: `${s.pct_time_moving}%`, backgroundColor: C.accent }]} />
              </View>
              <Text style={styles.profileLabel}>
                {s.pct_time_moving}% time moving · {100 - s.pct_time_moving}% idle
              </Text>
              {s.fuel_level_pct != null && (
                <Text style={styles.profileLabel}>
                  ⛽ Fuel level: {s.fuel_level_pct}%
                </Text>
              )}
            </View>
          </>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </View>
  );
}

// ── styles ────────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  root:           { flex: 1, backgroundColor: C.bg },
  centered:       { flex: 1, backgroundColor: C.bg, alignItems: "center", justifyContent: "center", padding: 24 },
  scroll:         { flex: 1 },

  // header
  header:         { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 20, paddingTop: Platform.OS === "android" ? 48 : 56, paddingBottom: 12 },
  appTitle:       { fontSize: 22, fontWeight: "700", color: C.textPri, letterSpacing: 0.5 },
  appSub:         { fontSize: 12, color: C.textSec, marginTop: 2 },
  refreshBtn:     { backgroundColor: C.card, borderRadius: 20, width: 40, height: 40, alignItems: "center", justifyContent: "center" },
  refreshText:    { fontSize: 20, color: C.textPri },

  // health ring
  healthRow:      { flexDirection: "row", alignItems: "center", padding: 20, gap: 24 },
  ringWrap:       { alignItems: "center" },
  ring:           { width: 100, height: 100, borderRadius: 50, borderWidth: 5, alignItems: "center", justifyContent: "center" },
  ringScore:      { fontSize: 32, fontWeight: "800" },
  ringLabel:      { fontSize: 11, fontWeight: "600" },
  ringTitle:      { fontSize: 12, color: C.textMute, marginTop: 6 },
  healthMeta:     { flex: 1, gap: 6 },
  healthMetaLine: { fontSize: 13, color: C.textSec },

  // alerts
  sectionHeader:  { fontSize: 14, fontWeight: "700", color: C.textMute, paddingHorizontal: 20, paddingTop: 16, paddingBottom: 8, textTransform: "uppercase", letterSpacing: 1 },
  alertCard:      { marginHorizontal: 16, marginBottom: 10, backgroundColor: C.card, borderRadius: 12, borderLeftWidth: 4, padding: 14 },
  alertHeader:    { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 6 },
  alertIcon:      { fontSize: 14 },
  alertLabel:     { fontSize: 14, fontWeight: "700", flex: 1 },
  alertBadge:     { borderRadius: 8, paddingHorizontal: 8, paddingVertical: 2 },
  alertBadgeText: { fontSize: 12, fontWeight: "700" },
  alertMsg:       { fontSize: 13, color: C.textSec, lineHeight: 18 },
  allGoodCard:    { marginHorizontal: 16, marginBottom: 10, backgroundColor: C.card, borderRadius: 12, borderLeftWidth: 4, borderLeftColor: C.green, padding: 16, alignItems: "center" },
  allGoodText:    { fontSize: 15, fontWeight: "700", color: C.green },
  allGoodSub:     { fontSize: 13, color: C.textSec, marginTop: 4 },

  // stat grid
  statGrid:       { flexDirection: "row", flexWrap: "wrap", paddingHorizontal: 12, gap: 8 },
  statCard:       { backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.cardBrd, padding: 12, width: (W - 40) / 2 },
  statLabel:      { fontSize: 11, color: C.textMute, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 4 },
  statRow:        { flexDirection: "row", alignItems: "baseline", marginBottom: 8 },
  statValue:      { fontSize: 22, fontWeight: "700", color: C.textPri },
  statUnit:       { fontSize: 12, color: C.textSec },

  // drive profile
  profileCard:    { marginHorizontal: 16, backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.cardBrd, padding: 14, gap: 8 },
  profileBar:     { height: 8, backgroundColor: C.cardBrd, borderRadius: 4, overflow: "hidden" },
  profileFill:    { height: "100%", borderRadius: 4 },
  profileLabel:   { fontSize: 13, color: C.textSec },

  // loading / error
  loadingText:    { color: C.textPri, fontSize: 16, marginTop: 16, fontWeight: "600" },
  loadingSubtext: { color: C.textMute, fontSize: 12, marginTop: 4 },
  errorIcon:      { fontSize: 48, marginBottom: 12 },
  errorTitle:     { fontSize: 18, fontWeight: "700", color: C.textPri, marginBottom: 8 },
  errorMsg:       { fontSize: 13, color: C.red, marginBottom: 12, textAlign: "center" },
  errorHint:      { fontSize: 13, color: C.textSec, textAlign: "center", lineHeight: 20, marginBottom: 24 },
  retryBtn:       { backgroundColor: C.accent, borderRadius: 12, paddingHorizontal: 32, paddingVertical: 12 },
  retryText:      { color: "#fff", fontWeight: "700", fontSize: 15 },
});
