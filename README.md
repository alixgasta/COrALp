Database di COrALp

Repository ufficiale della pipeline computazionale per il progetto Interreg COrALp. Include gli script in R e Python per l’integrazione, la riconciliazione tassonomica e l’arricchimento ecologico-conservazionistico (IUCN/Species+) della flora delle Alpi Latine, con la struttura del database relazionale normalizzato (1NF).

📐 Architettura della Pipeline

La pipeline si articola in quattro fasi consecutive:

Riconciliazione Tassonomica (taxonomic_reconciliation.R): Allineamento dei nomi botanici grezzi e risoluzione delle sinonimie tramite i backbone di WCVP, WFO e IPNI.

Estrazione Occorrenze GBIF (gbif_alcotra_occurrences.py): Interrogazione geospaziale sulle aree amministrative ALCOTRA (GADM 4.1) per il conteggio e la presenza delle specie.

Arricchimento Ecologico e Conservazionista (conservation_enrichment_complete.py): Data mining dalle API IUCN Red List e Species+ (UNEP-WCMC) per attributi ecologici, status di rischio e tutela normativa.

Normalizzazione Relazionale 1NF (matrix_normalization_explode.py): Esplosione delle variabili multivalore in tabelle atomiche 1NF pronte per l'importazione in SGBD/SQLite.

🛠️ Moduli e Script

1. taxonomic_reconciliation.R

Script in R dedicato all'allineamento tassonomico standardizzato della checklist floristica del progetto.

Funzionalità:

Caricamento e parsing dei dati di input (parsed_name, wcvp_id, wfo_id).

Lookup esatto per ID ed esecuzione di matching sia esatto che fuzzy tramite rWCVP e WorldFlora.

Gestione specifica degli ibridi interspecifici (con e senza il prefisso ×).

Consolidamento gerarchico dei dati con priorità WCVP rispetto a WFO e recupero automatico del link IPNI (https://www.ipni.org/n/...).

Output: File Excel Enriched_FINAL_taxonomic_reconciliation2.0.xlsx con tre fogli (Unique_Taxa, Source_Summary, FULL_Enriched).

2. gbif_alcotra_occurrences.py

Modulo Python per l'estrazione controllata dei dati di occorrenza georeferenziata da GBIF limitatamente ai territori del programma ALCOTRA.

Funzionalità:

Match esatto del taxon via GBIF Species API (senza fuzzy matching per evitare falsi positivi).

Download automatico dei confini amministrativi GADM 4.1 per i dipartimenti francesi e le province italiane coinvolte.

Verifica e risoluzione dinamica dei codici GID per prevenire errori territoriali.

Interrogazione geospaziale GBIF Occurrence API con ripristino automatico in caso di rate limiting o disconnessione (retry logic / backoff).

Output: CSV risultati_gbif_alcotra.csv contenente i conteggi dettagliati e gli indicatori di presenza per singola area amministrativa.

3. conservation_enrichment_complete.py

Questo modulo costituisce il motore di data mining automatizzato in Python progettato per l'arricchimento del nucleo floristico normalizzato del progetto Interreg COrALp (composto da 5.451 entità tassonomiche uniche). Lo script interroga in parallelo e in modo deterministico le API internazionali di riferimento per estrarre metadati legati allo status di conservazione, alle minacce antropiche, ai tratti ecologici e ai vincoli legislativi transfrontalieri della flora alpina.

Fonti Interrogate e Tratti Estratti

IUCN Red List API (v4):

Categoria di rischio su tre scale geografiche (Globale, Europeo, Mediterraneo) per analisi geoecologiche comparative.

Classificazione degli habitat naturali (Habitats Classification Scheme v3.1).

Minacce attive (Threats) e fattori di stress biologico indotto (Stresses).

Forme di crescita macro-strutturali (Growth Forms) e profili di utilizzo etnobotanico (Use and Trade).

Species+ API (v1) / UNEP-WCMC:

Grado di tutela cogente internazionale (Appendici CITES I, II, III).

Vincoli normativi di conservazione a scala comunitaria (Allegati della Direttiva Habitat 92/43/CEE).

Architettura e Tolleranza ai Guasti (Fault Tolerance)

Data la natura massiva dell'estrazione (oltre 8 ore di elaborazione remota) e i rigidi limiti di frequenza (Rate-Limiting) imposti dagli endpoint ufficiali, lo script integra un'architettura robusta per la persistenza dello stato:

Cache di Stato Locale (SQLite): Un database locale (specie_conservazione_completa.db) tiene traccia dei progressi riga per riga tramite gli stati DA_ELABORARE e COMPLETATO. In caso di interruzione della rete o crash del sistema, lo script riprende l'elaborazione esattamente dall'ultimo record valido, fungendo da checkpoint di ripristino.

Retry Logic ed Exponential Backoff: Gestione automatica degli errori HTTP 429 (Too Many Requests) e dei timeout di rete mediante cicli di attesa progressivi.

Logging di Sistema: Tracciamento asincrono dettagliato delle metriche e delle risposte API nel file enrichment_completo.log.

4. matrix_normalization_explode.py

Questo script automatizza la scomposizione e la normalizzazione delle variabili multivalore generate dalle pipeline di data mining (API IUCN). Nel database floristico originario, attributi ecologici complessi come minacce (Threats), habitat (Habitats), forme di crescita (Growth Forms) e fattori di stress (Stresses) sono memorizzati come stringhe concatenate e nidificate in formato pseudo-JSON, separate dal delimitatore verticale |.

Al fine di convertire queste relazioni molti-a-molti (N:N) in strutture atomiche compatibili con i principi della Prima Forma Normale (1NF) e con l'architettura del database relazionale SQLite del progetto COrALp, lo script esegue una procedura di splitting testuale e un'operazione di explode mediante la libreria pandas.

Funzionalità Principali

Caricamento Dinamico: Lettura controllata del foglio clean_results dal database centralizzato.

Esplosione delle Relazioni N:N: Scomposizione delle stringhe multivalore e generazione di righe indipendenti per ciascun attributo ecologico associato al taxon.

Pulizia Sintattica: Rimozione deterministica tramite espressioni regolari (Regex) dei marcatori residuali dei dizionari e delle stringhe JSON (es. {'en': '...).

Filtro del Rumore: Eliminazione automatica di valori nulli di sistema (NaN, None, null, stringhe vuote).

Deduplicazione Globale: Rimozione delle ridondanze nominali per garantire l'atomicità e l'integrità referenziale delle matrici risultanti.

Output Generato

Lo script produce un file Excel denominato Database_Normalizzato_Fogli_Separati.xlsx articolato in 8 fogli relazionali独立 e pronti per l'importazione nel DBMS:

Status_IUCN_Global

Status_IUCN_Europe

Status_IUCN_Mediterranean

Growth_Forms

Threats

Uses_and_Trade

Habitats

Stresses

⚙️ Configurazione e Installazione

Requisiti Ambiente Python

Crea un ambiente virtuale e installa le dipendenze:

python -m venv venv
source venv/bin/activate  # In Windows: venv\Scripts\activate
pip install -r requirements.txt


Esempio di requirements.txt:

pandas
requests
openpyxl
python-dotenv


Requisiti Ambiente R

Esegui all'interno della console R:

install.packages(c("dplyr", "stringr", "tibble", "readxl", "openxlsx", "readr", "remotes"))
remotes::install_github("matildabrown/rWCVP")
install.packages("WorldFlora")


Variabili d'Ambiente (.env)

Crea un file .env nella radice del progetto per memorizzare le credenziali API richieste dallo script conservation_enrichment_complete.py:

IUCN_TOKEN="il_tuo_token_iucn"
SPECIES_TOKEN="il_tuo_token_species_plus"


📂 Struttura Raccomandata del File .gitignore

Per evitare il caricamento accidentale di dati pesanti, file temporanei o chiavi private sul repository:

# Variabili d'ambiente e credenziali
.env

# Database locali e file di cache
*.db
*.log

# File di dati di input/output e backbone locali
*.xlsx
*.xls
*.csv
wcvp_backbone_csv.csv
wfo_backbone_csv.csv

# Ambienti virtuali Python
venv/
.venv/
__pycache__/
