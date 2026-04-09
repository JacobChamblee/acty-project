import Foundation
import Combine
import CryptoKit
import CoreBluetooth

final class CaptureViewModel: NSObject, ObservableObject {
    @Published var sessionId: String = UUID().uuidString
    @Published var statusMessage: String = "Ready"
    @Published var isRunning: Bool = false
    @Published var elapsedSecondsString: String = "00:00"
    @Published var sampleCount: Int = 0

    private var timer: Timer?

    func startCapture() {
        sessionId = UUID().uuidString
        statusMessage = "Connecting to OBD adapter..."
        isRunning = true
        sampleCount = 0
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] t in
            guard let self = self else { return }
            let elapsed = Int(t.fireDate.timeIntervalSince1970) % 3600
            self.elapsedSecondsString = String(format: "%02d:%02d", elapsed / 60, elapsed % 60)
        }
        // TODO: implement BLE ELM327 commands, CSV writer, .sig signing, and API sync.
        statusMessage = "Capturing (iOS skeleton)."
    }

    func stopCapture() {
        isRunning = false
        statusMessage = "Session saved"
        timer?.invalidate()
        timer = nil
    }
}
