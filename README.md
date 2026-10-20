# 🌿 Database & Pipeline Computazionale COrALp

Benvenuto nella repository ufficiale della pipeline computazionale sviluppata per il progetto **Interreg COrALp**.

Questa suite di script (in **R** e **Python**) consente di automatizzare l'intero ciclo di vita dei dati floristici per la regione delle Alpi Latine:
1. **Riconciliazione tassonomica** e risoluzione delle sinonimie botaniche.
2. **Estrazione delle occorrenze geografiche** georeferenziate dai territori ALCOTRA.
3. **Data mining dello status di conservazione** e dei tratti ecologici (IUCN / Species+).
4. **Normalizzazione e scomposizione (1NF)** per l'integrazione in database relazionali SQL.

---

## 📋 Indice
1. [Prerequisiti & Guida ai Token API](#-prerequisiti--guida-ai-token-api)
2. [Installazione e Configurazione](#-installazione-e-configurazione)
3. [Struttura dei File nel Repository](#-struttura-dei-file-nel-repository)
4. [Guida Dettagliata agli Script](#-guida-dettagliata-agli-script)
   - [1. Riconciliazione Tassonomica (`taxonomic_reconciliation.R`)](#1-taxonomic_reconciliationr)
   - [2. Occorrenze GBIF (`gbif_alcotra_occurrences.py`)](#2-gbif_alcotra_occurrencespy)
   - [3. Arricchimento Conservazionistico (`conservation_enrichment_complete.py`)](#3-conservation_enrichment_completepy)
   - [4. Normalizzazione Relazionale 1NF (`matrix_normalization_explode.py`)](#4-matrix_normalization_explodepy)
5. [Note sulla Sicurezza e `.gitignore`](#-note-sulla-sicurezza-e-gitignore)

---

## 🔑 Prerequisiti & Guida ai Token API

Per far funzionare gli script di data mining è necessario richiedere due **Token API**. Un Token è una chiave alfanumerica personale (simile a una password) che consente agli script di identificarsi e fare query ai server ufficiali di IUCN e Species+.

### 1. IUCN Red List API Token (`IUCN_TOKEN`)
* **A cosa serve:** Permette di interrogare l'API v4 della IUCN Red List per estrarre le categorie di rischio (Globale, Europeo, Mediterraneo), gli habitat, le minacce, i fattori di stress e le forme di crescita.
* **Come ottenerlo:**
  1. Registrati o accedi al sito [IUCN Red List API Account Request](https://api.iucnredlist.org/).
  2. Compila il modulo di richiesta specificando l'uso della ricerca (es. "Research project COrALp").
  3. Una volta approvata la richiesta, riceverai un token (stringa alfanumerica).

### 2. Species+ / UNEP-WCMC API Token (`SPECIES_TOKEN`)
* **A cosa serve:** Consente di accedere all'API v1 di Species+ per recuperare gli allegati delle Direttive UE (es. Direttiva Habitat 92/43/CEE) e le Appendici CITES (I, II, III).
* **Come ottenerlo:**
  1. Registrati sulla piattaforma [Species+ API Developer Portal](https://api.speciesplus.net/).
  2. Crea un account sviluppatore gratuito.
  3. Copia il tuo **API Token** personale mostrato nella dashboard del profilo.

---

## 🛠️ Installazione e Configurazione

### A. Configurazione dell'ambiente Python
Richiesto: **Python 3.10+**

1. **Clona la repository o scarica i file:**
   ```bash
   git clone https://github.com/tuo-username/nome-repository.git
   cd nome-repository
   ```

2. **Crea ed attiva un ambiente virtuale (consigliato):**
   * **Linux / macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   * **Windows (PowerShell):**
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```

3. **Installa le librerie richieste:**
   ```bash
   pip install pandas requests openpyxl python-dotenv
   ```

4. **Crea il file `.env` per le credenziali:**
   Crea un file di testo chiamato esattamente `.env` nella directory principale del progetto e inserisci i tuoi token come segue:
   ```env
   IUCN_TOKEN="inserisci_qui_il_tuo_token_iucn"
   SPECIES_TOKEN="inserisci_qui_il_tuo_token_species_plus"
   ```

### B. Configurazione dell'ambiente R
Richiesto: **R (v4.0+)** e **RStudio** (opzionale).

Apri la console R ed esegui il seguente comando per installare le dipendenze:

```R
install.packages(c("dplyr", "stringr", "tibble", "readxl", "openxlsx", "readr", "remotes"))
remotes::install_github("matildabrown/rWCVP")
install.packages("WorldFlora")
```

---

## 📁 Struttura dei File nel Repository

```text
├── .env                                # File riservato per i Token API (da creare)
├── .gitignore                          # Esclusione file temporanei e sensibili
├── taxonomic_reconciliation.R          # Script 1 (R): Riconciliazione tassonomica
├── gbif_alcotra_occurrences.py         # Script 2 (Python): Query occorrenze GBIF
├── conservation_enrichment_complete.py # Script 3 (Python): Data mining IUCN/Species+
├── matrix_normalization_explode.py     # Script 4 (Python): Normalizzazione 1NF
└── README.md                           # Documentazione della repository
```

---

## 🔍 Guida Dettagliata agli Script

---

### 1. `taxonomic_reconciliation.R`
Svolge l'allineamento tassonomico standardizzato della checklist floristica grezza, interrogando sia i backbone locali di **WCVP (World Checklist of Vascular Plants)** che quelli di **WFO (World Flora Online)**, con integrazione automatica dei Link **IPNI**.

* **Cosa serve prima di lanciarlo:**
  * Il file Excel di input (es. `NEW_WCVP_taxonomic_enrichment.xlsx`) contenente la colonna `parsed_name`.
  * I file CSV dei backbone scaricabili dai rispettivi portali: `wcvp_backbone_csv.csv` (separatore `|`) e `wfo_backbone_csv.csv` (separatore `Tab`).
* **Cosa eventualmente modificare nello script:**
  All'inizio dello script, modifica la sezione `SETTAGGI UTENTE` per adattarla alla tua struttura cartelle:
  ```R
  input_file <- "C:/percorso/tuo/file_input.xlsx"
  sheet_name <- "Nome_Foglio"
  wcvp_backbone_csv <- "wcvp_backbone_csv.csv"
  wfo_backbone_csv  <- "wfo_backbone_csv.csv"
  output_file <- "Enriched_FINAL_taxonomic_reconciliation2.0.xlsx"
  ```
* **Come eseguirlo:**
  ```bash
  Rscript taxonomic_reconciliation.R
  ```
* **Output:** Genera un file Excel (`Enriched_FINAL_taxonomic_reconciliation2.0.xlsx`) diviso nei fogli:
  1. `Unique_Taxa`: Tassonomia consolidata per le specie uniche (priorità WCVP > WFO).
  2. `Source_Summary`: Mappatura relazionale degli ID.
  3. `FULL_Enriched`: Dataset originale con l'arricchimento tassonomico completo.

---

### 2. `gbif_alcotra_occurrences.py`
Calcola in modo automatico e rigoroso il numero di occorrenze botaniche georeferenziate su **GBIF** all'interno delle province e dei dipartimenti dell'area transfrontaliera **ALCOTRA** (Italia/Francia).

* **Territori analizzati:** Torino, Cuneo, Imperia, Valle d'Aosta, Haute-Savoie, Savoie, Hautes-Alpes, Alpes-de-Haute-Provence, Alpes-Maritimes.
* **Caratteristiche tecniche:**
  * Utilizza confini amministrativi ufficiali **GADM 4.1**.
  * Accetta solo match tassonomici esatti (`matchType = EXACT`) per evitare falsi positivi da fuzzy matching.
  * Integra gestione dei *rate limit* (retry automatico in caso di errori 429/50x).
* **Cosa eventualmente modificare:**
  Nella funzione `analizza_checklist()` a fondo pagina, puoi cambiare il file Excel/CSV di input e il nome del file di output:
  ```python
  analizza_checklist(
      input_file="Confronto Bartolucci-COrALp DB.xlsx",
      output_file="risultati_gbif_alcotra.csv"
  )
  ```
* **Come eseguirlo:**
  ```bash
  python gbif_alcotra_occurrences.py
  ```
* **Output:** Un CSV (`risultati_gbif_alcotra.csv`) con il conteggio di osservazioni e flag di presenza (`TRUE`/`FALSE`) per ciascuna area ALCOTRA.

---

### 3. `conservation_enrichment_complete.py`
È il motore principale di data mining per l'arricchimento ecologico-conservazionistico delle specie. Interroga le API ufficiali IUCN e Species+.

* **Parametri estratti:**
  * **IUCN Red List:** Status Global (Scope 1), Europe (Scope 2), Mediterranean (Scope 4), Growth Forms, Threats, Use and Trade, Habitats (Scheme v3.1), Stresses.
  * **Species+:** Appendici CITES e Direttiva Habitat UE.
* **Architettura Fault-Tolerant:**
  * **Cache SQLite:** Crea in automatico il database locale `specie_conservazione_completa.db` dove salva ogni specie appena viene processata. Se l'esecuzione viene interrotta (es. caduta di connessione o `CTRL+C`), ripartirà dall'ultimo taxon rimasto in stato `DA_ELABORARE`.
  * **File di Log:** Registra il dettaglio delle operazioni in `enrichment_completo.log`.
* **Cosa eventualmente modificare:**
  Nella sezione `CONFIGURAZIONE FILE E PATH`:
  ```python
  FILE_EXCEL  = os.path.join(BASE_DIR, "NEW_db.xlsx")  # File Excel di origine
  NOME_FOGLIO = "clean_results"                        # Foglio da leggere
  FILE_OUTPUT = os.path.join(BASE_DIR, "WCVP_conservation_enriched_complete.xlsx")
  ```
* **Come eseguirlo:**
  ```bash
  python conservation_enrichment_complete.py
  ```
* **Output:** File Excel finale arricchito (`WCVP_conservation_enriched_complete.xlsx`).

---

### 4. `matrix_normalization_explode.py`
Risolve il problema delle variabili multivalore concatenate estratte dalle API (es. habitat o minacce separate da `|` o formattate come JSON). Trasforma il dataset in struttura atomica **Prima Forma Normale (1NF)** pronta per DBMS relazionali o SQLite.

* **Funzionalità:**
  * Esplode (*explode*) le liste molti-a-molti (N:N).
  * Pulisce i residui di sintassi JSON/Dizionari (es. `{'en': '...`).
  * Rimuove i duplicati e i valori vuoti di sistema.
* **Cosa eventualmente modificare:**
  Nella sezione `CONFIGURAZIONE`:
  ```python
  FILE_INPUT  = os.path.join(BASE_DIR, "NEW_db.xlsx")  # Input con i dati grezzi
  NOME_FOGLIO = "clean_results"
  FILE_OUTPUT = os.path.join(BASE_DIR, "Database_Normalizzato_Fogli_Separati.xlsx")
  ```
* **Come eseguirlo:**
  ```bash
  python matrix_normalization_explode.py
  ```
* **Output:** File Excel (`Database_Normalizzato_Fogli_Separati.xlsx`) contenente 8 fogli distinti per entità:
  `Status_IUCN_Global`, `Status_IUCN_Europe`, `Status_IUCN_Mediterranean`, `Growth_Forms`, `Threats`, `Uses_and_Trade`, `Habitats`, `Stresses`.

---

## 🔒 Note sulla Sicurezza e `.gitignore`

Per evitare di caricare accidentalmente dati personali, Token riservati o file pesanti su GitHub, assicuratevi che nella radice del progetto sia presente un file `.gitignore` con questo contenuto:

```gitignore
# Variabili d'ambiente e credenziali (MAI caricare i Token)
.env

# Database di cache locale e log
*.db
*.log

# File di dati pesanti / Excel di output
*.xlsx
*.xls
*.csv
wcvp_backbone_csv.csv
wfo_backbone_csv.csv

# Ambienti virtuali Python
venv/
.venv/
__pycache__/
```
