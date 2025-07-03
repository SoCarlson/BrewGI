# It's time to BrewGI! 

# BrewGI - A simple GUI for managing Homebrew apps on macOS
# Unofficial project, not affiliated with Homebrew or Apple.

# BrewGI allows you to view installed Homebrew apps, search for new ones, uninstall selected apps, and import/export app lists in JSON format.
# Note: This script requires Python, PyQt5, and Homebrew to be installed on your macOS system.


import json
import sys
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QListWidget, QLabel,
    QPushButton, QListWidgetItem, QHBoxLayout, QCheckBox, QMessageBox, QInputDialog, QFileDialog, QDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon




def except_hook(type, value, traceback):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle("Application Error")
    msg.setText("An unexpected error occurred:\n" + str(value))
    msg.exec_()
    sys.exit(1)

sys.excepthook = except_hook

def get_app_icon(app_name):
    """
    Try to get an icon for the app. For casks, try /Applications/{app}.app/Contents/Resources/*.icns.
    Fallback to a default icon if not found.
    """
    import glob, os
    # Try to find .icns in /Applications/{app}.app/Contents/Resources/
    app_bundle = f"/Applications/{app_name.capitalize()}.app"
    icns_pattern = os.path.join(app_bundle, "Contents", "Resources", "*.icns")
    icns_files = glob.glob(icns_pattern)
    if icns_files:
        return QIcon(icns_files[0])
    # Fallback: use a generic system icon or nothing
    return QIcon.fromTheme("application-x-executable")



class BrewInstaller(QThread):
    finished = pyqtSignal(list, list)  # (successes, failures)

    def __init__(self, apps):
        super().__init__()
        self.apps = apps

    def run(self):
        successes = []
        failures = []
        for app in self.apps:
            try:
                subprocess.check_call(['brew', 'install', app])
                successes.append(app)
            except subprocess.CalledProcessError:
                failures.append(app)
        self.finished.emit(successes, failures)

BREW_PATH = "/opt/homebrew/bin/brew"  # or your path from 'which brew'

def get_brew_apps():
    try:
        cask_apps = subprocess.check_output([BREW_PATH, 'list', '--cask'], text=True).splitlines()
    except subprocess.CalledProcessError:
        cask_apps = []
    try:
        formula_apps = subprocess.check_output([BREW_PATH, 'list'], text=True).splitlines()
    except subprocess.CalledProcessError:
        formula_apps = []
    return cask_apps, formula_apps

def search_brew_apps(query):
    try:
        result = subprocess.check_output([BREW_PATH, 'search', query], text=True).splitlines()
        return result
    except subprocess.CalledProcessError:
        return []

def uninstall_brew_app(app):
    try:
        result = subprocess.run(
            [BREW_PATH, 'uninstall', '--force', app],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            return True, ""
        else:
            return False, result.stderr.strip()
    except Exception as e:
        return False, str(e)

class BrewAppStore(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BrewGI - Unofficial GUI for Homebrew App Store")
        self.setGeometry(100, 100, 500, 700)
        
        layout = QVBoxLayout()
        self.label = QLabel("Installed Homebrew Apps")
        layout.addWidget(self.label)

        self.list_widget = QListWidget()
        self.refresh_app_list()
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.search_btn = QPushButton("Search for New Apps")
        self.search_btn.clicked.connect(self.search_apps)
        btn_layout.addWidget(self.search_btn)

        self.uninstall_btn = QPushButton("Uninstall Selected")
        self.uninstall_btn.clicked.connect(self.uninstall_selected)
        btn_layout.addWidget(self.uninstall_btn)

        self.export_btn = QPushButton("Export Installed as JSON")
        self.export_btn.clicked.connect(self.export_installed_json)
        btn_layout.addWidget(self.export_btn)

        self.import_btn = QPushButton("Import & Install from JSON")
        self.import_btn.clicked.connect(self.import_and_install_json)
        btn_layout.addWidget(self.import_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def export_installed_json(self):
        cask_apps, formula_apps = get_brew_apps()
        data = {
            "cask": cask_apps,
            "formula": formula_apps
        }
        path, _ = QFileDialog.getSaveFileName(self, "Save Installed Apps", "", "JSON Files (*.json)")
        if path:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Export", "Installed apps exported to JSON.")

    def import_and_install_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Apps JSON", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            import_casks = set(data.get("cask", []))
            import_formulae = set(data.get("formula", []))
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to read JSON:\n{e}")
            return

        cask_apps, formula_apps = get_brew_apps()
        installed_casks = set(cask_apps)
        installed_formulae = set(formula_apps)

        # Combine all apps from JSON, remove duplicates
        all_imported = import_casks | import_formulae
        already_installed = installed_casks | installed_formulae

        dlg = QDialog(self)
        dlg.setWindowTitle("Confirm Apps to Install")
        vbox = QVBoxLayout()
        vbox.addWidget(QLabel("Select apps to install:"))
        app_list = QListWidget()
        app_list.setSelectionMode(QListWidget.NoSelection)

        for app in sorted(all_imported):
            already = app in already_installed
            label = app + (" (already installed)" if already else "")
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if already:
                item.setCheckState(Qt.Unchecked)
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            else:
                item.setCheckState(Qt.Checked)
            app_list.addItem(item)

        vbox.addWidget(app_list)
        btn_layout = QHBoxLayout()
        install_btn = QPushButton("Install Selected")
        cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(install_btn)
        btn_layout.addWidget(cancel_btn)
        vbox.addLayout(btn_layout)
        dlg.setLayout(vbox)

        def do_install():
            selected = []
            for i in range(app_list.count()):
                item = app_list.item(i)
                if (item.flags() & Qt.ItemIsEnabled) and item.checkState() == Qt.Checked:
                    app_name = item.text().replace(" (already installed)", "")
                    selected.append(app_name)
            if not selected:
                QMessageBox.information(dlg, "Install", "No apps selected.")
                return
            install_btn.setEnabled(False)
            cancel_btn.setEnabled(False)
            dlg.setWindowTitle("Installing...")
            self.installer = BrewInstaller(selected)
            def on_finished(successes, failures):
                msg = ""
                if successes:
                    msg += f"Installed: {', '.join(successes)}\n"
                if failures:
                    msg += f"Failed: {', '.join(failures)}"
                QMessageBox.information(dlg, "Install", msg or "Done.")
                dlg.close()
                self.refresh_app_list()
            self.installer.finished.connect(on_finished)
            self.installer.start()

        install_btn.clicked.connect(do_install)
        cancel_btn.clicked.connect(dlg.close)
        dlg.exec_()

    def refresh_app_list(self):
        self.list_widget.clear()
        cask_apps, formula_apps = get_brew_apps()
        all_apps = sorted(set(cask_apps + formula_apps))
        for app in all_apps:
            item = QListWidgetItem(app)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(item)

    def search_apps(self):
        query, ok = QInputDialog.getText(self, "Search Brew", "Enter app name or keyword:")
        if ok and query:
            results = search_brew_apps(query)
            if results:
                # Show a new dialog with checkable results and Install/Back buttons
                dlg = QWidget()
                dlg.setWindowTitle("Search Results")
                dlg.setGeometry(150, 150, 400, 500)
                vbox = QVBoxLayout()
                label = QLabel("Select apps to install:")
                vbox.addWidget(label)
                result_list = QListWidget()
                for app in results:
                    item = QListWidgetItem(app)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                    result_list.addItem(item)
                vbox.addWidget(result_list)
                btn_layout = QHBoxLayout()
                install_btn = QPushButton("Install Selected")
                back_btn = QPushButton("Back")
                btn_layout.addWidget(install_btn)
                btn_layout.addWidget(back_btn)
                vbox.addLayout(btn_layout)
                dlg.setLayout(vbox)

                def do_install():
                    to_install = []
                    for i in range(result_list.count()):
                        item = result_list.item(i)
                        if item.checkState() == Qt.Checked:
                            to_install.append(item.text())
                    if not to_install:
                        QMessageBox.information(dlg, "Install", "No apps selected.")
                        return

                    install_btn.setEnabled(False)
                    back_btn.setEnabled(False)
                    dlg.setWindowTitle("Installing...")

                    self.installer = BrewInstaller(to_install)
                    def on_finished(successes, failures):
                        msg = ""
                        if successes:
                            msg += f"Installed: {', '.join(successes)}\n"
                        if failures:
                            msg += f"Failed: {', '.join(failures)}"
                        QMessageBox.information(dlg, "Install", msg or "Done.")
                        dlg.close()
                        self.refresh_app_list()
                    self.installer.finished.connect(on_finished)
                    self.installer.start()

                install_btn.clicked.connect(do_install)
                back_btn.clicked.connect(dlg.close)
                dlg.show()
            else:
                QMessageBox.information(self, "Search Results", "No apps found.")

    def uninstall_selected(self):
        to_uninstall = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                to_uninstall.append(item.text())
        if not to_uninstall:
            QMessageBox.information(self, "Uninstall", "No apps selected.")
            return
        errors = []
        for app in to_uninstall:
            try:
                success = uninstall_brew_app(app)
                if not success:
                    errors.append(app)
            except Exception as e:
                errors.append(f"{app} (error: {str(e)})")
        if errors:
            QMessageBox.warning(
                self,
                "Uninstall",
                "Failed to uninstall:\n" + "\n".join(errors) +
                "\n\nThis may be due to permissions or a cancelled password prompt."
            )
        else:
            QMessageBox.information(self, "Uninstall", "Selected apps uninstalled.")
        self.refresh_app_list()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BrewAppStore()
    window.show()
    sys.exit(app.exec_())



# import sys
# import subprocess
# from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QListWidget, QLabel

# def get_brew_apps():
#     try:
#         cask_apps = subprocess.check_output(['brew', 'list', '--cask'], text=True).splitlines()
#     except subprocess.CalledProcessError:
#         cask_apps = []
#     try:
#         formula_apps = subprocess.check_output(['brew', 'list'], text=True).splitlines()
#     except subprocess.CalledProcessError:
#         formula_apps = []
#     return cask_apps, formula_apps

# class BrewAppStore(QWidget):
#     def __init__(self):
#         super().__init__()
#         self.setWindowTitle("Brew App Store")
#         self.setGeometry(100, 100, 400, 600)
#         layout = QVBoxLayout()
#         self.label = QLabel("Installed Homebrew Apps")
#         layout.addWidget(self.label)
#         self.list_widget = QListWidget()
#         cask_apps, formula_apps = get_brew_apps()
#         for app in sorted(set(cask_apps + formula_apps)):
#             self.list_widget.addItem(app)
#         layout.addWidget(self.list_widget)
#         self.setLayout(layout)

# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     window = BrewAppStore()
#     window.show()
#     sys.exit(app.exec_())