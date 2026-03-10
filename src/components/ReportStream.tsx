import { useEffect, useState } from 'react';
import { FileText, Loader2 } from 'lucide-react';

interface ReportStreamProps {
  sessionId: string;
  reportText?: string;
}

export default function ReportStream({ sessionId, reportText }: ReportStreamProps) {
  const [streamedReport, setStreamedReport] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    if (reportText) {
      setStreamedReport(reportText);
      return;
    }

    setIsStreaming(true);
    setStreamedReport('');

    const eventSource = new EventSource(`/api/trips/${sessionId}/stream-report`);

    eventSource.onmessage = (event) => {
      setStreamedReport(prev => prev + event.data);
    };

    eventSource.onerror = () => {
      eventSource.close();
      setIsStreaming(false);
    };

    return () => {
      eventSource.close();
      setIsStreaming(false);
    };
  }, [sessionId, reportText]);

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center mb-4">
        <FileText className="w-6 h-6 text-blue-600 mr-2" />
        <h3 className="text-xl font-semibold text-gray-800">Maintenance Report</h3>
        {isStreaming && (
          <Loader2 className="w-4 h-4 text-blue-500 animate-spin ml-2" />
        )}
      </div>

      {streamedReport ? (
        <div className="prose max-w-none">
          <div className="text-gray-700 whitespace-pre-wrap leading-relaxed">
            {streamedReport}
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin mr-3" />
          <p className="text-gray-600">Generating AI-powered report...</p>
        </div>
      )}
    </div>
  );
}
