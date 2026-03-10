import { AlertCircle, AlertTriangle, Info, CheckCircle } from 'lucide-react';

interface DiagnosticEvent {
  type: string;
  severity: string;
  confidence: number;
  evidence: string;
}

interface DiagnosticCardsProps {
  events: DiagnosticEvent[];
}

export default function DiagnosticCards({ events }: DiagnosticCardsProps) {
  const getSeverityConfig = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'high':
        return {
          icon: AlertCircle,
          bgColor: 'bg-red-50',
          borderColor: 'border-red-300',
          textColor: 'text-red-800',
          iconColor: 'text-red-500',
        };
      case 'medium':
        return {
          icon: AlertTriangle,
          bgColor: 'bg-amber-50',
          borderColor: 'border-amber-300',
          textColor: 'text-amber-800',
          iconColor: 'text-amber-500',
        };
      case 'low':
        return {
          icon: Info,
          bgColor: 'bg-blue-50',
          borderColor: 'border-blue-300',
          textColor: 'text-blue-800',
          iconColor: 'text-blue-500',
        };
      default:
        return {
          icon: CheckCircle,
          bgColor: 'bg-gray-50',
          borderColor: 'border-gray-300',
          textColor: 'text-gray-800',
          iconColor: 'text-gray-500',
        };
    }
  };

  const formatEventType = (type: string) => {
    return type
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  if (events.length === 0) {
    return (
      <div className="bg-green-50 border-2 border-green-300 rounded-lg p-6">
        <div className="flex items-center">
          <CheckCircle className="w-6 h-6 text-green-500 mr-3" />
          <div>
            <h3 className="text-lg font-semibold text-green-800">All Systems Normal</h3>
            <p className="text-sm text-green-700 mt-1">
              No diagnostic events detected in this trip.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-xl font-semibold text-gray-800 mb-4">Diagnostic Events</h3>
      {events.map((event, index) => {
        const config = getSeverityConfig(event.severity);
        const Icon = config.icon;

        return (
          <div
            key={index}
            className={`${config.bgColor} ${config.borderColor} border-2 rounded-lg p-4`}
          >
            <div className="flex items-start">
              <Icon className={`w-6 h-6 ${config.iconColor} mr-3 mt-0.5 flex-shrink-0`} />
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <h4 className={`text-lg font-semibold ${config.textColor}`}>
                    {formatEventType(event.type)}
                  </h4>
                  <span className={`text-xs font-medium ${config.textColor} px-2 py-1 rounded`}>
                    {event.confidence.toFixed(0)}% confidence
                  </span>
                </div>
                <p className={`text-sm ${config.textColor}`}>{event.evidence}</p>
                <div className="mt-2 flex items-center">
                  <span
                    className={`text-xs font-medium uppercase ${config.textColor} bg-white px-2 py-1 rounded`}
                  >
                    {event.severity}
                  </span>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
