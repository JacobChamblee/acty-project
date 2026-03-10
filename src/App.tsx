import { useState, useEffect } from 'react';
import { Car } from 'lucide-react';
import UploadPanel from './components/UploadPanel';
import SignalCharts from './components/SignalCharts';
import DiagnosticCards from './components/DiagnosticCards';
import ReportStream from './components/ReportStream';
import TripSidebar from './components/TripSidebar';

function App() {
  const [vehicleId, setVehicleId] = useState('default');
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [tripData, setTripData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    createDefaultVehicle();
  }, []);

  const createDefaultVehicle = async () => {
    try {
      await fetch('/api/vehicles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          vehicle_id: 'default',
          vin: 'DEMO000000000000',
          make: 'Demo',
          model: 'Vehicle',
          year: '2024',
        }),
      });
    } catch (error) {
      console.log('Vehicle may already exist');
    }
  };

  const handleUploadComplete = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    await loadTripData(sessionId);
  };

  const loadTripData = async (sessionId: string) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/trips/${sessionId}`);
      if (response.ok) {
        const data = await response.json();
        setTripData(data);
      }
    } catch (error) {
      console.error('Failed to load trip data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTrip = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    await loadTripData(sessionId);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center">
            <Car className="w-8 h-8 text-blue-600 mr-3" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Acty</h1>
              <p className="text-sm text-gray-600">AI-Powered Vehicle Preventive Maintenance</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-1">
            <TripSidebar
              vehicleId={vehicleId}
              currentSessionId={currentSessionId || undefined}
              onSelectTrip={handleSelectTrip}
            />
          </div>

          <div className="lg:col-span-3 space-y-6">
            {!currentSessionId ? (
              <UploadPanel onUploadComplete={handleUploadComplete} vehicleId={vehicleId} />
            ) : loading ? (
              <div className="bg-white rounded-lg shadow-md p-12 text-center">
                <p className="text-gray-600">Loading trip data...</p>
              </div>
            ) : tripData ? (
              <>
                <SignalCharts features={tripData.features} />
                <DiagnosticCards events={tripData.events || []} />
                <ReportStream
                  sessionId={currentSessionId}
                  reportText={tripData.report_text}
                />
              </>
            ) : null}
          </div>
        </div>
      </main>

      <footer className="mt-12 pb-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500">
            Powered by Claude AI • Local Processing • Zero Cloud Dependencies
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
