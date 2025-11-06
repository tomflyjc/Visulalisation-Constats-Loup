# main_visualisation_constats.py
from qgis.utils import iface
from qgis.core import Qgis
from PyQt5.QtWidgets import QAction
from PyQt5.QtGui import QIcon
import os
from .dialog_visualisation_constats import VisualisationConstatsLoupDialog

class MainPluginVisualisationConstatsLoup:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None
        print("MainPluginVisualisationConstatsLoup initialized")  # Debug

    def initGui(self):
        """Initialise l'interface du plugin."""
        self.action = QAction("Visualisation Constats Loup", self.iface.mainWindow())
        plugin_dir = os.path.dirname(__file__)
        icon_path = os.path.join(plugin_dir, "loup1.ico")
        if os.path.exists(icon_path):
            self.action.setIcon(QIcon(icon_path))
            print(f"Icon loaded: {icon_path}")  # Debug
        else:
            print(f"Icon not found: {icon_path}")  # Debug
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        print("Plugin action added to toolbar")  # Debug

    def unload(self):
        """Supprime le plugin de l'interface."""
        if self.dialog:
            self.dialog.close()
        if self.action:
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
        self.dialog = None
        self.action = None
        print("Plugin unloaded")  # Debug

    def run(self):
        """Affiche la fenêtre principale du plugin."""
        try:
            self.dialog = VisualisationConstatsLoupDialog(self.iface)
            self.dialog.show()  # Use show() for non-modal dialog, consistent with previous
            print("Dialog opened")  # Debug
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Erreur",
                f"Impossible de lancer le plugin: {str(e)}",
                level=Qgis.Critical
            )
            print(f"Error in run: {str(e)}")  # Debug