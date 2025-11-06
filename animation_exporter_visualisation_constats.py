from qgis.core import (
    QgsPrintLayout, QgsLayoutItemMap, QgsLayoutItemLabel, QgsLayoutExporter,
    QgsLayoutPoint, QgsLayoutSize, QgsProject, QgsLayoutManager, QgsUnitTypes
)
from qgis.core import QgsTextFormat
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QProgressBar
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt
import os
import tempfile
import shutil
import subprocess
import time
from PyQt5.QtWidgets import QApplication

class AnimationExporterVisualisationConstats:
    def __init__(self, iface):
        self.iface = iface

    def record_animation_to_png(self, layers, dialog, output_dir, progress_callback=None):
        """Exporte chaque frame en PNG avec layout portrait, étendue globale et couche Dates."""
        if not output_dir:
            QMessageBox.warning(dialog, "Attention", "Veuillez choisir un dossier de sortie.")
            return
        if not layers:
            QMessageBox.warning(dialog, "Attention", "Aucune couche disponible pour l'export.")
            return

        # Récupérer les couches "Communes" et "Dates"
        communes_layer = None
        dates_layer = None
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == "Communes":
                communes_layer = layer
            elif layer.name() == "Dates":
                dates_layer = layer

        if not communes_layer:
            QMessageBox.warning(dialog, "Attention", "Couche 'Communes' introuvable. Utilisation de l'étendue par défaut.")
            return

        # Calculer l'étendue globale (avec une marge de 10%)
        global_extent = communes_layer.extent()
        global_extent.scale(1.1)

        # Créer le layout
        project = QgsProject.instance()
        manager = project.layoutManager()
        layout_name = "Export_Constats_Loup"
        layouts = manager.layouts()
        for existing_layout in layouts:
            if existing_layout.name() == layout_name:
                manager.removeLayout(existing_layout)

        layout = QgsPrintLayout(project)
        layout.initializeDefaults()
        layout.setName(layout_name)
        manager.addLayout(layout)

        # Configurer la page
        pc = layout.pageCollection()
        pc.pages()[0].setPageSize(QgsLayoutSize(210, 297, QgsUnitTypes.LayoutMillimeters))

        # Ajouter la carte
        map_item = QgsLayoutItemMap(layout)
        map_item.attemptMove(QgsLayoutPoint(10, 30, QgsUnitTypes.LayoutMillimeters))
        map_item.attemptResize(QgsLayoutSize(190, 250, QgsUnitTypes.LayoutMillimeters))
        map_item.setExtent(global_extent)
        layout.addLayoutItem(map_item)

        # Ajouter le titre
        # Nouveau code
        title_item = QgsLayoutItemLabel(layout)
        title_item.setText("Bilan des constats pour l'année YYYY, mois : MM")

        # Créer un format de texte
        text_format = QgsTextFormat()
        text_format.setFont(QFont("Arial", 16))
        text_format.setSize(16)
        text_format.setColor(QColor("black"))

        # Appliquer le format
        title_item.setTextFormat(text_format)
        """
        title_item = QgsLayoutItemLabel(layout)
        title_item.setText("Bilan des constats pour l'année YYYY, mois : MM")
        font = QFont("Arial", 16)
        font.setBold(True)
        title_item.setFont(font)
        title_item.adjustSizeToText()
        title_item.attemptMove(QgsLayoutPoint(10, 10, QgsUnitTypes.LayoutMillimeters))
        layout.addLayoutItem(title_item)
        """
        # S'assurer que la couche Dates est visible
        root = QgsProject.instance().layerTreeRoot()
        if dates_layer:
            dates_tree_layer = root.findLayer(dates_layer.id())
            if dates_tree_layer:
                dates_tree_layer.setItemVisibilityChecked(True)

        # Exporter les frames
        total_frames = len(layers)
        for i, (year, month, layer) in enumerate(layers):
            if not layer or not layer.isValid():
                print(f"Couche {year}_{month:02d} non valide, ignorée")
                continue
            title_item.setText(f"Bilan des constats pour l'année {year}, mois : {month:02d}")

            # Gérer l'affichage des couches en fonction du mode cumulatif
            for l in layers:
                tree_layer = root.findLayer(l[2].id())
                if tree_layer:
                    if dialog.png_cumulative_mode:
                        # En mode cumulatif, afficher toutes les couches jusqu'à l'index actuel
                        tree_layer.setItemVisibilityChecked(l in layers[:i + 1])
                    else:
                        # En mode non cumulatif, afficher uniquement la couche courante
                        tree_layer.setItemVisibilityChecked(l == (year, month, layer))

            # Synchroniser la couche Dates
            if dates_layer:
                month_key = f"{year}_{month:02d}"
                dates_layer.setSubsetString(f"month_key = '{month_key}'")
                dates_layer.triggerRepaint()

            # Ajouter les couches à la carte
            map_layers = [communes_layer]
            if dialog.png_cumulative_mode:
                map_layers.extend([l[2] for l in layers[:i + 1] if l[2] and l[2].isValid()])
            else:
                map_layers.append(layer)
            if dates_layer:
                map_layers.append(dates_layer)
            map_item.setLayers(map_layers)

            # Rafraîchir la carte
            self.iface.mapCanvas().refresh()
            time.sleep(0.5)
            QApplication.processEvents()

            # Exporter l'image
            exporter = QgsLayoutExporter(layout)
            output_path = os.path.join(output_dir, f"{i+1}_constats_{year:04d}_{month:02d}.png")
            exporter.exportToImage(output_path, QgsLayoutExporter.ImageExportSettings())

            # Mettre à jour la progression
            if progress_callback:
                progress_callback(int(((i + 1) / total_frames) * 100))

        # Nettoyer
        manager.removeLayout(layout)
        print(f"Export PNG terminé: {total_frames} images générées dans {output_dir}")

    def record_animation_to_mp4(self, layers, dialog, output_file, progress_callback=None):
        """Enregistre l'animation en MP4 avec layout portrait, étendue globale et couche Dates."""
        if not output_file:
            QMessageBox.warning(dialog, "Attention", "Veuillez choisir un fichier de sortie.")
            return
        if not layers:
            QMessageBox.warning(dialog, "Attention", "Aucune couche disponible pour l'export.")
            return

        # Récupérer les couches "Communes" et "Dates"
        communes_layer = None
        dates_layer = None
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == "Communes":
                communes_layer = layer
            elif layer.name() == "Dates":
                dates_layer = layer

        if not communes_layer:
            QMessageBox.warning(dialog, "Attention", "Couche 'Communes' introuvable. Utilisation de l'étendue par défaut.")
            return

        # Calculer l'étendue globale (avec une marge de 10%)
        global_extent = communes_layer.extent()
        global_extent.scale(1.1)

        # Créer un dossier temporaire pour les frames
        temp_dir = tempfile.mkdtemp()
        try:
            # Créer le layout
            project = QgsProject.instance()
            manager = project.layoutManager()
            layout_name = "Export_Constats_Loup_Video"
            layouts = manager.layouts()
            for existing_layout in layouts:
                if existing_layout.name() == layout_name:
                    manager.removeLayout(existing_layout)

            layout = QgsPrintLayout(project)
            layout.initializeDefaults()
            layout.setName(layout_name)
            manager.addLayout(layout)

            pc = layout.pageCollection()
            pc.pages()[0].setPageSize(QgsLayoutSize(210, 297, QgsUnitTypes.LayoutMillimeters))

            map_item = QgsLayoutItemMap(layout)
            map_item.attemptMove(QgsLayoutPoint(10, 30, QgsUnitTypes.LayoutMillimeters))
            map_item.attemptResize(QgsLayoutSize(190, 250, QgsUnitTypes.LayoutMillimeters))
            map_item.setExtent(global_extent)
            layout.addLayoutItem(map_item)
            
            title_item = QgsLayoutItemLabel(layout)
            title_item.setText("Bilan des constats pour l'année YYYY, mois : MM")

            text_format = QgsTextFormat()
            text_format.setFont(QFont("Arial", 16))
            text_format.setSize(16)
            text_format.setColor(QColor("black"))

            title_item.setTextFormat(text_format)
            title_item.adjustSizeToText()
            title_item.attemptMove(QgsLayoutPoint(10, 10, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(title_item)

            """
            title_item = QgsLayoutItemLabel(layout)
            title_item.setText("Bilan des constats pour l'année YYYY, mois : MM")
            font = QFont("Arial", 16)
            font.setBold(True)
            title_item.setFont(font)
            title_item.adjustSizeToText()
            title_item.attemptMove(QgsLayoutPoint(10, 10, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(title_item)
            """
            # S'assurer que la couche Dates est visible
            root = QgsProject.instance().layerTreeRoot()
            if dates_layer:
                dates_tree_layer = root.findLayer(dates_layer.id())
                if dates_tree_layer:
                    dates_tree_layer.setItemVisibilityChecked(True)

            # Exporter les frames
            total_frames = len(layers)
            for i, (year, month, layer) in enumerate(layers):
                if not layer or not layer.isValid():
                    print(f"Couche {year}_{month:02d} non valide, ignorée")
                    continue
                title_item.setText(f"Bilan des constats pour l'année {year}, mois : {month:02d}")

                # Gérer l'affichage des couches en fonction du mode cumulatif
                for l in layers:
                    tree_layer = root.findLayer(l[2].id())
                    if tree_layer:
                        if dialog.cumulative_mode:
                            tree_layer.setItemVisibilityChecked(l in layers[:i + 1])
                        else:
                            tree_layer.setItemVisibilityChecked(l == (year, month, layer))

                # Synchroniser la couche Dates
                if dates_layer:
                    month_key = f"{year}_{month:02d}"
                    dates_layer.setSubsetString(f"month_key = '{month_key}'")
                    dates_layer.triggerRepaint()

                # Ajouter les couches à la carte
                map_layers = [communes_layer]
                if dialog.cumulative_mode:
                    map_layers.extend([l[2] for l in layers[:i + 1] if l[2] and l[2].isValid()])
                else:
                    map_layers.append(layer)
                if dates_layer:
                    map_layers.append(dates_layer)
                map_item.setLayers(map_layers)

                # Rafraîchir la carte
                self.iface.mapCanvas().refresh()
                time.sleep(0.5)
                QApplication.processEvents()

                # Exporter l'image
                exporter = QgsLayoutExporter(layout)
                frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                exporter.exportToImage(frame_path, QgsLayoutExporter.ImageExportSettings())

                # Mettre à jour la progression (50% pour les frames)
                if progress_callback:
                    progress_callback(int(((i + 1) / total_frames) * 50))

            # Nettoyer le layout
            manager.removeLayout(layout)

            # Créer la vidéo avec FFmpeg
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",  # Overwrite output
                "-framerate", "2",
                "-i", os.path.join(temp_dir, "frame_%04d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                output_file
            ]

            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            # Mettre à jour la progression (100% après création de la vidéo)
            if progress_callback:
                progress_callback(100)

        except subprocess.CalledProcessError as e:
            QMessageBox.critical(dialog, "Erreur", f"Échec de la création de la vidéo : {e.stderr.decode() if e.stderr else str(e)}")
        except FileNotFoundError as e:
            if "ffmpeg" in str(e).lower():
                QMessageBox.critical(dialog, "Erreur", "FFmpeg non trouvé. Installez FFmpeg et ajoutez-le au PATH système.")
            else:
                QMessageBox.critical(dialog, "Erreur", f"Erreur lors de l'export MP4 : {str(e)}")
        except Exception as e:
            QMessageBox.critical(dialog, "Erreur", f"Erreur lors de l'export MP4 : {str(e)}")
        finally:
            # Nettoyer le dossier temporaire
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"Nettoyage dossier temporaire: {temp_dir}")