import SwiftUI

@main
struct SonotekoApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup("Sonoteko") {
            MainWindowView()
                .environmentObject(appState)
                .frame(minWidth: 1024, minHeight: 680)
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified)
        .commands {
            CommandGroup(replacing: .newItem) {}

            CommandMenu("Datei") {
                Button("Ordner hinzufügen …") { appState.openFolderDialog() }
                    .keyboardShortcut("O", modifiers: [.command, .shift])
                Button("Dateien öffnen …") { appState.openFilesDialog() }
                    .keyboardShortcut("O")
                Divider()
                Button("Tags speichern") { appState.tagEditorVM.save() }
                    .keyboardShortcut("S")
            }

            CommandMenu("Library") {
                Button("Aktualisieren") {
                    Task { await appState.libraryVM.loadFromDB() }
                }
                .keyboardShortcut("R")
                Button("Fehlende Tracks entfernen") {
                    Task { await appState.libraryVM.cleanupMissing() }
                }
            }

            CommandMenu("Ansicht") {
                Button("Tag-Editor einblenden") { appState.showRightPanel = true }
                    .keyboardShortcut("T")
            }
        }
    }
}
