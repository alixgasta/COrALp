"""Conteggio delle occorrenze GBIF per una checklist botanica nelle aree ALCOTRA.

Dipendenze: pandas, requests, openpyxl (per file .xlsx).
Il file di input deve contenere una colonna 'parsed_name' oppure una colonna
con un nome riconoscibile come 'specie'.
"""

import io
import json
import time
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd
import requests

GBIF_API = "https://api.gbif.org/v1"
GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_{iso}_{lvl}.json.zip"

# Nome area: (codice ISO3, livello amministrativo GADM, nome nel GeoJSON)
AREE_ALCOTRA = {
    "Torino": ("ITA", 2, "Torino"),
    "Cuneo": ("ITA", 2, "Cuneo"),
    "Imperia": ("ITA", 2, "Imperia"),
    "Valle d'Aosta": ("ITA", 1, "Valle d'Aosta"),
    "Haute-Savoie": ("FRA", 2, "Haute-Savoie"),
    "Savoie": ("FRA", 2, "Savoie"),
    "Hautes-Alpes": ("FRA", 2, "Hautes-Alpes"),
    "Alpes-de-Haute-Provence": ("FRA", 2, "Alpes-de-Haute-Provence"),
    "Alpes-Maritimes": ("FRA", 2, "Alpes-Maritimes"),
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "COrALp-GBIF-checklist/1.0 (research use)"})

PAUSA_TRA_QUERY = 0.5  # secondi tra una query e l'altra


def get_con_retry(url, params=None, timeout=30, tentativi=6):
    """GET con nuovi tentativi in caso di 429 (troppe richieste) o errori temporanei del server."""
    attesa = 2
    for n in range(tentativi):
        response = SESSION.get(url, params=params, timeout=timeout)
        if response.status_code in (429, 500, 502, 503, 504):
            if n == tentativi - 1:
                break
            try:
                pausa = float(response.headers.get("Retry-After", attesa))
            except ValueError:
                pausa = attesa
            print(f"      HTTP {response.status_code}: nuovo tentativo tra {pausa:.0f}s "
                  f"({n + 1}/{tentativi - 1})")
            time.sleep(pausa)
            attesa = min(attesa * 2, 60)
            continue
        response.raise_for_status()
        return response
    response.raise_for_status()
    return response


def normalizza_testo(value):
    """Normalizza accenti e segni di punteggiatura per confrontare nomi geografici."""
    if not isinstance(value, str):
        return ""
    value = value.replace("'", " ").replace("’", " ").replace("-", " ")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    # Rimuove anche gli spazi: GADM scrive alcuni nomi senza (es. "Valled'Aosta").
    return "".join(value.lower().split())


def carica_input(file_path):
    """Carica Excel o CSV, segnalando chiaramente se il file non è leggibile."""
    base_dir = Path(__file__).resolve().parent
    candidati = [file_path, "Confronto Bartolucci-COrALp DB.xlsx",
                 "Confronto Bartolucci-COrALp DB.xls", "specie.csv"]
    file_effettivo = None
    for candidato in candidati:
        if candidato:
            path = Path(candidato)
            if not path.is_absolute():
                path = base_dir / path
            if path.is_file():
                file_effettivo = path
                break

    if file_effettivo is None:
        simili = [p for p in base_dir.iterdir() if p.is_file()
                  and ("bartolucci" in p.name.lower() or "coral" in p.name.lower())
                  and p.suffix.lower() in {".xlsx", ".xls", ".csv"}]
        if simili:
            file_effettivo = simili[0]
        else:
            disponibili = [p.name for p in base_dir.iterdir() if p.is_file()
                           and p.suffix.lower() in {".xlsx", ".xls", ".csv"}]
            raise FileNotFoundError(
                f"File di input non trovato nella cartella {base_dir}. "
                f"File Excel/CSV disponibili: {disponibili}"
            )

    print(f"\nCaricamento file: {file_effettivo.name}")
    if file_effettivo.suffix.lower() in {".xlsx", ".xls"}:
        xls = pd.ExcelFile(file_effettivo)
        print(f"Fogli Excel: {xls.sheet_names}")
        for foglio in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=foglio)
            colonne = [str(c).strip().lower() for c in df.columns]
            if "parsed_name" in colonne or any("specie" in c for c in colonne):
                df.columns = [str(c).strip() for c in df.columns]
                print(f"Foglio utilizzato: {foglio}")
                return df
        raise ValueError("Nessun foglio contiene 'parsed_name' o una colonna con 'specie'.")

    errori = []
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        for separatore in (";", ",", "\t"):
            try:
                df = pd.read_csv(file_effettivo, encoding=encoding, sep=separatore)
                if len(df.columns) > 1:
                    df.columns = [str(c).strip() for c in df.columns]
                    print(f"CSV letto: codifica={encoding}, separatore={separatore!r}")
                    return df
            except Exception as exc:
                errori.append(str(exc))
    raise ValueError(f"Impossibile leggere il CSV {file_effettivo}. Errori: {errori[-3:]}")


def carica_gadm_geojson(iso, livello):
    """Scarica e legge il GeoJSON GADM per un paese e un livello amministrativo."""
    url = GADM_URL.format(iso=iso, lvl=livello)
    print(f"Scarico confini GADM 4.1: {iso}, livello {livello}...")
    response = SESSION.get(url, timeout=120)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archivio:
        nomi_json = [n for n in archivio.namelist() if n.lower().endswith(".json")]
        if not nomi_json:
            raise ValueError(f"Nessun GeoJSON trovato nell'archivio {url}")
        dati = json.loads(archivio.read(nomi_json[0]).decode("utf-8"))
    return dati


def risolvi_codici_gid():
    """Ricava e valida i GID GADM cercando SEMPRE per nome (nessun GID scritto a mano)."""
    cache = {}
    gids = {}
    errori = []

    for area, (iso, livello, nome_gadm) in AREE_ALCOTRA.items():
        try:
            chiave = (iso, livello)
            if chiave not in cache:
                cache[chiave] = carica_gadm_geojson(iso, livello)

            features = cache[chiave].get("features", [])
            nome_campo = f"NAME_{livello}"
            gid_campo = f"GID_{livello}"

            nome_atteso = normalizza_testo(nome_gadm)
            corrispondenze = [
                feature.get("properties", {})
                for feature in features
                if normalizza_testo(feature.get("properties", {}).get(nome_campo, "")) == nome_atteso
            ]

            if len(corrispondenze) != 1:
                nomi_disponibili = sorted({
                    str(feature.get("properties", {}).get(nome_campo, ""))
                    for feature in features
                })
                raise ValueError(
                    f"Attesa una sola corrispondenza per {nome_gadm!r}, "
                    f"trovate {len(corrispondenze)}. "
                    f"Nomi presenti nel GeoJSON: {nomi_disponibili}"
                )

            gid = corrispondenze[0].get(gid_campo)
            nome_effettivo = corrispondenze[0].get(nome_campo, "")

            if not gid:
                raise ValueError(f"Valore GID non valido per {area}")

            # Controllo di sicurezza: il nome trovato deve coincidere con quello atteso.
            if normalizza_testo(nome_effettivo) != nome_atteso:
                raise ValueError(
                    f"Nome GADM {nome_effettivo!r} diverso da quello atteso {nome_gadm!r}"
                )

            # Verifica che GBIF riconosca il GID prima dei conteggi.
            verifica = SESSION.get(f"{GBIF_API}/geocode/gadm/{gid}", timeout=30)
            verifica.raise_for_status()
            dettagli = verifica.json()
            if not dettagli:
                raise ValueError(f"GBIF ha restituito una risposta vuota per {gid}")
            gid_restituito = dettagli.get("gid")
            if gid_restituito is not None and gid_restituito != gid:
                raise ValueError(
                    f"GBIF ha restituito il GID {gid_restituito!r} invece di {gid!r}"
                )

            gids[area] = gid
            print(
                f"  {area:27s} -> {gid} (verificato; "
                f"nome GADM: {nome_effettivo})"
            )

        except Exception as exc:
            errori.append(f"{area}: {exc}")

    if errori:
        raise RuntimeError(
            "Impossibile validare tutte le aree. Analisi interrotta per evitare "
            "conteggi territoriali errati:\n- " + "\n- ".join(errori)
        )
    return gids


def match_specie_gbif(nome_botanico):
    """Accetta solo un match esatto; niente fuzzy matching."""
    try:
        response = get_con_retry(
            f"{GBIF_API}/species/match",
            params={"name": nome_botanico, "kingdom": "Plantae", "strict": "true"},
            timeout=30,
        )
        data = response.json()
        usage_key = data.get("usageKey")
        match_type = data.get("matchType", "")
        rank = data.get("rank", "")
        status = data.get("status", "")

        # In caso di nessun match, match approssimativo o rango superiore, non conteggiare.
        if not usage_key or match_type != "EXACT":
            return None, data.get("scientificName"), "NOT FOUND", status, rank
        if rank not in {"SPECIES", "SUBSPECIES", "VARIETY", "FORM", "SUBVARIETY", "SUBFORM"}:
            return None, data.get("scientificName"), "NOT FOUND", status, rank
        return usage_key, data.get("scientificName"), "EXACT", status, rank
    except requests.RequestException as exc:
        return None, None, f"API_ERROR: {exc}", "", ""
    except (ValueError, json.JSONDecodeError) as exc:
        return None, None, f"API_ERROR: risposta non valida ({exc})", "", ""


def conta_occurrences_area(taxon_key, gadm_gid):
    """Restituisce il conteggio GBIF; gli errori vengono propagati, mai convertiti in zero."""
    response = get_con_retry(
        f"{GBIF_API}/occurrence/search",
        params={
            "taxonKey": taxon_key,
            "gadmGid": gadm_gid,
            "hasCoordinate": "true",
            "hasGeospatialIssue": "false",
            "limit": 0,
        },
        timeout=60,
    )
    data = response.json()
    if "count" not in data:
        raise ValueError(f"La risposta GBIF non contiene 'count': {data}")
    return int(data["count"])


def salva_risultati(righe, output_path):
    pd.DataFrame(righe).to_csv(output_path, index=False, encoding="utf-8-sig", sep=";")


def analizza_checklist(input_file="Confronto Bartolucci-COrALp DB.xlsx",
                       output_file="risultati_gbif_alcotra.csv"):
    base_dir = Path(__file__).resolve().parent
    output_path = base_dir / output_file
    gids = risolvi_codici_gid()
    df_input = carica_input(input_file)

    colonne = {str(col).strip().lower(): col for col in df_input.columns}
    if "parsed_name" in colonne:
        col_nome = colonne["parsed_name"]
    else:
        candidate = [col for col in df_input.columns if "specie" in str(col).lower()]
        if len(candidate) == 1:
            col_nome = candidate[0]
        else:
            raise ValueError(
                "Colonna di ricerca non identificabile in modo univoco. "
                "Rinomina la colonna dei nomi scientifici in 'parsed_name'."
            )

    risultati = []
    totale = len(df_input)
    print(f"\nAvvio analisi di {totale} righe. Output: {output_path.name}\n")

    for indice, riga in df_input.iterrows():
        dati = riga.to_dict()
        nome = str(riga[col_nome]).strip() if pd.notna(riga[col_nome]) else ""
        # Lascia i conteggi vuoti finché le query non vengono completate.
        # In questo modo un nome vuoto o un errore non viene confuso con zero.
        dati.update({f"gbif_occurrences_{area}": "" for area in gids})
        # Una colonna TRUE/FALSE per area; resta vuota se la query non è stata eseguita.
        dati.update({f"presente_{area}": "" for area in gids})

        if not nome:
            dati.update({
                "gbif_taxon_key": "", "gbif_nome_matched": "", "gbif_match_type": "EMPTY_NAME",
                "gbif_status": "", "gbif_rank": "", "totale_occorrenze_alcotra": "",
                "presente_alcotra": "EMPTY_NAME", "gbif_query_status": "EMPTY_NAME"
            })
            risultati.append(dati)
            continue

        key, nome_matched, match_type, status, rank = match_specie_gbif(nome)
        dati.update({
            "gbif_taxon_key": key or "",
            "gbif_nome_matched": nome_matched or "",
            "gbif_match_type": match_type,
            "gbif_status": status or "",
            "gbif_rank": rank or "",
        })

        if match_type == "NOT FOUND":
            # Nessun match esatto: niente fuzzy matching e nessuna query delle occorrenze.
            dati.update({"totale_occorrenze_alcotra": "", "presente_alcotra": "NOT FOUND",
                         "gbif_query_status": "NOT FOUND"})
        elif str(match_type).startswith("API_ERROR"):
            # Errore API distinto da una specie non trovata.
            dati.update({"totale_occorrenze_alcotra": "", "presente_alcotra": "ERROR",
                         "gbif_query_status": match_type})
        else:
            errori_aree = []
            totale_occorrenze = 0
            for area, gid in gids.items():
                try:
                    conteggio = conta_occurrences_area(key, gid)
                    dati[f"gbif_occurrences_{area}"] = conteggio
                    dati[f"presente_{area}"] = "TRUE" if conteggio > 0 else "FALSE"
                    totale_occorrenze += conteggio
                except Exception as exc:
                    errori_aree.append(f"{area}: {exc}")
                    dati[f"gbif_occurrences_{area}"] = "ERROR"
                    dati[f"presente_{area}"] = "ERROR"
                time.sleep(PAUSA_TRA_QUERY)

            if errori_aree:
                dati["totale_occorrenze_alcotra"] = ""
                dati["presente_alcotra"] = "ERROR"
                dati["gbif_query_status"] = "ERROR: " + " | ".join(errori_aree)
            else:
                dati["totale_occorrenze_alcotra"] = totale_occorrenze
                dati["presente_alcotra"] = "SI" if totale_occorrenze > 0 else "NO"
                dati["gbif_query_status"] = "OK"

        risultati.append(dati)
        print(f"[{indice + 1}/{totale}] {nome[:42]:42s} -> {dati['presente_alcotra']}")
        if dati["presente_alcotra"] == "ERROR":
            # Mostra subito il motivo dell'errore invece di scoprirlo solo nel CSV.
            print(f"      motivo: {dati['gbif_query_status'][:200]}")

        # Salvataggio progressivo per non perdere il lavoro in caso di interruzione.
        if len(risultati) % 20 == 0:
            salva_risultati(risultati, output_path)

    salva_risultati(risultati, output_path)
    print("\nAnalisi terminata.")
    print(f"Risultati salvati in: {output_path}")


if __name__ == "__main__":
    analizza_checklist()
