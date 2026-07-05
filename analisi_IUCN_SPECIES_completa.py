"""
conservation_enrichment_complete.py
===================================
Script unificato e definitivo per l'arricchimento del database tassonomico WCVP.

Estrae da IUCN Red List API v4:
  - Status IUCN Global (Scope 1)
  - Status IUCN Europe (Scope 2)
  - Status IUCN Mediterranean (Scope 4)
  - Forme di Crescita (Growth Forms)
  - Minacce (Threats)
  - Usi e Commercio (Use and Trade)
  - Habitat (Habitats Classification Scheme v3.1)
  - Fattori di Stress (Stresses)

Estrae da Species+ API v1:
  - Appendici CITES (I, II, III)
  - Direttive UE (Habitats Directive Annex, ecc.)
"""

import os
import sqlite3
import time
import logging
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Carica le variabili dal file .env nella stessa cartella dello script
load_dotenv()

# ─────────────────────────────────────────────
#  CONFIGURAZIONE FILE E PATH
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configura i tuoi file di input e output qui
FILE_EXCEL     = os.path.join(BASE_DIR, "NEW_db.xlsx")
NOME_FOGLIO    = "clean_results"
FILE_OUTPUT    = os.path.join(BASE_DIR, "WCVP_conservation_enriched_complete.xlsx")

# Database dedicato per questa estrazione completa
DATABASE       = os.path.join(BASE_DIR, "specie_conservazione_completa.db")
FILE_LOG       = os.path.join(BASE_DIR, "enrichment_completo.log")

IUCN_TOKEN     = os.getenv("IUCN_TOKEN")
SPECIES_TOKEN  = os.getenv("SPECIES_TOKEN")

if not IUCN_TOKEN or not SPECIES_TOKEN:
    raise SystemExit("ERRORE: token mancanti nel file .env. Controlla IUCN_TOKEN e SPECIES_TOKEN.")

# Impostazioni di timeout e attesa per rispettare i Rate-Limit
SLEEP_IUCN     = 1.5   
SLEEP_SPECIES  = 1.0   
MAX_RETRY      = 3
RETRY_WAIT     = 10    

# ─────────────────────────────────────────────
#  LOGGING SYSTEM
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(FILE_LOG, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  FUNZIONI DI RETRY E CHIAMATA HTTP
# ─────────────────────────────────────────────
def get_with_retry(url: str, headers: dict = None, params: dict = None) -> dict | None:
    """Effettua una chiamata GET con gestione automatica di rate limiting (429) e timeout."""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                log.warning(f"  Rate limit (429) rilevato. Attendo {RETRY_WAIT}s... (tentativo {attempt}/{MAX_RETRY})")
                time.sleep(RETRY_WAIT)
            elif resp.status_code == 404:
                return None   
            else:
                log.warning(f"  HTTP {resp.status_code} per l'URL: {url}")
                return None
        except requests.exceptions.Timeout:
            log.warning(f"  Timeout riscontrato. Tentativo {attempt}/{MAX_RETRY}")
            time.sleep(5)
        except requests.exceptions.RequestException as e:
            log.error(f"  Errore di connessione/rete: {e}")
            return None
    return None

# ─────────────────────────────────────────────
#  FUNZIONI DI SUPPORTO PER ESTRAZIONE DATI
# ─────────────────────────────────────────────
def extract_cat_fallback(obj) -> str | None:
    """Scansiona ricorsivamente l'oggetto JSON alla ricerca di codici di categoria Red List."""
    if isinstance(obj, dict):
        if obj.get("red_list_category_code"):
            return obj["red_list_category_code"]
        for key in ["red_list_category", "category"]:
            if key in obj:
                cat = obj[key]
                if isinstance(cat, dict) and cat.get("code"):
                    return cat.get("code")
                elif isinstance(cat, str):
                    return cat
        for v in obj.values():
            res = extract_cat_fallback(v)
            if res: return res
    elif isinstance(obj, list):
        for item in obj:
            res = extract_cat_fallback(item)
            if res: return res
    return None

def get_assessment_for_scope(assessments: list, target_scope: str) -> dict | None:
    """Trova la valutazione più idonea (preferendo la più recente) per uno specifico scope geographically."""
    if not assessments:
        return None
    
    matched = []
    for a in assessments:
        if not isinstance(a, dict):
            continue
        
        is_match = False
        # Metodo 1: Verifica diretta di scope_code
        scope_code = a.get("scope_code")
        if scope_code is not None and str(scope_code) == str(target_scope):
            is_match = True
            
        # Metodo 2: Ispezione della lista annidata 'scopes'
        if not is_match and isinstance(a.get("scopes"), list):
            for s in a["scopes"]:
                if isinstance(s, dict):
                    code_val = s.get("code") or s.get("scope_code")
                    if code_val is not None and str(code_val) == str(target_scope):
                        is_match = True
                        break
                elif isinstance(s, (str, int)) and str(s) == str(target_scope):
                    is_match = True
                    break
                    
        if is_match:
            matched.append(a)
            
    if not matched:
        return None
        
    # Favorisce la valutazione contrassegnata come 'latest'
    latest_item = next((a for a in matched if a.get("latest") is True or str(a.get("latest")).lower() == 'true'), None)
    if latest_item:
        return latest_item
        
    return matched[0]

def extract_category_code(assessment: dict | None) -> str | None:
    """Estrae in modo sicuro il codice della categoria (es: EN, LC, CR) da un blocco assessment."""
    if not assessment:
        return None
    if assessment.get("red_list_category_code"):
        return assessment["red_list_category_code"]
    
    cat = assessment.get("red_list_category") or assessment.get("category")
    if isinstance(cat, dict):
        return cat.get("code") or cat.get("category_code")
    elif isinstance(cat, str):
        return cat
    return None

# ─────────────────────────────────────────────
#  QUERY PRINCIPALE IUCN
# ─────────────────────────────────────────────
def query_iucn_complete(nome: str) -> dict:
    """
    Effettua le chiamate all'API IUCN v4 per recuperare lo status per i vari ambiti (Global, Europe, Med)
    e interroga la singola valutazione per estrarre habitat, stressor, forme di crescita e minacce.
    """
    results = {
        "status_iucn_global": None,
        "status_iucn_europe": None,
        "status_iucn_mediterranean": None,
        "growth_forms": None,
        "threats": None,
        "uses_and_trade": None,
        "habitats": None,
        "stresses": None
    }
    
    headers = {"Authorization": f"Bearer {IUCN_TOKEN}"}
    
    parti = nome.split(" ", 1)
    genus_name = parti[0]
    species_name = parti[1] if len(parti) > 1 else ""

    # 1. Ricerca del taxon per nome scientifico latino binomiale
    url = "https://api.iucnredlist.org/api/v4/taxa/scientific_name"
    params = {"genus_name": genus_name, "species_name": species_name}
    data = get_with_retry(url, headers=headers, params=params)

    # Fallback con ricerca testuale generica
    if not data:
        url_fallback = "https://api.iucnredlist.org/api/v4/taxa/search"
        data = get_with_retry(url_fallback, headers=headers, params={"query": nome})

    if not data:
        # Se non trovato in nessuno dei due modi, compila con "Not Found"
        for k in ["status_iucn_global", "status_iucn_europe", "status_iucn_mediterranean"]:
            results[k] = "Not Found"
        return results

    # Estrazione della lista delle valutazioni
    assessments = data.get("assessments", [])
    
    # Adattamento per strutture di risposta alternative derivanti dalla ricerca fallback
    if not assessments:
        if isinstance(data, list) and len(data) > 0:
            assessments = data[0].get("assessments", [])
        elif isinstance(data, dict):
            sub_results = data.get("results", [])
            if sub_results and len(sub_results) > 0:
                assessments = sub_results[0].get("assessments", [])

    # Estrazione degli status differenziati per Scope
    global_ass = get_assessment_for_scope(assessments, "1")
    europe_ass = get_assessment_for_scope(assessments, "2")
    med_ass    = get_assessment_for_scope(assessments, "4")

    results["status_iucn_global"] = extract_category_code(global_ass)
    results["status_iucn_europe"] = extract_category_code(europe_ass)
    results["status_iucn_mediterranean"] = extract_category_code(med_ass)

    # Salvataggio di sicurezza se il global_ass specifico è vuoto ma è presente un codice nel payload
    if not results["status_iucn_global"]:
        fallback_cat = extract_cat_fallback(data)
        if fallback_cat:
            results["status_iucn_global"] = fallback_cat

    # Individuazione dell'assessment_id ottimale per interrogare i dettagli ecologici
    # (Preferiamo la valutazione Global, seguita da Europe, Med, o la prima disponibile)
    assessment_id = None
    if global_ass:
        assessment_id = global_ass.get("assessment_id") or global_ass.get("id")
    elif europe_ass:
        assessment_id = europe_ass.get("assessment_id") or europe_ass.get("id")
    elif med_ass:
        assessment_id = med_ass.get("assessment_id") or med_ass.get("id")
    elif assessments:
        assessment_id = assessments[0].get("assessment_id") or assessments[0].get("id")

    # Se abbiamo un ID valutazione valido, scarichiamo le informazioni di dettaglio
    if assessment_id:
        time.sleep(SLEEP_IUCN) 
        url_ass = f"https://api.iucnredlist.org/api/v4/assessment/{assessment_id}"
        ass_data = get_with_retry(url_ass, headers=headers)
        
        if ass_data:
            # Estrazione Forme di Crescita (Growth Forms)
            gf_list = ass_data.get("growth_forms", [])
            if gf_list:
                results["growth_forms"] = " | ".join([
                    str(g.get("name", g.get("title", g.get("description", "")))) 
                    for g in gf_list if g
                ])
            
            # Estrazione Minacce (Threats)
            threats_list = ass_data.get("threats", [])
            if threats_list:
                results["threats"] = " | ".join([
                    str(t.get("description", t.get("title", t.get("name", "")))) 
                    for t in threats_list if t
                ])
            
            # Estrazione Usi e Commercio (Use and Trade)
            uses_list = ass_data.get("use_and_trade", [])
            if uses_list:
                results["uses_and_trade"] = " | ".join([
                    str(u.get("description", u.get("title", u.get("name", "")))) 
                    for u in uses_list if u
                ])

            # Estrazione Habitat (Habitats Classification Scheme v3.1)
            habitats_list = ass_data.get("habitats", [])
            if habitats_list:
                results["habitats"] = " | ".join([
                    str(h.get("name", h.get("title", h.get("description", h.get("code", ""))))) 
                    for h in habitats_list if h
                ])

            # Estrazione Fattori di Stress (Stresses)
            stresses_list = ass_data.get("stresses", [])
            if stresses_list:
                results["stresses"] = " | ".join([
                    str(s.get("name", s.get("title", s.get("description", s.get("code", ""))))) 
                    for s in stresses_list if s
                ])

    return results

# ─────────────────────────────────────────────
#  QUERY SPECIES+ (CITES & UE DIRECTIVES)
# ─────────────────────────────────────────────
def query_species_plus(nome: str) -> tuple[str | None, str | None]:
    """Interroga l'API Species+ per ottenere le appendici CITES e le Direttive UE applicate."""
    headers = {"X-Authentication-Token": SPECIES_TOKEN}
    url = "https://api.speciesplus.net/api/v1/taxon_concepts"
    params = {"name": nome}

    data = get_with_retry(url, headers=headers, params=params)
    
    if not data or not data.get("taxon_concepts"):
        return "Not Found", "Not Found"

    # Ricerca di una corrispondenza esatta di nome (case-insensitive)
    taxon = next((tc for tc in data["taxon_concepts"] if tc.get("full_name", "").lower() == nome.lower()), None)
    
    if not taxon:
        return "Not Found", "Not Found"

    cites = taxon.get("cites_listing")
    eu = taxon.get("eu_listing")
    
    return (cites if cites else None), (eu if eu else None)

# ─────────────────────────────────────────────
#  1. CARICAMENTO DEL FILE EXCEL
# ─────────────────────────────────────────────
log.info("Caricamento del file Excel di origine...")
try:
    df_originale = pd.read_excel(FILE_EXCEL, sheet_name=NOME_FOGLIO)
    lista_specie = df_originale["parsed_name"].dropna().unique().tolist()
    log.info(f"Rilevate {len(lista_specie)} specie univoche da analizzare.")
except Exception as e:
    log.error(f"Impossibile leggere il file Excel: {e}")
    raise SystemExit(1)

# ─────────────────────────────────────────────
#  2. CONFIGURAZIONE DATABASE SQLITE (CACHE DI STATO)
# ─────────────────────────────────────────────
conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

# Creazione della tabella con la nuova struttura ad arricchimento completo
cursor.execute("""
    CREATE TABLE IF NOT EXISTS dati_conservazione (
        nome_scientifico           TEXT PRIMARY KEY,
        status_iucn_global         TEXT,
        status_iucn_europe         TEXT,
        status_iucn_mediterranean  TEXT,
        growth_forms               TEXT,
        threats                    TEXT,
        uses_and_trade             TEXT,
        habitats                   TEXT,
        stresses                   TEXT,
        cites_appendice            TEXT,
        direttiva_ue               TEXT,
        stato                      TEXT DEFAULT 'DA_ELABORARE'
    )
""")
conn.commit()

# Inserimento iniziale delle specie mancanti nel tracciamento locale
for specie in lista_specie:
    cursor.execute(
        "INSERT OR IGNORE INTO dati_conservazione (nome_scientifico) VALUES (?)",
        (specie,)
    )
conn.commit()

# Recupero delle specie ancora in stato DA_ELABORARE
cursor.execute("SELECT nome_scientifico FROM dati_conservazione WHERE stato = 'DA_ELABORARE'")
da_elaborare = [r[0] for r in cursor.fetchall()]
totale = len(da_elaborare)
log.info(f"Specie rimanenti da elaborare in questa sessione: {totale}")

# ─────────────────────────────────────────────
#  3. LOOP PRINCIPALE DI ELABORAZIONE
# ─────────────────────────────────────────────
try:
    for i, specie in enumerate(da_elaborare, 1):
        log.info(f"[{i}/{totale}] In elaborazione: {specie}")

        res_iucn = {
            "status_iucn_global": None, "status_iucn_europe": None, "status_iucn_mediterranean": None,
            "growth_forms": None, "threats": None, "uses_and_trade": None, "habitats": None, "stresses": None
        }
        
        # Chiamata a IUCN v4
        try:
            res_iucn = query_iucn_complete(specie)
            
            # Log visivo di anteprima nel terminale per monitorare i dati estratti
            prev_g = res_iucn["status_iucn_global"]
            prev_e = res_iucn["status_iucn_europe"]
            prev_m = res_iucn["status_iucn_mediterranean"]
            log.info(f"  IUCN Status: Global={prev_g} | Europe={prev_e} | Med={prev_m}")
            
            if res_iucn["habitats"]:
                prev_h = (res_iucn["habitats"][:40] + '...') if len(res_iucn["habitats"]) > 40 else res_iucn["habitats"]
                log.info(f"  Habitats estratti: {prev_h}")
            if res_iucn["stresses"]:
                prev_s = (res_iucn["stresses"][:40] + '...') if len(res_iucn["stresses"]) > 40 else res_iucn["stresses"]
                log.info(f"  Stresses estratti: {prev_s}")
                
        except Exception as e:
            log.error(f"  Eccezione non gestita durante la query IUCN per '{specie}': {e}")
        
        time.sleep(SLEEP_IUCN)

        # Chiamata a Species+
        cites_appendice = None
        direttiva_ue = None
        try:
            cites_appendice, direttiva_ue = query_species_plus(specie)
            log.info(f"  Species+: CITES={cites_appendice} | EU={direttiva_ue}")
        except Exception as e:
            log.error(f"  Eccezione non gestita durante la query Species+ per '{specie}': {e}")
            
        time.sleep(SLEEP_SPECIES)

        # Aggiornamento record sul database SQLite e marcatura come COMPLETATO
        cursor.execute("""
            UPDATE dati_conservazione
            SET status_iucn_global = ?,
                status_iucn_europe = ?,
                status_iucn_mediterranean = ?,
                growth_forms = ?,
                threats = ?,
                uses_and_trade = ?,
                habitats = ?,
                stresses = ?,
                cites_appendice = ?,
                direttiva_ue = ?,
                stato = 'COMPLETATO'
            WHERE nome_scientifico = ?
        """, (
            res_iucn["status_iucn_global"],
            res_iucn["status_iucn_europe"],
            res_iucn["status_iucn_mediterranean"],
            res_iucn["growth_forms"],
            res_iucn["threats"],
            res_iucn["uses_and_trade"],
            res_iucn["habitats"],
            res_iucn["stresses"],
            cites_appendice,
            direttiva_ue,
            specie
        ))
        conn.commit()

    log.info("Fase di scansione delle specie completata correttamente.")

except KeyboardInterrupt:
    log.warning("\nProcesso interrotto dall'utente. I dati raccolti finora sono salvati in cache. Esegui nuovamente lo script per riprendere.")

# ─────────────────────────────────────────────
#  4. EXPORT EXCEL FINALE (MERGE DEI DATI)
# ─────────────────────────────────────────────
log.info("Preparazione esportazione su file Excel finale...")

# Lettura di tutti i dati elaborati dal database SQLite
df_risultati = pd.read_sql("""
    SELECT nome_scientifico AS parsed_name,
           status_iucn_global,
           status_iucn_europe,
           status_iucn_mediterranean,
           growth_forms,
           threats,
           uses_and_trade,
           habitats,
           stresses,
           cites_appendice,
           direttiva_ue
    FROM dati_conservazione
""", conn)
conn.close()

# Rilevamento e rimozione preventiva di colonne omonime presenti nel file di input,
# per scongiurare la generazione di doppioni del tipo 'colonna_x' o 'colonna_y' nel merge finalizzato
colonne_arricchimento = [
    "status_iucn", "status_iucn_global", "status_iucn_europe", "status_iucn_mediterranean",
    "growth_forms", "threats", "uses_and_trade", "habitats", "stresses",
    "cites_appendice", "direttiva_ue"
]
colonne_da_rimuovere = [c for c in colonne_arricchimento if c in df_originale.columns]
if colonne_da_rimuovere:
    log.info(f"Pulizia colonne preesistenti nel file di origine per evitare collisioni: {colonne_da_rimuovere}")
    df_originale = df_originale.drop(columns=colonne_da_rimuovere)

# Esecuzione del merge a sinistra (left join) sul parsed_name
df_finale = df_originale.merge(df_risultati, on="parsed_name", how="left")

# Salvataggio del nuovo file Excel arricchito
df_finale.to_excel(FILE_OUTPUT, index=False, sheet_name="clean_results_enriched")
log.info(f"File salvato con successo: {FILE_OUTPUT}")

# Riassunto delle metriche estratte
log.info("--- STATISTICHE DI COMPLETAMENTO ESTRAZIONE ---")
log.info(f"Righe totali generate: {len(df_finale)}")
log.info(f"Specie con IUCN Global: {df_finale['status_iucn_global'].notna().sum()}")
log.info(f"Specie con IUCN Europe: {df_finale['status_iucn_europe'].notna().sum()}")
log.info(f"Specie con IUCN Mediterranean: {df_finale['status_iucn_mediterranean'].notna().sum()}")
log.info(f"Specie con Habitat compilati: {df_finale['habitats'].notna().sum()}")
log.info(f"Specie con Stresses compilati: {df_finale['stresses'].notna().sum()}")
log.info(f"Specie con CITES compilato: {df_finale['cites_appendice'].notna().sum()}")
log.info(f"Specie con Direttive UE compilate: {df_finale['direttiva_ue'].notna().sum()}")