import { Activity } from 'lucide-react';

interface SignalChartsProps {
  features: any;
}

export default function SignalCharts({ features }: SignalChartsProps) {
  const metrics = [
    {
      label: 'Average RPM',
      value: features.avg_rpm ? (features.avg_rpm * 8000).toFixed(0) : '0',
      unit: 'RPM',
    },
    {
      label: 'Wide Open Throttle',
      value: features.pct_time_wot ? features.pct_time_wot.toFixed(1) : '0',
      unit: '%',
    },
    {
      label: 'LTFT Drift',
      value: features.ltft_drift ? (features.ltft_drift * 100).toFixed(1) : '0',
      unit: '%',
    },
    {
      label: 'Redline Events',
      value: features.redline_events || '0',
      unit: 'events',
    },
    {
      label: 'Knock Events',
      value: features.knock_events_per_1k_cycles
        ? features.knock_events_per_1k_cycles.toFixed(1)
        : '0',
      unit: 'per 1k cycles',
    },
    {
      label: 'MAF/RPM Ratio',
      value: features.maf_per_rpm ? features.maf_per_rpm.toFixed(5) : '0',
      unit: '',
    },
    {
      label: 'Peak Coolant Temp',
      value: features.coolant_peak_temp
        ? ((features.coolant_peak_temp * 255) - 40).toFixed(0)
        : '0',
      unit: '°C',
    },
    {
      label: 'Time Above 100°C',
      value: features.time_above_100c ? features.time_above_100c.toFixed(0) : '0',
      unit: 'seconds',
    },
  ];

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center mb-6">
        <Activity className="w-6 h-6 text-blue-600 mr-2" />
        <h3 className="text-xl font-semibold text-gray-800">Signal Metrics</h3>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {metrics.map((metric, index) => (
          <div
            key={index}
            className="bg-gradient-to-br from-gray-50 to-gray-100 rounded-lg p-4 border border-gray-200"
          >
            <p className="text-xs text-gray-600 mb-2 font-medium">{metric.label}</p>
            <div className="flex items-baseline">
              <p className="text-2xl font-bold text-gray-800">{metric.value}</p>
              {metric.unit && (
                <p className="text-sm text-gray-600 ml-2">{metric.unit}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
        <p className="text-sm text-blue-800">
          <span className="font-semibold">Signal Processing:</span> Data processed through
          median filtering (5-sample window), outlier detection (z-score), and derived signal
          computation (RPM rate, coolant rise rate, throttle transients, knock frequency).
        </p>
      </div>
    </div>
  );
}
