import Foundation
import UserNotifications

/// A local daily notification. No server or push setup needed.
enum Reminders {
    static let id = "daily-digest-reminder"

    static func update(enabled: Bool, hour: Int, minute: Int) async -> Bool {
        let center = UNUserNotificationCenter.current()
        center.removePendingNotificationRequests(withIdentifiers: [id])
        guard enabled else { return true }

        let granted = (try? await center.requestAuthorization(options: [.alert, .sound])) ?? false
        guard granted else { return false }

        let content = UNMutableNotificationContent()
        content.title = "Today's Science Digest"
        content.body = "New research picks are ready to read."
        content.sound = .default

        var when = DateComponents()
        when.hour = hour
        when.minute = minute
        let trigger = UNCalendarNotificationTrigger(dateMatching: when, repeats: true)
        do {
            try await center.add(UNNotificationRequest(identifier: id, content: content, trigger: trigger))
            return true
        } catch {
            return false
        }
    }
}
