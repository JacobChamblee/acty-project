import { useEffect, useState } from 'react';
import { Calendar, TrendingUp, TrendingDown, Minus, ChevronRight } from 'lucide-react';

interface Trip {
  session_id: string;
  uploaded_at: string;
  features: any;
  events: any[];
}

interface TripSidebarProps {
  vehicleId: string;
  currentSessionId?: string;
  onSelectTrip: (sessionId: string) => void;
}

export default function TripSidebar({ vehicleId, currentSessionId, onSelectTrip }: TripSidebarProps) {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [trends, setTrends] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadTrips();
  }, [vehicleId]);

  const loadTrips = async () => {
    try {
      const response = await fetch(`/api/vehicles/${vehicleId}/trips`);
      if (response.ok) {
        const data = await response.json();
        setTrips(data.trips);
        setTrends(data.vehicle.trend_history);
      }
    } catch (error) {
      console.error('Failed to load trips:', error);
    } finally {
      setLoading(false);
    }
  };

  const getTrendIcon = (direction: string) => {
    switch (direction) {
      case 'increasing':
        return <TrendingUp className="w-4 h-4 text-red-500" />;
      case 'decreasing':
        return <TrendingDown className="w-4 h-4 text-green-500" />;
      case 'stable':
        return <Minus className="w-4 h-4 text-gray-500" />;
      default:
        return <Minus className="w-4 h-4 text-gray-400" />;
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold mb-4 text-gray-800">Trip History</h3>
        <p className="text-gray-600 text-sm">Loading...</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-semibold mb-4 text-gray-800">Trip History</h3>

      {trends && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <h4 className="text-sm font-semibold text-gray-700 mb-3">Trend Indicators</h4>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">LTFT Drift</span>
              <div className="flex items-center">
                {getTrendIcon(trends.ltft_direction)}
                <span className="ml-1 text-gray-700">{trends.ltft_direction}</span>
              </div>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">MAF/RPM</span>
              <div className="flex items-center">
                {getTrendIcon(trends.maf_direction)}
                <span className="ml-1 text-gray-700">{trends.maf_direction}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {trips.length === 0 ? (
          <p className="text-gray-600 text-sm">No trips recorded yet</p>
        ) : (
          trips.map((trip) => (
            <button
              key={trip.session_id}
              onClick={() => onSelectTrip(trip.session_id)}
              className={`
                w-full text-left p-3 rounded-lg transition-all
                ${currentSessionId === trip.session_id
                  ? 'bg-blue-100 border-2 border-blue-300'
                  : 'bg-gray-50 hover:bg-gray-100 border-2 border-transparent'
                }
              `}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <Calendar className="w-4 h-4 text-gray-500 mr-2" />
                  <span className="text-sm font-medium text-gray-800">
                    {formatDate(trip.uploaded_at)}
                  </span>
                </div>
                <ChevronRight className="w-4 h-4 text-gray-400" />
              </div>
              {trip.events && trip.events.length > 0 && (
                <div className="mt-2 text-xs text-gray-600">
                  {trip.events.length} event{trip.events.length !== 1 ? 's' : ''} detected
                </div>
              )}
            </button>
          ))
        )}
      </div>
    </div>
  );
}
