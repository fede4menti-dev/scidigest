import SwiftUI

struct SettingsView: View {
    @Environment(DigestStore.self) private var store
    @AppStorage(Config.feedURLKey) private var feedURL = Config.defaultFeedURL
    @AppStorage("reminderOn") private var reminderOn = false
    @AppStorage("reminderHour") private var reminderHour = 8
    @AppStorage("reminderMinute") private var reminderMinute = 0
    @State private var notificationsDenied = false

    private var reminderTime: Binding<Date> {
        Binding {
            Calendar.current.date(from: DateComponents(hour: reminderHour, minute: reminderMinute)) ?? .now
        } set: { newValue in
            let c = Calendar.current.dateComponents([.hour, .minute], from: newValue)
            reminderHour = c.hour ?? 8
            reminderMinute = c.minute ?? 0
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("https://yourname.github.io/scidigest/", text: $feedURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Button("Reload now") { Task { await store.refresh() } }
                    if let msg = store.errorMessage {
                        Text(msg).font(.footnote).foregroundStyle(.red)
                    }
                } header: {
                    Text("Report address")
                } footer: {
                    Text("Your GitHub Pages address, where the daily reports are published.")
                }

                Section {
                    Toggle("Daily reminder", isOn: $reminderOn)
                    if reminderOn {
                        DatePicker("Time", selection: reminderTime, displayedComponents: .hourAndMinute)
                    }
                    if notificationsDenied {
                        Text("Notifications are turned off for SciDigest. Turn them on in the iPhone Settings app.")
                            .font(.footnote)
                            .foregroundStyle(.red)
                    }
                } header: {
                    Text("Notifications")
                } footer: {
                    Text("Pick a time after your daily report is generated.")
                }

                Section("About") {
                    Text("SciDigest picks the most significant new papers from journals such as Nature, Science, Cell, PNAS, NEJM and The Lancet, and explains them for science students.")
                    Text("Summaries are paraphrased by AI from each paper's abstract, or its full text when a free, legal copy exists. Always read the original before citing it.")
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
            .onChange(of: reminderOn) { scheduleReminder() }
            .onChange(of: reminderHour) { scheduleReminder() }
            .onChange(of: reminderMinute) { scheduleReminder() }
        }
    }

    private func scheduleReminder() {
        Task {
            let ok = await Reminders.update(enabled: reminderOn, hour: reminderHour, minute: reminderMinute)
            guard reminderOn else { return }  // turning it off never clears the warning
            notificationsDenied = !ok
            if !ok { reminderOn = false }
        }
    }
}
