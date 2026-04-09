import SwiftUI

struct ContentView: View {
    @StateObject private var model = CaptureViewModel()

    var body: some View {
        NavigationView {
            VStack(spacing: 16) {
                Text("Acty Cactus iOS")
                    .font(.largeTitle)
                    .bold()

                Text("Session: \(model.sessionId)")
                    .font(.subheadline)

                Text(model.statusMessage)
                    .foregroundColor(.gray)

                HStack {
                    Text("Timer: \(model.elapsedSecondsString)")
                    Text("Samples: \(model.sampleCount)")
                }

                Spacer()

                Button(action: model.isRunning ? model.stopCapture : model.startCapture) {
                    Text(model.isRunning ? "Stop Capture" : "Start Capture")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(model.isRunning ? Color.red : Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                }
                .padding(.horizontal)

                Spacer()
            }
            .padding()
            .navigationTitle("Acty Capture")
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
