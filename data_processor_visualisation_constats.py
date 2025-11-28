#data_processor_visualisation_constats.py
from qgis.core import QgsVectorLayer, QgsFeature, QgsField
from .utils_visualisation_constats import normalize_string, normalize_elevage, nettoie_chaine_majuscule, cherche_nom
import datetime
import os
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QVariant

class DataProcessorVisualisationConstats:
    def load_ods_layer(self, path):
        """Charge le fichier ODS."""
        ods_uris = [f"{path}|layerid=0", f"{path}|layerid=1", path]
        for uri in ods_uris:
            layer = QgsVectorLayer(uri, "Constats_Loups_ODS", "ogr")
            if layer.isValid() and layer.featureCount() > 0:
                print(f"ODS chargé avec succès via URI: {uri}, {layer.featureCount()} entités")
                # Vérifier les champs disponibles
                fields = [field.name() for field in layer.fields()]
                print(f"Champs ODS: {fields}")
                # Afficher jusqu'à 5 entités pour débogage
                count = 0
                for feature in layer.getFeatures():
                    if count >= 5:  # Limiter à 5 entités
                        break
                    print(f"Entité ODS ID {feature.id()}: Commune={feature['commune']}, Conclusion={feature['Conclusion technique']}, Date={feature['date du constat']}")
                    count += 1
                return layer
        print("Erreur: Aucune URI valide pour le fichier ODS")
        return None

    def load_shp_layer(self, path):
        """Charge le fichier SHP."""
        layer = QgsVectorLayer(path, "Communes", "ogr")
        if not layer.isValid():
            print("Erreur: Couche SHP non valide")
            return None
        print(f"SHP chargé avec succès: {layer.featureCount()} entités")
        return layer

    def load_data(self, ods_path, shp_path):
        """Charge les fichiers ODS et SHP."""
        ods_layer = self.load_ods_layer(ods_path)
        shp_layer = self.load_shp_layer(shp_path)
        return ods_layer, shp_layer

    def prepare_dict_communes(self, shp_layer):
        """Crée un dictionnaire des communes."""
        dict_communes = {}
        insee_fields = ["INSEE", "CODE_INSEE", "code_insee", "INSEE_COM"]
        nom_fields = ["NOM", "NOM_COM", "nom", "NOM_COMM"]
        for feature in shp_layer.getFeatures():
            insee = None
            for insee_field in insee_fields:
                if insee_field in feature.fields().names():
                    insee = str(feature[insee_field] or "")
                    break
            if not insee:
                continue
            nom = None
            for nom_field in nom_fields:
                if nom_field in feature.fields().names():
                    nom = str(feature[nom_field] or "")
                    break
            if not nom:
                nom = f"Commune_{insee}"
            dict_communes[insee] = (nom, feature)
        print(f"Dictionnaire des communes créé: {len(dict_communes)} communes")
        # Commenter l'appel à QMessageBox pour éviter l'erreur
        # QMessageBox.information(self, "Dictionnaire des communes créé:", str(dict_communes))
        return dict_communes

    def match_ods_features(self, ods_layer, shp_layer):
        """Effectue la jointure floue."""
        dict_communes = self.prepare_dict_communes(shp_layer)
        dico_test = {}
        matched = {}
        unmatched = []
        for feature in ods_layer.getFeatures():
            try:
                commune_fields = ["commune", "Commune", "COMMUNE"]
                commune_name = ""
                for field in commune_fields:
                    if field in feature.fields().names():
                        raw_value = feature[field]
                        commune_name = str(raw_value or "").strip()
                        if commune_name:
                            break
                if not commune_name:
                    unmatched.append((feature.id(), "Inconnue", str(feature["Conclusion technique"] or ""), str(feature["Elevage"] or "")))
                    print(f"Pas de commune trouvée pour feature ID: {feature.id()}")
                    continue
                insee = cherche_nom(commune_name, dict_communes)
                if insee and insee in dict_communes:
                    matched[feature.id()] = {
                        'insee': insee,
                        'feature': dict_communes[insee][1],
                        'nom_insee': dict_communes[insee][0], # Stocker le nom pour Nom_Insee
                        'nom_init':commune_name
                    }
                    dico_test[insee] = (commune_name, dict_communes[insee][1])
                    print(f"Match trouvé: {commune_name} -> INSEE={insee}, Nom={dict_communes[insee][0]}")
                else:
                    dico_test[insee] = (commune_name, f"Pas de commune trouvée pour feature ID: {feature.id()}")
                    unmatched.append((feature.id(), commune_name, str(feature["Conclusion technique"] or ""), str(feature["Elevage"] or "")))
                    print(f"Pas de correspondance pour la commune '{commune_name}' (ID: {feature.id()})")
            except Exception as e:
                print(f"ERREUR match feature {feature.id()}: {str(e)}")
                continue
        print(f"Jointure floue terminée: {len(matched)} matched, {len(unmatched)} unmatched")
        return matched, unmatched 

    def create_unmatched_report(self, unmatched):
        """Génère un rapport pour les constats non joints."""
        if unmatched:
            message = f"{len(unmatched)} constats non joints aux communes:\n\n"
            for id, commune, conclusion, espece in unmatched:
                message += f"ID: {id}, Commune: {commune}, Conclusion: {conclusion}, Espèce: {espece}\n"
            print(f"Constats non joints: {message}")
            return len(unmatched), message
        print("Aucun constat non joint trouvé.")
        return 0, "Aucun constat non joint trouvé."


    def process_data(self, ods_layer, shp_layer):
        try:
            # Créer une copie en mémoire de la couche ODS pour standardiser les champs
            temp_ods_layer = QgsVectorLayer(
                f"Point?crs={ods_layer.crs().authid()}",
                "Temp_ODS",
                "memory"
            )
            if not temp_ods_layer.isValid():
                print("ERREUR: Impossible de créer la couche temporaire ODS")
                return {}, 0, None

            # Copier les champs et ajouter le champ "C_tech_new"
            provider = temp_ods_layer.dataProvider()
            provider.addAttributes(ods_layer.fields())
            provider.addAttributes([QgsField("C_tech_new", QVariant.String)])
            temp_ods_layer.updateFields()

            # Standardiser les champs dans la couche temporaire
            temp_ods_layer.startEditing()
            for feature in ods_layer.getFeatures():
                new_feature = QgsFeature(temp_ods_layer.fields())
                new_feature.setAttributes(feature.attributes() + [None])

                # Standardiser "Conclusion technique" en fonction de "Indemnisation"
                conclusion = str(feature["Conclusion technique"] or "")
                indemnisation = str(feature["Indemnisation"] or "").upper()

                if conclusion == "Cause mortalité indéterminée":
                    if indemnisation == "OUI":
                        c_tech_new = "Cause mortalité indéterminée - dégâts indemnisés"
                    elif indemnisation == "NON":
                        c_tech_new = "Cause mortalité indéterminée - Sans indemnisation"
                    else:
                        c_tech_new = conclusion
                else:
                    c_tech_new = conclusion

                c_tech_new_idx = temp_ods_layer.fields().indexFromName("C_tech_new")
                new_feature.setAttribute(c_tech_new_idx, c_tech_new)

                # Standardiser "Conclusion technique" pour la couche temporaire
                new_feature["Conclusion technique"] = c_tech_new

                # Standardiser "Elevage"
                elevage = normalize_elevage(str(feature["Elevage"] or ""))
                new_feature["Elevage"] = elevage

                # Copier la géométrie
                new_feature.setGeometry(feature.geometry())
                provider.addFeature(new_feature)

            temp_ods_layer.commitChanges()
            print(f"Couche temporaire créée avec {temp_ods_layer.featureCount()} entités")

            # Préparer le dictionnaire des communes
            dict_communes = self.prepare_dict_communes(shp_layer)

            # Effectuer la jointure floue sur la couche temporaire
            matched, unmatched = self.match_ods_features(temp_ods_layer, shp_layer)
            unmatched_count, unmatched_message = self.create_unmatched_report(unmatched)

            # Retourner la couche temporaire
            return matched, unmatched_count, temp_ods_layer

        except Exception as e:
            print(f"ERREUR process_data: {str(e)}")
            return {}, 0, None

    def group_data_by_month(self, ods_layer):
        """Groupe les données par mois."""
        try:
            data_by_month = {}
            date_fields = ["date du constat", "Date du constat", "DATE"]
            feature_count = 0
            for feature in ods_layer.getFeatures():
                date_str = ""
                for field in date_fields:
                    if field in feature.fields().names():
                        raw_date = feature[field]
                        date_str = str(raw_date or "").strip()
                        if date_str:
                            break
                if not date_str:
                    print(f"Date vide ignorée pour feature ID: {feature.id()}")
                    continue
                for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
                    try:
                        date = datetime.datetime.strptime(date_str, fmt)
                        key = (date.year, date.month)
                        data_by_month.setdefault(key, []).append(feature)
                        feature_count += 1
                        print(f"Feature ID: {feature.id()} groupée pour {key}")
                        break
                    except ValueError:
                        continue
                else:
                    print(f"Date invalide ignorée: {date_str} pour feature ID: {feature.id()}")
            print(f"Données groupées par mois: {len(data_by_month)} groupes, {feature_count} entités")
            print(f"Clés de groupement: {sorted(data_by_month.keys())}")
            return data_by_month
        except Exception as e:
            print(f"ERREUR group_data_by_month: {str(e)}")
            return {}