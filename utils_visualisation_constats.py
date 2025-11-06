# utils_visualisation_constats.py
import unicodedata
import re
import difflib
import csv
import datetime  
from collections import defaultdict

def generate_crosstab_data(ods_layer):
    """
    Génère les données pour un tableau croisé dynamique à partir de la couche ODS.
    Retourne un dictionnaire structuré comme suit :
    {
        "années": [2013, 2014, ...],
        "espèces": ["Bovins", "Ovin", ...],
        "conclusions": ["Loup non écarté", "Grands prédateurs écartés", ...],
        "data": {
            (année, espèce, conclusion): nombre_de_constats,
            ...
        },
        "totaux_par_conclusion_et_année": {
            (année, conclusion): total_toutes_espèces,
            ...
        }
    }
    """
    # Initialisation des structures de données
    data = defaultdict(int)
    totaux_par_conclusion_et_année = defaultdict(int)
    espèces = set()
    conclusions = set()
    années = set()

    # Champs de date possibles
    date_fields = ["date du constat", "Date du constat", "DATE"]

    for feature in ods_layer.getFeatures():
        # Récupérer l'année
        date_str = ""
        for field in date_fields:
            if field in feature.fields().names():
                raw_date = feature[field]
                date_str = str(raw_date or "").strip()
                if date_str:
                    break
        if not date_str:
            continue

        # Extraire l'année
        year = None
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
            try:
                date = datetime.datetime.strptime(date_str, fmt)
                year = date.year
                années.add(year)
                break
            except ValueError:
                continue
        if year is None:
            continue

        # Récupérer l'espèce et la conclusion
        espèce = normalize_elevage(str(feature["Elevage"] or ""))
        conclusion = str(feature["Conclusion technique"] or "")
        if not espèce or not conclusion:
            continue

        espèces.add(espèce)
        conclusions.add(conclusion)

        # Incrémenter les compteurs
        data[(year, espèce, conclusion)] += 1
        totaux_par_conclusion_et_année[(year, conclusion)] += 1

    return {
        "années": sorted(années),
        "espèces": sorted(espèces),
        "conclusions": sorted(conclusions),
        "data": data,
        "totaux_par_conclusion_et_année": totaux_par_conclusion_et_année
    }

def write_crosstab_to_csv(crosstab_data, output_path):
    """
    Écrit le tableau croisé dynamique dans un fichier CSV.
    Structure du CSV :
    - Une ligne par espèce.
    - Une colonne par conclusion technique, avec le nombre de constats.
    - Une colonne "Année" qui répète l'année pour chaque ligne.
    - Une colonne "Total" avec le total toutes espèces confondues pour chaque conclusion et année.
    """
    années = crosstab_data["années"]
    espèces = crosstab_data["espèces"]
    conclusions = crosstab_data["conclusions"]
    data = crosstab_data["data"]
    totaux = crosstab_data["totaux_par_conclusion_et_année"]

    with open(output_path, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=';')

        # Écrire l'en-tête
        header = ["Espèce", "Année"] + conclusions + ["Total"]
        writer.writerow(header)

        # Écrire les données
        for espèce in espèces:
            for année in années:
                row = [espèce, année]
                total_row = 0
                for conclusion in conclusions:
                    count = data.get((année, espèce, conclusion), 0)
                    row.append(count)
                    total_row += count
                # Ajouter le total pour la ligne (toutes espèces confondues)
                row.append(totaux.get((année, conclusion), 0) if conclusion else 0)
                writer.writerow(row)

    print(f"Tableau croisé dynamique sauvegardé dans : {output_path}")
 
def normalize_string(s):
    if not s:
        return ""
    s = str(s).lower().strip()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = s.replace("'", " ").replace("-", " ").replace("  ", " ")
    return s

def nettoie_chaine_majuscule(chaineutf8):
    """Nettoie une chaîne pour la comparaison."""
    if not chaineutf8:
        return ""
    chaineutf8 = str(chaineutf8).upper()
    chaineutf8 = re.sub(r'[^\w\s]', ' ', chaineutf8)
    chaineutf8 = re.sub('_', ' ', chaineutf8)
    chaineutf8 = chaineutf8.strip()
    chaineutf8 = re.sub(r'\s+', ' ', chaineutf8)
    return chaineutf8

"""
def cherche_nom(commune_name, dict_communes):
    normalized_commune = normalize_string(commune_name)
    for insee, (nom, _) in dict_communes.items():
        if normalize_string(nom) == normalized_commune:
            return insee
    return None
"""

def cherche_nom(nom, dict_communes):
    """Recherche floue du nom de commune dans dict_communes."""
    
    if not nom:
        return None
    nom_normalized = normalize_string(nom)
    if nom_normalized == normalize_string("Val-Larrey (ex Flée)"):
        return "21272"
    for insee, (nom_dict, _) in dict_communes.items():
        if normalize_string(nom_dict) == nom_normalized:
            return insee
    matches = difflib.get_close_matches(nom_normalized, [normalize_string(n) for n, _ in dict_communes.values()], n=1, cutoff=0.8)
    if matches:
        for insee, (nom_dict, _) in dict_communes.items():
            if normalize_string(nom_dict) == matches[0]:
                return insee
    nom_clean = nettoie_chaine_majuscule(nom)
    max_sim = -1
    best_match = None
    for insee, (nom_commune, _) in dict_communes.items():
        nomC = nettoie_chaine_majuscule(nom_commune)
        if nomC:
            sim = difflib.SequenceMatcher(None, nom_clean, nomC).ratio()
            if sim > max_sim:
                max_sim = sim
                best_match = insee
    if max_sim >= 0.6:
        print(f"Match trouvé pour '{nom}' avec INSEE {best_match} (similarité: {max_sim})")
        return best_match
    print(f"Aucun match pour '{nom}' (meilleure similarité: {max_sim})")
    return None

def normalize_elevage(elevage):
    """Normalise les noms d'élevage."""
    norm = normalize_string(elevage)
    if norm.startswith('bovin'):
        return 'Bovin'
    elif norm.startswith('caprin'):
        return 'Caprin'
    elif norm.startswith('equin'):
        return 'Equin'
    elif norm.startswith('ovin'):
        return 'Ovin'
    elif norm.startswith('avicole'):
        return 'Avicole'
    elif norm.startswith('porcin'):
        return 'Porcin'
    elif norm.startswith('cunicole'):
        return 'Cunicole'
    elif norm.startswith('canin'):
        return 'Canin'
    else:
        return 'Autres'
        
