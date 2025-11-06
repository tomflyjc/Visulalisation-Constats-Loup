from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsField, QgsMarkerSymbol, QgsCategorizedSymbolRenderer,
    QgsRendererCategory, QgsProject, QgsSingleSymbolRenderer, QgsFillSymbol, QgsSymbolLayer,
    QgsTextFormat, QgsTextBufferSettings, QgsGeometry, QgsPointXY, QgsPalLayerSettings,
    QgsVectorLayerSimpleLabeling 
)
from qgis.core import QgsExpression
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QColor, QFont
from .utils_visualisation_constats import normalize_elevage, normalize_string
from PyQt5.QtCore import QVariant
import os
import re
import traceback

class LayerManagerVisualisationConstats:
    def __init__(self, iface):
        self.iface = iface
        self.conclusion_colors = {
                "Cause mortalité indéterminée - dégâts indemnisés": "lightblue",
                "Cause mortalité indéterminée - Sans indemnisation": "darkblue",
                "Grands prédateurs écartés": "green",
                "Lynx non écarté": "orange",
                "Loup non écarté": "darkred",
                "Indéterminé": "grey",
                "Prédation exclue": "pink",
                "attente conclusions": "yellow"
            }
        self.species_shapes = {
            "Bovin": "circle",
            "Caprin": "square",
            "Equin": "triangle",
            "Ovin": "diamond",
            "Avicole": "pentagon",
            "Porcin": "hexagon",
            "Cunicole": "star",
            "Canin": "cross",
            "Autres": "circle"
        }

    def add_layer_to_project(self, layer, name=None):
        """Ajoute une couche au projet."""
        if not layer or not layer.isValid():
            print(f"Erreur: Couche {name if name else 'sans nom'} non valide pour ajout au projet")
            return False
        try:
            if name:
                layer.setName(name)
            QgsProject.instance().addMapLayer(layer)
            print(f"Couche {layer.name()} ajoutée au projet")
            return True
        except Exception as e:
            print(f"ERREUR add_layer_to_project: {str(e)}")
            return False

    def apply_commune_styling(self, layer):
        """Applique un style simple aux communes."""
        try:
            symbol = QgsFillSymbol.createSimple({
                'color': 'transparent',
                'outline_color': 'lightgrey',
                'outline_width': '0.4'
            })
            renderer = QgsSingleSymbolRenderer(symbol)
            layer.setRenderer(renderer)
            layer.triggerRepaint()
            print(f"Style appliqué à la couche Communes: {layer.name()}")
        except Exception as e:
            print(f"ERREUR apply_commune_styling: {str(e)}")

    def add_commune_layer(self, communes_layer):
        """Ajoute la couche des communes au projet."""
        try:
            QgsProject.instance().addMapLayer(communes_layer, False)
            root = QgsProject.instance().layerTreeRoot()
            group = root.findGroup("Communes")
            if not group:
                group = root.insertGroup(len(root.children()), "Communes")
            group.addLayer(communes_layer)
            self.apply_commune_styling(communes_layer)
            print(f"Couche Communes ajoutée avec {communes_layer.featureCount()} entités")
        except Exception as e:
            print(f"ERREUR add_commune_layer: {str(e)}")
    
    def create_monthly_layers(self, ods_layer, communes_layer, matched_features, data_by_month):
        layers = []
        try:
            sorted_keys = sorted(data_by_month.keys(), key=lambda x: (x[0], x[1]), reverse=True)
            print(f"Clés mensuelles triées: {sorted_keys}")
            ods_filename = os.path.basename(ods_layer.source())
            print(f"Nom du fichier ODS: {ods_filename}")

            for year, month in sorted_keys:
                layer_name = f"constats_{year}_{month:02d}"
                layer = QgsVectorLayer(
                    f"Point?crs={communes_layer.crs().authid()}",
                    layer_name,
                    "memory"
                )
                if not layer.isValid():
                    print(f"Erreur: Couche {layer_name} non valide")
                    continue

                provider = layer.dataProvider()
                provider.addAttributes(ods_layer.fields())
                provider.addAttributes([
                    QgsField("Nom_init", QVariant.String),
                    QgsField("Nom_Insee", QVariant.String),
                    QgsField("C_tech_new", QVariant.String)
                ])
                layer.updateFields()
                layer.startEditing()

                feature_count = 0
                nom_init_idx = layer.fields().indexFromName("Nom_init")
                nom_insee_idx = layer.fields().indexFromName("Nom_Insee")
                c_tech_new_idx = layer.fields().indexFromName("C_tech_new")

                for feature in data_by_month[(year, month)]:
                    if feature.id() in matched_features:
                        new_feature = QgsFeature(layer.fields())
                        attributes = feature.attributes() + [None, None, None]
                        new_feature.setAttributes(attributes)

                        nom_init = matched_features[feature.id()]['nom_init']
                        nom_insee = matched_features[feature.id()]['nom_insee']
                        new_feature.setAttribute(nom_init_idx, nom_init)
                        new_feature.setAttribute(nom_insee_idx, nom_insee)

                        c_tech_new = feature["C_tech_new"]
                        new_feature.setAttribute(c_tech_new_idx, c_tech_new)

                        matched_commune = matched_features[feature.id()]['feature']
                        geom = matched_commune.geometry().pointOnSurface()
                        if geom is None or geom.isNull():
                            print(f"Géométrie vide pour commune {nom_insee}, skip feature ID {feature.id()}")
                            continue

                        new_feature.setGeometry(geom)
                        provider.addFeature(new_feature)
                        feature_count += 1
                        print(f"Ajout entité à {layer_name}: ID={feature.id()}, Nom_init={nom_init}, Nom_Insee={nom_insee}, C_tech_new={c_tech_new}")
                    else:
                        print(f"Entité ID {feature.id()} non appariée pour {layer_name}")

                layer.commitChanges()
                self.apply_combined_styling(layer)
                QgsProject.instance().addMapLayer(layer, False)
                root = QgsProject.instance().layerTreeRoot()
                group = root.findGroup("Constats")
                if not group:
                    group = root.insertGroup(0, "Constats")
                group.addLayer(layer)
                layers.append((year, month, layer))
                print(f"Couche {layer_name}: {feature_count} constats ajoutés")

            print(f"Couches mensuelles créées: {[(year, month, layer.name()) for year, month, layer in layers]}")
            return layers
        except Exception as e:
            print(f"ERREUR create_monthly_layers: {str(e)}")
            traceback.print_exc()
            return []

    def create_global_layer(self, ods_layer, matched_features, data_by_month):
        try:
            layer = QgsVectorLayer(
                f"Point?crs={ods_layer.crs().authid()}",
                "Constats_Globaux",
                "memory"
            )
            if not layer.isValid():
                print("Erreur: Couche Constats_Globaux non valide")
                return None

            provider = layer.dataProvider()
            provider.addAttributes(ods_layer.fields())
            provider.addAttributes([
                QgsField("Nom_init", QVariant.String),
                QgsField("Nom_Insee", QVariant.String),
                QgsField("C_tech_new", QVariant.String)
            ])
            layer.updateFields()
            layer.startEditing()

            feature_count = 0
            ods_filename = os.path.basename(ods_layer.source())
            print(f"Nom du fichier ODS pour Constats_Globaux: {ods_filename}")

            nom_init_idx = layer.fields().indexFromName("Nom_init")
            nom_insee_idx = layer.fields().indexFromName("Nom_Insee")
            c_tech_new_idx = layer.fields().indexFromName("C_tech_new")

            for feature_id, matched_info in matched_features.items():
                for (year, month), features in data_by_month.items():
                    for feature in features:
                        if feature.id() == feature_id:
                            new_feature = QgsFeature(layer.fields())
                            attributes = feature.attributes() + [None, None, None]
                            new_feature.setAttributes(attributes)

                            # Récupérer les valeurs de matched_features
                            nom_init = matched_info['nom_init']
                            nom_insee = matched_info['nom_insee']
                            new_feature.setAttribute(nom_init_idx, nom_init)
                            new_feature.setAttribute(nom_insee_idx, nom_insee)

                            # Copier la valeur de "C_tech_new" depuis la feature
                            c_tech_new = feature["C_tech_new"]
                            new_feature.setAttribute(c_tech_new_idx, c_tech_new)

                            # Géométrie
                            geom = matched_info['feature'].geometry().centroid()
                            if geom is None or geom.isNull():
                                print(f"Géométrie vide pour commune {nom_insee}, skip feature ID {feature_id}")
                                continue

                            new_feature.setGeometry(geom)
                            provider.addFeature(new_feature)
                            feature_count += 1
                            print(f"Ajout entité à Constats_Globaux: ID={feature_id}, Nom_init={nom_init}, Nom_Insee={nom_insee}, C_tech_new={c_tech_new}")
                            break
                    else:
                        continue
                    break

            layer.commitChanges()
            self.apply_combined_styling(layer)
            QgsProject.instance().addMapLayer(layer, False)
            root = QgsProject.instance().layerTreeRoot()
            group = root.findGroup("Constats")
            if not group:
                group = root.insertGroup(0, "Constats")
            group.addLayer(layer)
            print(f"Couche Constats_Globaux: {feature_count} constats ajoutés")
            return layer
        except Exception as e:
            print(f"ERREUR create_global_layer: {str(e)}")
            traceback.print_exc()
            return None

    def apply_combined_styling(self, layer):
        try:
            categories = []
            for conclusion, color in self.conclusion_colors.items():
                for species, shape in self.species_shapes.items():
                    symbol = QgsMarkerSymbol.createSimple({
                        'name': shape,
                        'color': color,
                        'size': '3',
                        'outline_color': 'black',
                        'outline_width': '0.2'
                    })
                    category = QgsRendererCategory(
                        f"{conclusion}|{species}",
                        symbol,
                        f"{conclusion} - {species}"
                    )
                    categories.append(category)
            renderer = QgsCategorizedSymbolRenderer(
                """concat("C_tech_new", '|', "Elevage")""",
                categories
            )
            layer.setRenderer(renderer)

            # Configuration des étiquettes avec Nom_Insee
            text_format = QgsTextFormat()
            text_format.setFont(QFont("Arial", 10))
            text_format.setColor(QColor("black"))
            buffer = QgsTextBufferSettings()
            buffer.setEnabled(True)
            buffer.setSize(1)
            buffer.setColor(QColor("white"))
            text_format.setBuffer(buffer)
            label_settings = QgsPalLayerSettings()
            label_settings.fieldName = "Nom_Insee"
            label_settings.enabled = True
            label_settings.placement = QgsPalLayerSettings.AroundPoint
            label_settings.setFormat(text_format)
            layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
            layer.setLabelsEnabled(True)
            layer.triggerRepaint()
            print(f"Style combiné et étiquettes Nom_Insee appliqués à {layer.name()}: {layer.featureCount()} entités rendues")
        except Exception as e:
            print(f"ERREUR apply_combined_styling: {str(e)}")



    def create_dates_layer(self, layers, crs):
        """Crée une couche de points pour les dates avec étiquettes."""
        try:
            # Créer la couche
            dates_layer = QgsVectorLayer("Point?crs=EPSG:2154", "Dates", "memory")
            if not dates_layer.isValid():
                print("Erreur: Impossible de créer la couche Dates")
                return None

            # Ajouter les champs
            provider = dates_layer.dataProvider()
            provider.addAttributes([
                QgsField("year", QVariant.Int),
                QgsField("month", QVariant.Int),
                QgsField("month_key", QVariant.String)
            ])
            dates_layer.updateFields()

            # Créer les entités
            dates_layer.startEditing()
            point_geom = QgsGeometry.fromPointXY(QgsPointXY(863800, 6764000))
            created_dates = []
            for year, month, constats_layer in layers:
                if not constats_layer or not constats_layer.isValid():
                    print(f"Couche constats_{year}_{month:02d} est None ou non valide, ignorée")
                    continue

                month_key = f"{year}_{month:02d}"
                feature = QgsFeature(dates_layer.fields())
                feature.setAttributes([year, month, month_key])
                feature.setGeometry(point_geom)
                provider.addFeature(feature)
                created_dates.append(month_key)

            dates_layer.commitChanges()

            if not created_dates:
                print("AVERTISSEMENT: Aucune entité ajoutée à la couche Dates")
                return None

            # Configurer les étiquettes
            text_format = QgsTextFormat()
            text_format.setFont(QFont("Arial", 16, QFont.Bold))
            text_format.setColor(QColor("red"))
            buffer = QgsTextBufferSettings()
            buffer.setEnabled(True)
            buffer.setSize(1)
            buffer.setColor(QColor("white"))
            text_format.setBuffer(buffer)

            label_settings = QgsPalLayerSettings()
            label_settings.fieldName = "to_string(\"year\") || '_' || lpad(to_string(\"month\"), 2, '0')"
            label_settings.enabled = True
            label_settings.placement = QgsPalLayerSettings.OverPoint
            label_settings.setFormat(text_format)

            dates_layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
            dates_layer.setLabelsEnabled(True)

            # Symbole invisible
            symbol = QgsMarkerSymbol.createSimple({
                'name': 'circle',
                'color': 'red',
                'size': '0',
                'outline_color': 'black',
                'outline_width': '0.5'
            })
            renderer = QgsSingleSymbolRenderer(symbol)
            dates_layer.setRenderer(renderer)
            dates_layer.updateExtents()
            dates_layer.triggerRepaint()

            # Ajouter la couche au projet
            QgsProject.instance().addMapLayer(dates_layer, False)
            root = QgsProject.instance().layerTreeRoot()
            group = root.findGroup("Constats")
            if not group:
                group = root.insertGroup(0, "Constats")
            group.addLayer(dates_layer)

            layer_node = root.findLayer(dates_layer.id())
            if layer_node:
                layer_node.setItemVisibilityChecked(True)
            self.iface.mapCanvas().refresh()
            print(f"Couche Dates ajoutée au projet, {dates_layer.featureCount()} entités")
            return dates_layer

        except Exception as e:
            print(f"ERREUR create_dates_layer: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

            
    def zoom_to_communes(self, communes_layer):
        """Zoom sur l'emprise des communes."""
        try:
            self.iface.mapCanvas().setExtent(communes_layer.extent())
            self.iface.mapCanvas().refresh()
            print("Zoom effectué sur l'emprise des communes")
        except Exception as e:
            print(f"ERREUR zoom_to_communes: {str(e)}")

    def save_project(self, output_dir):
        """Sauvegarde le projet et les couches."""
        try:
            for _, _, layer in self.layers:
                if layer:
                    output_path = os.path.join(output_dir, f"{layer.name()}.gpkg")
                    QgsVectorFileWriter.writeAsVectorFormat(layer, output_path, "ogr")
                    print(f"Couche {layer.name()} sauvegardée à {output_path}")
            if self.global_layer:
                output_path = os.path.join(output_dir, "Constats_Globaux.gpkg")
                QgsVectorFileWriter.writeAsVectorFormat(self.global_layer, output_path, "ogr")
                print(f"Couche Constats_Globaux sauvegardée à {output_path}")
            project_path = os.path.join(output_dir, "projet_constats_loup.qgs")
            QgsProject.instance().write(project_path)
            print(f"Projet sauvegardé à {project_path}")
        except Exception as e:
            print(f"ERREUR save_project: {str(e)}")
                
    def set_layer_visibility(self, index, layers):
        """Affiche uniquement la couche correspondant à l'index."""
        try:
            for i, (_, _, layer) in enumerate(layers):
                if not layer:
                    continue
                layer_node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
                if not layer_node:
                    continue
                layer_node.setItemVisibilityChecked(i == index)
                print(f"Couche {layer.name()} {'visible' if i == index else 'masquée'}")
            self.iface.mapCanvas().refresh()
        except Exception as e:
            print(f"ERREUR set_layer_visibility: {str(e)}")
