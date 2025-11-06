from qgis.core import (
    QgsProject, QgsFeature, QgsLayerTreeLayer, QgsVectorLayer, QgsVectorFileWriter,
    QgsExpression, QgsFeatureRequest, QgsTextFormat, QgsTextBufferSettings, QgsPalLayerSettings,
    QgsVectorLayerSimpleLabeling
)
from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QPixmap, QPainter, QPen, QBrush, QPainterPath, QColor 
import math

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLineEdit,
    QSlider, QLabel, QCheckBox, QGroupBox, QMessageBox, QWidget, QGridLayout,
    QTextEdit, QTabWidget, QFormLayout, QDoubleSpinBox, QApplication, QProgressBar, QComboBox,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from .data_processor_visualisation_constats import DataProcessorVisualisationConstats
from .layer_manager_visualisation_constats import LayerManagerVisualisationConstats
from .animation_exporter_visualisation_constats import AnimationExporterVisualisationConstats
from .utils_visualisation_constats import normalize_string, normalize_elevage
import os
import csv
import subprocess

class VisualisationConstatsLoupDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("Visualisation Constats Loup")
        self.resize(900, 700)
        self.data_processor = DataProcessorVisualisationConstats()
        self.layer_manager = LayerManagerVisualisationConstats(self.iface)
        self.animation_exporter = AnimationExporterVisualisationConstats(self.iface)
        self.layers = []
        self.all_layers = []
        self.effective_layers = []
        self.global_layer = None
        self.dates_layer = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)
        self.current_frame = 0
        self.is_playing = False
        self.conclusion_checkboxes = {}
        self.elevage_checkboxes = {}
        self.last_project_path = None
        self.cumulative_mode = False
        self.png_cumulative_mode = False
        self.start_year = None
        self.png_start_year = None
        self.available_years = []
        self.setup_ui()
        self.load_last_project_info()
        print("Dialog initialized")

    def load_last_project_info(self):
        """Charge les infos du dernier projet depuis le CSV."""
        try:
            plugin_dir = os.path.dirname(__file__)
            csv_path = os.path.join(plugin_dir, "last_project.csv")
            if os.path.exists(csv_path):
                with open(csv_path, mode='r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) >= 3:
                            self.last_project_path = row[1]
                            break
        except Exception as e:
            print(f"Erreur chargement projet: {str(e)}")

    def setup_ui(self):
        """Configure l'interface utilisateur."""
        layout = QVBoxLayout()
        self.tabs = QTabWidget()
        self.setup_instructions_tab()
        self.setup_processing_tab()
        self.setup_recording_tab()
        self.tabs.addTab(self.instructions_tab, "Instructions")
        self.tabs.addTab(self.processing_tab, "Traitements")
        self.tabs.addTab(self.recording_tab, "Enregistrement")
        layout.addWidget(self.tabs)
        self.setLayout(layout)
        print("UI setup completed")

    def setup_instructions_tab(self):
        """Configure l'onglet des instructions."""
        layout = QVBoxLayout()
        self.instructions_text = QTextEdit()
        self.instructions_text.setReadOnly(True)
        self.instructions_text.setMinimumHeight(600)
        instructions = """
        <h2>Visualisation Constats Loup</h2>
        <h3>🚀 Chemins par défaut :</h3>
        <ul>
        <li><b>ODS :</b> <code>T:/30_BIODIV/ESPECE_PROTEG/LOUP_LYNX/NV_CONSTAT_INDEMN/5_TAB_SUIVI_CONSTAT_INDEMN/2_TAB_suivi_constat_conclusion.ods</code></li>
        <li><b>SHP :</b> <code>N:/BDCARTO_V5/1_DONNEES_LIVRAISON_2024-07-00018/ADMINISTRATIF/COMMUNE.shp</code></li>
        </ul>
        <h3>⚙️ Utilisation :</h3>
        <ol>
        <li><b>Vérifiez les statuts</b> (doivent être verts)</li>
        <li>Cliquez <b>"Lancer les traitements"</b></li>
        <li>Les fichiers source sont ajoutés au projet</li>
        <li>Utilisez l'animation pour visualiser (cumulatif ou mensuel)</li>
        </ol>
        """
        self.instructions_text.setHtml(instructions)
        layout.addWidget(self.instructions_text)
        self.instructions_tab = QWidget()
        self.instructions_tab.setLayout(layout)

    def setup_processing_tab(self):
        """Configure l'onglet de traitement."""
        layout = QVBoxLayout()
        path_layout = QFormLayout()
        ods_hlayout = QHBoxLayout()
        default_ods = "T:/30_BIODIV/ESPECE_PROTEG/LOUP_LYNX/NV_CONSTAT_INDEMN/5_TAB_SUIVI_CONSTAT_INDEMN/2_TAB_suivi_constat_conclusion.ods"
        self.ods_path_edit = QLineEdit(default_ods)
        self.ods_path_edit.textChanged.connect(lambda: self.check_file_status(self.ods_path_edit, self.ods_status_label))
        self.ods_browse_btn = QPushButton("...")
        self.ods_browse_btn.clicked.connect(lambda: self.browse_file(self.ods_path_edit, "Fichier ODS (*.ods)", self.ods_status_label))
        ods_hlayout.addWidget(self.ods_path_edit)
        ods_hlayout.addWidget(self.ods_browse_btn)
        self.ods_status_label = QLabel("Vérification...")
        self.ods_status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.check_file_status(self.ods_path_edit, self.ods_status_label)
        path_layout.addRow("Fichier ODS :", ods_hlayout)
        path_layout.addRow("Statut ODS :", self.ods_status_label)
        shp_hlayout = QHBoxLayout()
        default_shp = "N:/BDCARTO_V5/1_DONNEES_LIVRAISON_2024-07-00018/ADMINISTRATIF/COMMUNE.shp"
        self.shp_path_edit = QLineEdit(default_shp)
        self.shp_path_edit.textChanged.connect(lambda: self.check_file_status(self.shp_path_edit, self.shp_status_label))
        self.shp_browse_btn = QPushButton("...")
        self.shp_browse_btn.clicked.connect(lambda: self.browse_file(self.shp_path_edit, "Shapefile (*.shp)", self.shp_status_label))
        shp_hlayout.addWidget(self.shp_path_edit)
        shp_hlayout.addWidget(self.shp_browse_btn)
        self.shp_status_label = QLabel("Vérification...")
        self.shp_status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.check_file_status(self.shp_path_edit, self.shp_status_label)
        path_layout.addRow("Fichier SHP :", shp_hlayout)
        path_layout.addRow("Statut SHP :", self.shp_status_label)
        self.process_button = QPushButton("🚀 Lancer les traitements")
        self.process_button.clicked.connect(self.run_processing)
        path_layout.addRow(self.process_button)
        layout.addLayout(path_layout)
        self.filters_group = QGroupBox("Filtres")
        filters_layout = QGridLayout()
        conclusion_label = QLabel("<u>Conclusion technique</u>")
        conclusion_label.setStyleSheet("font-weight: bold;")
        filters_layout.addWidget(conclusion_label, 0, 0)
        self.conclusion_layout = QVBoxLayout()
        filters_layout.addLayout(self.conclusion_layout, 1, 0)
        elevage_label = QLabel("<u>Type d'espèces:</u>")
        elevage_label.setStyleSheet("font-weight: bold;")
        filters_layout.addWidget(elevage_label, 0, 1)
        self.elevage_layout = QVBoxLayout()
        filters_layout.addLayout(self.elevage_layout, 1, 1)
        self.filters_group.setLayout(filters_layout)
        self.filters_group.setVisible(False)
        layout.addWidget(self.filters_group)
        self.save_button = QPushButton("💾 Sauvegarder le projet")
        self.save_button.clicked.connect(self.save_layers_and_project)
        self.save_button.setVisible(False)
        layout.addWidget(self.save_button)
        animation_group = QGroupBox("Animation temporelle")
        animation_layout = QVBoxLayout()
        # Start year selection
        start_year_layout = QHBoxLayout()
        self.start_year_label = QLabel("Choisir l’année de départ :")
        self.year_combo = QComboBox()
        self.year_combo.currentIndexChanged.connect(self.update_start_year)
        start_year_layout.addWidget(self.start_year_label)
        start_year_layout.addWidget(self.year_combo)
        animation_layout.addLayout(start_year_layout)
        print("Start year UI added: label, year_combo")
        # Cumulative option
        cumulative_layout = QHBoxLayout()
        self.cumulative_label = QLabel("Option de cumul des constats")
        self.cumulative_checkbox = QCheckBox()
        self.cumulative_checkbox.setChecked(False)
        self.cumulative_checkbox.stateChanged.connect(self.toggle_cumulative_mode)
        cumulative_layout.addWidget(self.cumulative_label)
        cumulative_layout.addWidget(self.cumulative_checkbox)
        animation_layout.addLayout(cumulative_layout)
        print("Cumulative UI added: label, checkbox")
        time_step_layout = QHBoxLayout()
        time_step_label = QLabel("Durée par frame :")
        self.time_step_spin = QDoubleSpinBox()
        self.time_step_spin.setRange(0.1, 60.0)
        self.time_step_spin.setValue(0.5)
        self.time_step_spin.setSuffix(" s")
        time_step_layout.addWidget(time_step_label)
        time_step_layout.addWidget(self.time_step_spin)
        animation_layout.addLayout(time_step_layout)
        slider_layout = QHBoxLayout()
        slider_label = QLabel("Progression :")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setEnabled(False)
        self.slider.valueChanged.connect(self.slider_changed)
        slider_layout.addWidget(slider_label)
        slider_layout.addWidget(self.slider)
        animation_layout.addLayout(slider_layout)
        play_layout = QHBoxLayout()
        play_label = QLabel("Contrôle :")
        self.play_button = QPushButton("▶ Play")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.toggle_play)
        self.play_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Match slider width
        play_layout.addWidget(play_label)
        play_layout.addWidget(self.play_button)
        animation_layout.addLayout(play_layout)
        animation_group.setLayout(animation_layout)
        layout.addWidget(animation_group)
        self.processing_tab = QWidget()
        self.processing_tab.setLayout(layout)
        print("Processing tab setup completed")

    def export_crosstab_to_csv(self):
        """Exporte le tableau croisé dynamique en CSV."""
        output_dir = self.crosstab_output_dir_edit.text()
        if not output_dir:
            QMessageBox.warning(self, "Attention", "Veuillez choisir un dossier de sortie.")
            return

        if not hasattr(self, 'ods_layer') or not self.ods_layer:
            QMessageBox.warning(self, "Attention", "Aucune couche ODS disponible pour générer le TCD.")
            return

        output_path = os.path.join(output_dir, "tableau_croise_dynamique.csv")

        try:
            from .utils_visualisation_constats import generate_crosstab_data, write_crosstab_to_csv
            crosstab_data = generate_crosstab_data(self.ods_layer)
            write_crosstab_to_csv(crosstab_data, output_path)
            QMessageBox.information(self, "Succès", f"Tableau croisé dynamique sauvegardé dans : {output_path}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export du TCD : {str(e)}")
            print(f"ERREUR export_crosstab_to_csv: {str(e)}")

    def setup_recording_tab(self):
        """Configure l'onglet d'enregistrement."""
        layout = QVBoxLayout()
        png_group = QGroupBox("Exporter les cartes mensuelles en PNG")
        png_layout = QVBoxLayout()
        png_label = QLabel("Choisir le dossier d'export des cartes mensuelles :")
        png_layout.addWidget(png_label)
        png_dir_layout = QHBoxLayout()
        self.png_output_dir_edit = QLineEdit()
        self.png_output_dir_edit.setPlaceholderText("Chemin du dossier de sortie...")
        self.png_output_dir_edit.setReadOnly(True)
        png_browse_button = QPushButton("Parcourir...")
        png_browse_button.clicked.connect(lambda: self.choose_output_dir(self.png_output_dir_edit))
        png_dir_layout.addWidget(self.png_output_dir_edit)
        png_dir_layout.addWidget(png_browse_button)
        png_layout.addLayout(png_dir_layout)
        cumulative_png_layout = QHBoxLayout()
        self.png_cumulative_label = QLabel("Option de cumul pour l'export PNG depuis l’année :")
        self.png_cumulative_checkbox = QCheckBox()
        self.png_cumulative_checkbox.setChecked(False)
        self.png_cumulative_checkbox.stateChanged.connect(self.toggle_png_cumulative_mode)
        self.png_year_combo = QComboBox()
        self.png_year_combo.setEnabled(False)
        self.png_year_combo.currentIndexChanged.connect(self.update_png_start_year)
        cumulative_png_layout.addWidget(self.png_cumulative_label)
        cumulative_png_layout.addWidget(self.png_cumulative_checkbox)
        cumulative_png_layout.addWidget(self.png_year_combo)
        png_layout.addLayout(cumulative_png_layout)
        self.export_png_button = QPushButton("📷 Exporter en PNG")
        self.export_png_button.clicked.connect(self.export_png_with_progress)
        png_layout.addWidget(self.export_png_button)
        self.png_progress_bar = QProgressBar()
        self.png_progress_bar.setRange(0, 100)
        self.png_progress_bar.setValue(0)
        self.png_progress_bar.setVisible(False)
        png_layout.addWidget(self.png_progress_bar)
        png_group.setLayout(png_layout)
        layout.addWidget(png_group)
        mp4_group = QGroupBox("Exporter l'animation en MP4")
        mp4_layout = QVBoxLayout()
        mp4_label = QLabel("Choisir le dossier d'export de la vidéo :")
        mp4_layout.addWidget(mp4_label)
        mp4_dir_layout = QHBoxLayout()
        self.mp4_output_dir_edit = QLineEdit()
        self.mp4_output_dir_edit.setPlaceholderText("Chemin du dossier de sortie...")
        self.mp4_output_dir_edit.setReadOnly(True)
        mp4_browse_button = QPushButton("Parcourir...")
        mp4_browse_button.clicked.connect(lambda: self.choose_output_dir(self.mp4_output_dir_edit))
        mp4_dir_layout.addWidget(self.mp4_output_dir_edit)
        mp4_dir_layout.addWidget(mp4_browse_button)
        mp4_layout.addLayout(mp4_dir_layout)
        self.record_button = QPushButton("🎥 Enregistrer en MP4")
        self.record_button.clicked.connect(self.export_mp4_with_progress)
        self.record_button.setEnabled(False)
        mp4_layout.addWidget(self.record_button)
        self.mp4_progress_bar = QProgressBar()
        self.mp4_progress_bar.setRange(0, 100)
        self.mp4_progress_bar.setValue(0)
        self.mp4_progress_bar.setVisible(False)
        mp4_layout.addWidget(self.mp4_progress_bar)
        self.mp4_ffmpeg_label = QLabel("Vérification de FFmpeg en cours...")
        self.mp4_ffmpeg_label.setStyleSheet("color: orange; font-weight: bold;")
        mp4_layout.addWidget(self.mp4_ffmpeg_label)
        mp4_group.setLayout(mp4_layout)
        layout.addWidget(mp4_group)
        crosstab_group = QGroupBox("Exporter le tableau croisé dynamique (TCD) en CSV")
        crosstab_layout = QVBoxLayout()
        crosstab_label = QLabel("Choisir le dossier d'export du TCD :")
        crosstab_layout.addWidget(crosstab_label)
        crosstab_dir_layout = QHBoxLayout()
        self.crosstab_output_dir_edit = QLineEdit()
        self.crosstab_output_dir_edit.setPlaceholderText("Chemin du dossier de sortie...")
        self.crosstab_output_dir_edit.setReadOnly(True)
        crosstab_browse_button = QPushButton("Parcourir...")
        crosstab_browse_button.clicked.connect(lambda: self.choose_output_dir(self.crosstab_output_dir_edit))
        crosstab_dir_layout.addWidget(self.crosstab_output_dir_edit)
        crosstab_dir_layout.addWidget(crosstab_browse_button)
        crosstab_layout.addLayout(crosstab_dir_layout)
        self.export_crosstab_button = QPushButton("📊 Exporter le TCD en CSV")
        self.export_crosstab_button.clicked.connect(self.export_crosstab_to_csv)
        crosstab_layout.addWidget(self.export_crosstab_button)
        crosstab_group.setLayout(crosstab_layout)
        layout.addWidget(crosstab_group)
        self.recording_tab = QWidget()
        self.recording_tab.setLayout(layout)
        self.check_ffmpeg_availability()

    def check_ffmpeg_availability(self):
        """Vérifie si FFmpeg est disponible."""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            self.record_button.setEnabled(True)
            self.mp4_ffmpeg_label.setText("FFmpeg détecté.")
            self.mp4_ffmpeg_label.setStyleSheet("color: green; font-weight: bold;")
            print("FFmpeg disponible pour l'export MP4.")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.record_button.setEnabled(False)
            self.mp4_ffmpeg_label.setText("FFmpeg non détecté. Fonctionnalité MP4 désactivée. Installez FFmpeg et ajoutez-le au PATH système.")
            self.mp4_ffmpeg_label.setStyleSheet("color: red; font-weight: bold;")
            print("FFmpeg non disponible pour l'export MP4.")

    def toggle_cumulative_mode(self, state):
        """Active ou désactive le mode cumulatif pour l'animation."""
        self.cumulative_mode = state == Qt.Checked
        self.year_combo.setEnabled(True)  # Always enable year combo
        self.update_effective_layers()
        print(f"Mode cumulatif animation: {'Activé' if self.cumulative_mode else 'Désactivé'}")

    def toggle_png_cumulative_mode(self, state):
        """Active ou désactive le mode cumulatif pour l'export PNG."""
        self.png_cumulative_mode = state == Qt.Checked
        self.png_year_combo.setEnabled(self.png_cumulative_mode)
        print(f"Mode cumulatif PNG: {'Activé' if self.png_cumulative_mode else 'Désactivé'}")

    def update_start_year(self):
        """Met à jour l'année de départ pour l'animation."""
        if self.year_combo.currentText():
            self.start_year = int(self.year_combo.currentText())
            self.update_effective_layers()
            print(f"Année de départ animation: {self.start_year}")

    def update_png_start_year(self):
        """Met à jour l'année de départ pour l'export PNG."""
        if self.png_year_combo.currentText():
            self.png_start_year = int(self.png_year_combo.currentText())
            print(f"Année de départ PNG: {self.png_start_year}")

    def update_effective_layers(self):
        """Met à jour les couches effectives pour l'animation."""
        if not self.layers:
            print("Aucune couche dans self.layers pour update_effective_layers")
            return
        self.all_layers = sorted(self.layers, key=lambda x: (x[0], x[1]))
        if self.start_year is not None:
            self.effective_layers = [l for l in self.all_layers if l[0] >= self.start_year]
        else:
            self.effective_layers = self.all_layers
        self.slider.setMaximum(len(self.effective_layers) - 1 if self.effective_layers else 0)
        self.current_frame = 0
        self.slider.setValue(0)
        self.show_frame(0)
        print(f"Effective layers updated: {len(self.effective_layers)} layers")

    def choose_output_dir(self, line_edit):
        """Ouvre une boîte de dialogue pour choisir un dossier de sortie."""
        output_dir = QFileDialog.getExistingDirectory(self, "Choisir un dossier de sortie")
        if output_dir:
            line_edit.setText(output_dir)

    def export_png_with_progress(self):
        """Exporte les images PNG avec suivi de progression."""
        output_dir = self.png_output_dir_edit.text()
        if not output_dir:
            QMessageBox.warning(self, "Attention", "Veuillez choisir un dossier de sortie.")
            return
        if not self.layers:
            QMessageBox.warning(self, "Attention", "Aucune couche disponible pour l'export.")
            return
        valid_layers = [(y, m, l) for y, m, l in self.layers if l and l.isValid()]
        if not valid_layers:
            QMessageBox.warning(self, "Attention", "Aucune couche valide disponible pour l'export.")
            return
        if not self.available_years:
            self.available_years = sorted(set(year for year, _ in [(y, m) for y, m, _ in valid_layers]))
            self.png_year_combo.clear()
            self.png_year_combo.addItems([str(year) for year in self.available_years])
            if self.available_years:
                self.png_start_year = self.available_years[0]
                self.png_year_combo.setCurrentText(str(self.png_start_year))
        self.png_progress_bar.setVisible(True)
        self.png_progress_bar.setValue(0)
        def update_progress(value):
            self.png_progress_bar.setValue(value)
            QApplication.processEvents()
        if self.png_cumulative_mode and hasattr(self, 'png_start_year') and self.png_start_year is not None:
            export_layers = [l for y, m, l in sorted(valid_layers, key=lambda x: (x[0], x[1])) if y >= self.png_start_year]
        else:
            export_layers = sorted(valid_layers, key=lambda x: (x[0], x[1]))
        if not export_layers:
            QMessageBox.warning(self, "Attention", "Aucune couche valide après filtrage pour l'export.")
            return
        print(f"Export PNG: {len(export_layers)} couches à exporter")
        try:
            self.animation_exporter.record_animation_to_png(export_layers, self, output_dir, update_progress)
            self.png_progress_bar.setValue(100)
            QMessageBox.information(self, "Succès", f"Export PNG terminé. Les images sont dans : {output_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export PNG : {str(e)}")
            self.png_progress_bar.setValue(0)

    def export_mp4_with_progress(self):
        """Exporte la vidéo MP4 avec suivi de progression."""
        output_dir = self.mp4_output_dir_edit.text()
        if not output_dir:
            QMessageBox.warning(self, "Attention", "Veuillez choisir un dossier de sortie.")
            return
        if not self.layers:
            QMessageBox.warning(self, "Attention", "Aucune couche disponible pour l'export.")
            return
        output_file = os.path.join(output_dir, "animation_constats_loup.mp4")
        self.mp4_progress_bar.setVisible(True)
        self.mp4_progress_bar.setValue(0)
        def update_progress(value):
            self.mp4_progress_bar.setValue(value)
            QApplication.processEvents()
        if self.cumulative_mode and self.start_year is not None:
            export_layers = [l for y, m, l in self.all_layers if y >= self.start_year]
        else:
            export_layers = self.all_layers
        try:
            self.animation_exporter.record_animation_to_mp4(export_layers, self, output_file, update_progress)
            self.mp4_progress_bar.setValue(100)
            QMessageBox.information(self, "Succès", f"Vidéo enregistrée : {output_file}")
        except FileNotFoundError as e:
            if "ffmpeg" in str(e).lower():
                QMessageBox.critical(self, "Erreur", "FFmpeg non trouvé. Installez FFmpeg et ajoutez-le au PATH système.")
            else:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export MP4 : {str(e)}")
            self.mp4_progress_bar.setValue(0)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export MP4 : {str(e)}")
            self.mp4_progress_bar.setValue(0)

    def browse_file(self, line_edit, filter_str, status_label):
        """Ouvre une boîte de dialogue pour sélectionner un fichier."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Sélectionner un fichier", line_edit.text(), filter_str)
        if file_path:
            line_edit.setText(file_path)
            self.check_file_status(line_edit, status_label)

    def check_file_status(self, path_edit, status_label):
        """Vérifie et met à jour le statut d'un fichier."""
        path = path_edit.text().strip()
        if not path:
            status_label.setText("⚠️ Entrez un chemin")
            status_label.setStyleSheet("color: orange; font-weight: bold;")
            return
        if os.path.exists(path):
            status_label.setText("✅ Fichier trouvé")
            status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            status_label.setText("❌ Introuvable")
            status_label.setStyleSheet("color: red; font-weight: bold;")
            
    def populate_conclusion_checkboxes(self, ods_layer):
        try:
            while self.conclusion_layout.count():
                child = self.conclusion_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            conclusion_colors = self.layer_manager.conclusion_colors
            normalized_conclusion_map = {normalize_string(k): k for k in conclusion_colors.keys()}
            unique_normalized = set()
            for feature in ods_layer.getFeatures():
                conclusion = str(feature["C_tech_new"] or "")
                if conclusion:
                    unique_normalized.add(normalize_string(conclusion))
            sorted_standards = sorted(
                [normalized_conclusion_map.get(norm, 'Inconnu') for norm in unique_normalized],
                key=lambda x: x.lower()
            )
            for standard_conclusion in sorted_standards:
                hbox = QHBoxLayout()
                cb = QCheckBox(standard_conclusion)
                cb.setChecked(True)
                cb.stateChanged.connect(self.apply_filters_to_layers)
                self.conclusion_checkboxes[standard_conclusion] = cb
                hbox.addWidget(cb)
                color = conclusion_colors.get(standard_conclusion, 'grey')
                color_label = QLabel()
                color_label.setFixedSize(20, 20)
                color_label.setStyleSheet(f"background-color: {color}; border: 1px solid black;")
                hbox.addWidget(color_label)
                widget = QWidget()
                widget.setLayout(hbox)
                self.conclusion_layout.addWidget(widget)
            print(f"Checkboxes conclusions créées: {sorted_standards}")
        except Exception as e:
            print(f"ERREUR populate_conclusion: {str(e)}")

    def populate_elevage_checkboxes(self, ods_layer, show_symbols=True):
        """Crée checkboxes élevages, avec option pour afficher les symboles."""
        try:
            while self.elevage_layout.count():
                child = self.elevage_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            species_shapes = self.layer_manager.species_shapes
            unique_elevages = set()
            for feature in ods_layer.getFeatures():
                elevage = normalize_elevage(str(feature["Elevage"] or ""))
                if elevage:
                    unique_elevages.add(elevage)
                    print(f"Valeur Elevage brute: {feature['Elevage']}, normalisée: {elevage}")  # Débogage

            species_order = ["Bovin", "Caprin", "Equin", "Ovin", "Avicole", "Porcin", "Cunicole", "Canin", "Autres"]
            sorted_elevages = sorted(unique_elevages, key=lambda x: species_order.index(x) if x in species_order else len(species_order))

            for elevage in sorted_elevages:
                hbox = QHBoxLayout()
                cb = QCheckBox(elevage)
                cb.setChecked(True)
                cb.stateChanged.connect(self.apply_filters_to_layers)
                self.elevage_checkboxes[elevage] = cb
                hbox.addWidget(cb)

                if show_symbols:
                    shape = species_shapes.get(elevage, "circle")
                    print(f"Élevage: {elevage}, Forme assignée: {shape}")

                    # Créer un QPixmap propre
                    pixmap = QPixmap(20, 20)
                    pixmap.fill(Qt.transparent)

                    # --- Dessin sécurisé ---
                    painter = QPainter()
                    try:
                        if not painter.begin(pixmap):
                            raise RuntimeError("Impossible de démarrer QPainter sur QPixmap")

                        painter.setRenderHint(QPainter.Antialiasing, True)
                        painter.setPen(QPen(Qt.black, 1.2))
                        painter.setBrush(QBrush(QColor("#e0e0e0")))

                        margin = 3
                        rect = QRectF(margin, margin, 20 - 2*margin, 20 - 2*margin)

                        if shape == "circle":
                            painter.drawEllipse(rect)
                        elif shape == "square":
                            painter.drawRect(rect)
                        elif shape == "triangle":
                            path = QPainterPath()
                            path.moveTo(10, margin)
                            path.lineTo(20 - margin, 20 - margin)
                            path.lineTo(margin, 20 - margin)
                            path.closeSubpath()
                            painter.drawPath(path)
                        elif shape == "diamond":
                            path = QPainterPath()
                            path.moveTo(10, margin)           # Haut
                            path.lineTo(20 - margin, 10)      # Droite
                            path.lineTo(10, 20 - margin)      # Bas
                            path.lineTo(margin, 10)           # Gauche
                            path.closeSubpath()
                            painter.drawPath(path)
                        elif shape == "pentagon":
                            path = QPainterPath()
                            cx, cy, r = 10, 10, 7
                            import math
                            for i in range(5):
                                angle = 2 * math.pi * i / 5 - math.pi / 2
                                x = cx + r * math.cos(angle)
                                y = cy + r * math.sin(angle)
                                if i == 0:
                                    path.moveTo(x, y)
                                else:
                                    path.lineTo(x, y)
                            path.closeSubpath()
                            painter.drawPath(path)
                        elif shape == "hexagon":
                            path = QPainterPath()
                            cx, cy, r = 10, 10, 7
                            import math
                            for i in range(6):
                                angle = 2 * math.pi * i / 6
                                x = cx + r * math.cos(angle)
                                y = cy + r * math.sin(angle)
                                if i == 0:
                                    path.moveTo(x, y)
                                else:
                                    path.lineTo(x, y)
                            path.closeSubpath()
                            painter.drawPath(path)
                        elif shape == "star":
                            path = QPainterPath()
                            cx, cy = 10, 10
                            outer_r, inner_r = 8, 4
                            import math
                            for i in range(10):
                                r = outer_r if i % 2 == 0 else inner_r
                                angle = math.pi * i / 5
                                x = cx + r * math.cos(angle)
                                y = cy + r * math.sin(angle)
                                if i == 0:
                                    path.moveTo(x, y)
                                else:
                                    path.lineTo(x, y)
                            path.closeSubpath()
                            painter.drawPath(path)
                        elif shape == "cross":
                            painter.drawRect(6, 2, 8, 16)  # |
                            painter.drawRect(2, 6, 16, 8)  # -

                    except Exception as e:
                        print(f"ERREUR dessin symbole {shape}: {e}")
                        # Fallback : carré gris
                        painter.end()
                        pixmap.fill(QColor("lightgrey"))
                    finally:
                        if painter.isActive():
                            painter.end()
                        del painter  # ← CRUCIAL : libère les ressources

                    # Appliquer au QLabel
                    symbol_label = QLabel()
                    symbol_label.setFixedSize(20, 20)
                    symbol_label.setPixmap(pixmap)
                    symbol_label.setAlignment(Qt.AlignCenter)
                    hbox.addWidget(symbol_label)

                widget = QWidget()
                widget.setLayout(hbox)
                self.elevage_layout.addWidget(widget)

            print(f"Checkboxes élevages créées: {sorted_elevages}")
        except Exception as e:
            print(f"ERREUR populate_elevage: {str(e)}")

    def apply_filters_to_layers(self):
        """Applique les filtres."""
        try:
            elevage_filters = []
            for s, cb in self.elevage_checkboxes.items():
                if cb.isChecked():
                    escaped_s = s.replace("'", "''")
                    elevage_filters.append(f"\"Elevage\" ILIKE '{escaped_s}%'")
            conclusion_filters = []
            for c, cb in self.conclusion_checkboxes.items():
                if cb.isChecked():
                    escaped_c = c.replace("'", "''")
                    conclusion_filters.append(f"\"C_tech_new\" = '{escaped_c}'")
            elevage_filter = " OR ".join(elevage_filters) if elevage_filters else "1=1"
            conclusion_filter = " OR ".join(conclusion_filters) if conclusion_filters else "1=1"
            filter_expr = f"({elevage_filter}) AND ({conclusion_filter})"
            print(f"Expression de filtre appliquée: {filter_expr}")
            for _, _, layer in self.layers:
                if not layer:
                    continue
                layer.setSubsetString(filter_expr)
                print(f"Couche {layer.name()}: {layer.featureCount()} entités après filtre")
                layer.triggerRepaint()
            if self.global_layer:
                self.global_layer.setSubsetString(filter_expr)
                print(f"Couche Constats_Globaux: {self.global_layer.featureCount()} entités après filtre")
                self.global_layer.triggerRepaint()
            self.iface.mapCanvas().refresh()
        except Exception as e:
            print(f"ERREUR apply_filters: {str(e)}")



    def closeEvent(self, event):
        """Arrête le timer et supprime les fichiers temporaires."""
        if self.is_playing:
            self.timer.stop()
            self.is_playing = False
            self.play_button.setText("▶ Play")
        temp_files = [f for f in os.listdir(os.path.dirname(__file__)) if f.startswith("temp_")]
        for f in temp_files:
            try:
                os.remove(os.path.join(os.path.dirname(__file__), f))
            except Exception as e:
                print(f"Erreur suppression fichier temporaire {f}: {e}")
        event.accept()

    def range_commune(self, communes_layer):
        """Déplace la couche 'Communes' dans un groupe dédié en bas de la légende avec filtre INSEE_DEP."""
        if not communes_layer:
            print("ERREUR: Couche Communes non fournie")
            return None
        try:
            root = QgsProject.instance().layerTreeRoot()
            group_name = "Communes"
            group = root.findGroup(group_name)
            if not group:
                group = root.insertGroup(len(root.children()), group_name)

            # Créer une couche mémoire filtrée
            clone = QgsVectorLayer(
                f"Polygon?crs={communes_layer.crs().authid()}",
                "Communes",  # Keep original name for PNG export compatibility
                "memory"
            )
            if not clone.isValid():
                print("Erreur: Impossible de créer la couche clone des Communes")
                return None

            # Copier les champs
            clone_data_provider = clone.dataProvider()
            clone_data_provider.addAttributes(communes_layer.fields())
            clone.updateFields()

            # Créer une expression de filtre
            expression = QgsExpression('"INSEE_DEP" = \'21\'')
            if not expression.hasParserError():
                # Appliquer l'expression et ajouter les entités filtrées
                it = communes_layer.getFeatures(QgsFeatureRequest(expression))
                clone.startEditing()
                for feature in it:
                    new_feature = QgsFeature(clone.fields())
                    new_feature.setGeometry(feature.geometry())
                    new_feature.setAttributes(feature.attributes())
                    clone_data_provider.addFeature(new_feature)
                clone.commitChanges()
                print(f"Filtre appliqué à Communes: {clone.featureCount()} entités")
            else:
                print(f"Erreur dans l'expression: {expression.parserErrorString()}")
                return None

            # Supprimer l'ancienne couche
            QgsProject.instance().removeMapLayer(communes_layer.id())

            # Ajouter la nouvelle couche au groupe Communes
            QgsProject.instance().addMapLayer(clone, False)
            group.addLayer(clone)
            self.layer_manager.apply_commune_styling(clone)

            layer_node = group.findLayer(clone.id())
            if layer_node:
                layer_node.setItemVisibilityChecked(True)

            print(f"Couche Communes clonée et filtrée ajoutée, {clone.featureCount()} entités")
            return clone
        except Exception as e:
            print(f"ERREUR range_commune: {str(e)}")
            return None

    def run_processing(self):
        ods_path = self.ods_path_edit.text().strip()
        shp_path = self.shp_path_edit.text().strip()
        if not os.path.exists(ods_path) or not os.path.exists(shp_path):
            QMessageBox.critical(self, "Erreur", "Fichiers introuvables")
            return
        self.process_button.setEnabled(False)
        QApplication.processEvents()
        try:
            ods_layer, communes_layer = self.data_processor.load_data(ods_path, shp_path)
            self.ods_layer = ods_layer
            if not ods_layer or not communes_layer:
                QMessageBox.critical(self, "Erreur", "Couches ODS ou SHP non valides")
                return
            if ods_layer.featureCount() == 0:
                QMessageBox.warning(self, "Attention", "La couche ODS est vide")
                return
            if communes_layer.featureCount() == 0:
                QMessageBox.warning(self, "Attention", "La couche Communes est vide")
                return
            print(f"ODS chargé: {ods_layer.featureCount()} entités")

            # Appel de process_data et décompression des trois valeurs retournées
            matched_features, unmatched_count, temp_ods_layer = self.data_processor.process_data(ods_layer, communes_layer)
            print(f"Features appariées: {len(matched_features)}")

            # Utiliser temp_ods_layer pour regrouper les données par mois
            data_by_month = self.data_processor.group_data_by_month(temp_ods_layer)
            print(f"Groupes mensuels: {len(data_by_month)}")

            if not data_by_month:
                QMessageBox.warning(self, "Attention", "Aucun groupe mensuel créé")
                return

            self.layer_manager.add_commune_layer(communes_layer)
            self.layers = self.layer_manager.create_monthly_layers(temp_ods_layer, communes_layer, matched_features, data_by_month)
            print(f"Couches mensuelles créées: {[(year, month, layer.name() if layer else 'None') for year, month, layer in self.layers]}")

            global_layer = self.layer_manager.create_global_layer(temp_ods_layer, matched_features, data_by_month)
            self.global_layer = global_layer

            # Créer la couche Dates
            self.dates_layer = self.layer_manager.create_dates_layer(self.layers, ods_layer.crs().authid())
            if not self.dates_layer:
                print("ERREUR: La couche Dates n'a pas pu être créée.")
                QMessageBox.warning(self, "Attention", "La couche Dates n'a pas pu être créée.")
                return
            print(f"Couche Dates ajoutée avec {self.dates_layer.featureCount() if self.dates_layer else 0} entités")

            self.layer_manager.zoom_to_communes(communes_layer)
            if not self.layers or not global_layer or not communes_layer:
                QMessageBox.warning(self, "Attention", "Impossible de réorganiser les couches : données manquantes.")
                return
            if communes_layer:
                communes_layer = self.range_commune(communes_layer)
            if global_layer:
                root = QgsProject.instance().layerTreeRoot()
                all_layers = QgsProject.instance().mapLayers().values()
                custom_order = [global_layer] + [layer for layer in all_layers if layer != global_layer]
                root.setCustomLayerOrder(custom_order)
                global_node = root.findLayer(global_layer.id())
                if global_node:
                    global_node.setItemVisibilityChecked(False)
                print("Couche Constats_Globaux masquée")
            if self.dates_layer:
                dates_node = root.findLayer(self.dates_layer.id())
                if dates_node:
                    dates_node.setItemVisibilityChecked(True)
                print("Couche Dates rendue visible")
            constats_group = root.findGroup("Constats")

            self.available_years = sorted(set(year for year, _ in [(y, m) for y, m, _ in self.layers]))
            self.year_combo.clear()
            self.png_year_combo.clear()
            self.year_combo.addItems([str(year) for year in self.available_years])
            self.png_year_combo.addItems([str(year) for year in self.available_years])
            if self.available_years:
                self.start_year = self.available_years[0]
                self.png_start_year = self.available_years[0]
                self.year_combo.setCurrentText(str(self.start_year))
                self.png_year_combo.setCurrentText(str(self.png_start_year))
                print(f"Années disponibles: {self.available_years}, Année initiale: {self.start_year}")
            if self.layers:
                self.filters_group.setVisible(True)
                self.populate_conclusion_checkboxes(temp_ods_layer)  # Utiliser temp_ods_layer
                self.populate_elevage_checkboxes(temp_ods_layer, show_symbols=True)
                self.update_effective_layers()
                self.slider.setEnabled(True)
                self.play_button.setEnabled(True)
                self.save_button.setVisible(True)
                self.show_frame(0)
                success_message = f"{len(self.layers)} couches mensuelles créées"
                if global_layer:
                    success_message += f" et 1 couche globale créée avec {global_layer.featureCount()} constats"
                if unmatched_count > 0:
                    success_message += f"\n{unmatched_count} constats non joints"
                QMessageBox.information(self, "Succès", success_message)
                temp_files = [f for f in os.listdir(os.path.dirname(__file__)) if f.startswith("temp_")]
                for f in temp_files:
                    try:
                        os.remove(os.path.join(os.path.dirname(__file__), f))
                    except Exception as e:
                        print(f"Erreur suppression fichier temporaire {f}: {e}")
        except Exception as e:
            print(f"ERREUR run_processing: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self.process_button.setEnabled(True)


    def save_layers_and_project(self):
        """Sauvegarde les couches et le projet."""
        output_dir = QFileDialog.getExistingDirectory(self, "Choisir un dossier de sauvegarde")
        if not output_dir:
            return
        try:
            self.layer_manager.save_project(output_dir)
            QMessageBox.information(self, "Succès", f"Projet sauvegardé dans: {output_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde: {str(e)}")

    def slider_changed(self, value):
        """Affiche la couche correspondante au slider."""
        self.current_frame = value
        self.show_frame(value)

    def refresh_dates_layer_labels(self):
        """Reconfigure les étiquettes de la couche Dates."""
        if not hasattr(self, 'dates_layer') or not self.dates_layer or not self.dates_layer.isValid():
            print("ERREUR: Couche Dates non valide")
            return

        # Configurer les étiquettes
        text_format = QgsTextFormat()
        text_format.setFont(QFont("Arial", 16, QFont.Bold))
        text_format.setColor(QColor("red"))
        buffer = QgsTextBufferSettings()
        buffer.setEnabled(True)
        buffer.setSize(2)
        buffer.setColor(QColor("white"))
        text_format.setBuffer(buffer)
        label_settings = QgsPalLayerSettings()
        label_settings.fieldName = "month_key"
        label_settings.enabled = True
        label_settings.placement = QgsPalLayerSettings.OverPoint
        label_settings.setFormat(text_format)

        # Appliquer les paramètres d'étiquetage
        self.dates_layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
        self.dates_layer.setLabelsEnabled(True)

        # Rafraîchir la couche et le canevas
        self.dates_layer.triggerRepaint()
        self.iface.mapCanvas().refresh()
        print("Étiquettes de la couche Dates reconfigurées")

    def show_frame(self, index):
        """Affiche ou masque les couches selon l'index chronologique et met à jour l'affichage des dates."""
        if not self.effective_layers or index >= len(self.effective_layers):
            print(f"ERREUR show_frame: Index {index} invalide ou effective_layers vide")
            return
        try:
            root = QgsProject.instance().layerTreeRoot()

            # Hide all layers first
            for _, _, layer in self.all_layers:
                if layer:
                    layer_node = root.findLayer(layer.id())
                    if layer_node:
                        layer_node.setItemVisibilityChecked(False)

            if self.cumulative_mode:
                for i, (year, month, layer) in enumerate(self.all_layers):
                    if (year, month, layer) in self.effective_layers[:index + 1]:
                        if layer:
                            layer_node = root.findLayer(layer.id())
                            if layer_node:
                                layer_node.setItemVisibilityChecked(True)
                                print(f"Couche {layer.name()} visible")
            else:
                self.layer_manager.set_layer_visibility(index, self.effective_layers)

            # Update Dates layer
            if hasattr(self, 'dates_layer') and self.dates_layer and self.dates_layer.isValid():
                year, month, _ = self.effective_layers[index]
                month_key = f"{year}_{month:02d}"
                self.dates_layer.setSubsetString(f"month_key = '{month_key}'")
                self.dates_layer.triggerRepaint()
                dates_node = root.findLayer(self.dates_layer.id())
                if dates_node:
                    dates_node.setItemVisibilityChecked(True)
                    print(f"Couche Dates rendue visible pour {month_key}")

                # Appeler refresh_dates_layer_labels sans argument
                self.refresh_dates_layer_labels()

            self.iface.mapCanvas().refresh()
            year, month, layer = self.effective_layers[index]
            mode = 'Cumulatif' if self.cumulative_mode else 'Mensuel'
            print(f"Affichage frame {index}: {year}_{month:02d}, couche {layer.name()}, {layer.featureCount()} entités, Mode: {mode}")
        except Exception as e:
            print(f"ERREUR show_frame: {str(e)}")
            import traceback
            traceback.print_exc()


    def toggle_play(self):
        """Bascule entre lecture et pause de l'animation."""
        if self.is_playing:
            self.timer.stop()
            self.is_playing = False
            self.play_button.setText("▶ Play")
            print("Animation arrêtée")
        else:
            if not self.effective_layers:
                print("Aucune couche disponible pour l'animation")
                return
            self.is_playing = True
            self.play_button.setText("⏸ Pause")
            interval = int(self.time_step_spin.value() * 1000)
            self.timer.start(interval)
            print(f"Animation démarrée, intervalle: {interval}ms")

    def next_frame(self):
        """Passe à la frame suivante dans l'animation."""
        if not self.effective_layers:
            print("Aucune couche disponible dans next_frame")
            self.timer.stop()
            self.is_playing = False
            self.play_button.setText("▶ Play")
            return
        self.current_frame += 1
        if self.current_frame >= len(self.effective_layers):
            self.current_frame = 0
            print("Fin de l'animation, retour au début")
        self.slider.setValue(self.current_frame)
        self.show_frame(self.current_frame)
        print(f"Frame suivante affichée: index {self.current_frame}")

    def create_point_for_feature(self, point_layer, feature, match):
        """Crée un point pour un constat."""
        try:
            geom = match['feature'].geometry()
            if geom and not geom.isEmpty():
                
                pt=geom.pointOnSurface()
                if pt.isNull():
                    pt = geom.pointOnSurface()
                centroid=pt
                #centroid = geom.centroid()
                #if centroid.isNull():
                #    centroid = geom.pointOnSurface()

                new_feat = QgsFeature(point_layer.fields())
                new_feat.setAttributes(feature.attributes())
                new_feat.setGeometry(centroid)
                point_layer.dataProvider().addFeature(new_feat)

        except Exception as e:
            print(f"ERREUR création point: {str(e)}")