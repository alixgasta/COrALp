# 🌿 COrALp: Database & Pipeline Computazionale
### di Alasia Maria Gastaudo

**Autore:** Alasia Maria Gastaudo 
**Progetto:** Interreg ALCOTRA COrALp, Università degli Studi di Torino, 2025/2026

Questa suite di script (in **R** e **Python**) automatizza l'intero ciclo di vita dei dati floristici per la regione delle Alpi Latine:

1. **Riconciliazione tassonomica** e risoluzione delle sinonimie botaniche.
2. **Estrazione delle occorrenze geografiche** georeferenziate dai territori ALCOTRA.
3. **Data mining dello status di conservazione** e dei tratti ecologici (IUCN / Species+).
4. **Normalizzazione e scomposizione (1NF)** per l'integrazione in database relazionali SQL.

---

## Indice

1. [Flusso di lavoro e ordine di esecuzione](#flusso-di-lavoro-e-ordine-di-esecuzione)
2. [Prerequisiti e guida ai token API](#prerequisiti-e-guida-ai-token-api)
3. [Installazione e configurazione](#installazione-e-configurazione)
4. [Struttura dei file nel repository](#struttura-dei-file-nel-repository)
5. [Guida dettagliata agli script](#guida-dettagliata-agli-script)
   - [1. Riconciliazione tassonomica (`taxonomic_reconciliation.R`)](#1-taxonomic_reconciliationr)
   - [2. Occorrenze GBIF (`gbif_alcotra_occurrences.py`)](#2-gbif_alcotra_occurrencespy)
   - [3. Arricchimento conservazionistico (`conservation_enrichment_complete.py`)](#3-conservation_enrichment_completepy)
   - [4. Normalizzazione relazionale 1NF (`matrix_normalization_explode.py`)](#4-matrix_normalization_explodepy)
6. [Note sulla sicurezza e `.gitignore`](#note-sulla-sicurezza-e-gitignore)
7. [Licenza](#licenza)
8. [Come citare](#come-citare)
9. [Autore e contatti](#autore-e-contatti)

---

## Flusso di lavoro e ordine di esecuzione

Gli script sono pensati per essere lanciati in sequenza, ma ciascuno può essere usato in modo indipendente se si dispone del relativo file di input.

```text
Checklist floristica grezza (.xlsx)
        │
        ▼
[1] taxonomic_reconciliation.R           → nomi accettati, sinonimi, ID WCVP / WFO / IPNI
        │
        ├──────────────► [2] gbif_alcotra_occurrences.py       → occorrenze GBIF per area ALCOTRA
        │
        ▼
[3] conservation_enrichment_complete.py  → status IUCN, CITES, Direttiva Habitat
        │
        ▼
[4] matrix_normalization_explode.py      → tabelle atomiche (1NF) per database SQL
```

**Input atteso:** un file Excel con una riga per taxon. Lo script 1 richiede una colonna `parsed_name` con il nome scientifico (binomio o trinomio, senza autore). Gli script successivi leggono il foglio indicato nella loro sezione di configurazione.

---

## Prerequisiti e guida ai token API

Per far funzionare gli script di data mining è necessario richiedere due **token API**. Un token è una chiave alfanumerica personale (simile a una password) che consente agli script di identificarsi e di interrogare i server ufficiali di IUCN e Species+.

### 1. IUCN Red List API Token (`IUCN_TOKEN`)

* **A cosa serve:** permette di interrogare l'API v4 della IUCN Red List per estrarre le categorie di rischio (Globale, Europeo, Mediterraneo), gli habitat, le minacce, i fattori di stress e le forme di crescita.
* **Come ottenerlo:**
  1. Registrati o accedi alla pagina [IUCN Red List API](https://api.iucnredlist.org/).
  2. Compila il modulo di richiesta indicando l'uso a fini di ricerca (es. "Research project COrALp").
  3. Una volta approvata la richiesta, riceverai un token (stringa alfanumerica).

### 2. Species+ / UNEP-WCMC API Token (`SPECIES_TOKEN`)

* **A cosa serve:** consente di accedere all'API v1 di Species+ per recuperare gli allegati delle direttive UE (es. Direttiva Habitat 92/43/CEE) e le Appendici CITES (I, II, III).
* **Come ottenerlo:**
  1. Registrati sul portale [Species+ API](https://api.speciesplus.net/).
  2. Crea un account sviluppatore gratuito.
  3. Copia il tuo **API Token** personale mostrato nella dashboard del profilo.

> I portali cambiano talvolta indirizzo: se un link non funziona, cerca "IUCN Red List API" o "Species+ API" sul sito ufficiale.

---

## Installazione e configurazione

### A. Ambiente Python

Richiesto: **Python 3.10+**

1. **Clona il repository o scarica i file:**
   ```bash
   git clone https://github.com/alixgasta/COrALp.git
   cd COrALp
   ```

2. **Crea e attiva un ambiente virtuale (consigliato):**
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
   crea un file di testo chiamato esattamente `.env` nella directory principale del progetto e inserisci i tuoi token:
   ```env
   IUCN_TOKEN="inserisci_qui_il_tuo_token_iucn"
   SPECIES_TOKEN="inserisci_qui_il_tuo_token_species_plus"
   ```

### B. Ambiente R

Richiesto: **R (v4.0+)** e **RStudio** (opzionale).

Apri la console R ed esegui:

```r
install.packages(c("dplyr", "stringr", "tibble", "readxl", "openxlsx", "readr", "remotes"))
remotes::install_github("matildabrown/rWCVP")
install.packages("WorldFlora")
```

---

## Struttura dei file nel repository

```text
├── taxonomic_reconciliation.R          # Script 1 (R): riconciliazione tassonomica
├── gbif_alcotra_occurrences.py         # Script 2 (Python): query occorrenze GBIF
├── conservation_enrichment_complete.py # Script 3 (Python): data mining IUCN / Species+
├── matrix_normalization_explode.py     # Script 4 (Python): normalizzazione 1NF
├── .gitignore                          # Esclusione di file temporanei e sensibili
├── LICENSE                             # Licenza del codice (MIT)
├── CITATION.cff                        # Metadati per la citazione
└── README.md                           # Documentazione del repository
```

File da creare **in locale** e **non** da versionare (esclusi da `.gitignore`):

```text
├── .env                                # Token API (locale, non versionato)
├── wcvp_backbone_csv.csv               # Backbone WCVP (da scaricare)
└── wfo_backbone_csv.csv                # Backbone WFO (da scaricare)
```

---

## Guida dettagliata agli script

---

### 1. `taxonomic_reconciliation.R`

Svolge l'allineamento tassonomico standardizzato della checklist floristica grezza, interrogando sia i backbone locali di **WCVP (World Checklist of Vascular Plants)** sia quelli di **WFO (World Flora Online)**, con integrazione automatica dei link **IPNI**.

* **Cosa serve prima di lanciarlo:**
  * Il file Excel di input (es. `NEW_WCVP_taxonomic_enrichment.xlsx`) contenente la colonna `parsed_name`.
  * I file CSV dei backbone, scaricabili dai rispettivi portali: `wcvp_backbone_csv.csv` (separatore `|`) e `wfo_backbone_csv.csv` (separatore `Tab`).
* **Cosa eventualmente modificare:**
  all'inizio dello script, nella sezione `SETTAGGI UTENTE`, adatta i percorsi alla tua struttura di cartelle:
  ```r
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
* **Output:** un file Excel (`Enriched_FINAL_taxonomic_reconciliation2.0.xlsx`) diviso nei fogli:
  1. `Unique_Taxa`: tassonomia consolidata per le specie uniche (priorità WCVP > WFO).
  2. `Source_Summary`: mappatura relazionale degli ID.
  3. `FULL_Enriched`: dataset originale con l'arricchimento tassonomico completo.

---

### 2. `gbif_alcotra_occurrences.py`

Calcola in modo automatico e rigoroso il numero di occorrenze botaniche georeferenziate su **GBIF** all'interno delle province e dei dipartimenti dell'area transfrontaliera **ALCOTRA** (Italia/Francia).

* **Territori analizzati:** Torino, Cuneo, Imperia, Valle d'Aosta, Haute-Savoie, Savoie, Hautes-Alpes, Alpes-de-Haute-Provence, Alpes-Maritimes.
* **Caratteristiche tecniche:**
  * utilizza i confini amministrativi ufficiali **GADM 4.1**;
  * accetta solo match tassonomici esatti (`matchType = EXACT`) per evitare falsi positivi da fuzzy matching;
  * gestisce i *rate limit* (retry automatico in caso di errori 429/50x).
* **Cosa eventualmente modificare:**
  nella funzione `analizza_checklist()` a fondo pagina puoi cambiare il file Excel/CSV di input e il nome del file di output:
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
* **Output:** un CSV (`risultati_gbif_alcotra.csv`) con il conteggio delle osservazioni e i flag di presenza (`TRUE`/`FALSE`) per ciascuna area ALCOTRA.

---

### 3. `conservation_enrichment_complete.py`

È il motore principale di data mining per l'arricchimento ecologico-conservazionistico delle specie. Interroga le API ufficiali IUCN e Species+.

* **Parametri estratti:**
  * **IUCN Red List:** status Global (Scope 1), Europe (Scope 2), Mediterranean (Scope 4), forme di crescita, minacce, uso e commercio, habitat (Scheme v3.1), fattori di stress.
  * **Species+:** Appendici CITES e Direttiva Habitat UE.
* **Architettura fault-tolerant:**
  * **Cache SQLite:** crea automaticamente il database locale `specie_conservazione_completa.db`, dove salva ogni specie appena viene processata. Se l'esecuzione viene interrotta (es. caduta di connessione o `CTRL+C`), riparte dall'ultimo taxon rimasto in stato `DA_ELABORARE`.
  * **File di log:** registra il dettaglio delle operazioni in `enrichment_completo.log`.
* **Cosa eventualmente modificare:**
  nella sezione `CONFIGURAZIONE FILE E PATH`:
  ```python
  FILE_EXCEL  = os.path.join(BASE_DIR, "NEW_db.xlsx")  # File Excel di origine
  NOME_FOGLIO = "clean_results"                        # Foglio da leggere
  FILE_OUTPUT = os.path.join(BASE_DIR, "WCVP_conservation_enriched_complete.xlsx")
  ```
* **Come eseguirlo:**
  ```bash
  python conservation_enrichment_complete.py
  ```
* **Output:** file Excel finale arricchito (`WCVP_conservation_enriched_complete.xlsx`).

---

### 4. `matrix_normalization_explode.py`

Risolve il problema delle variabili multivalore concatenate estratte dalle API (es. habitat o minacce separate da `|` o formattate come JSON). Trasforma il dataset in una struttura atomica in **Prima Forma Normale (1NF)**, pronta per DBMS relazionali o SQLite.

* **Funzionalità:**
  * esplode (*explode*) le liste molti-a-molti (N:N);
  * pulisce i residui di sintassi JSON/dizionari (es. `{'en': '...`);
  * rimuove i duplicati e i valori vuoti di sistema.
* **Cosa eventualmente modificare:**
  nella sezione `CONFIGURAZIONE`:
  ```python
  FILE_INPUT  = os.path.join(BASE_DIR, "NEW_db.xlsx")  # Input con i dati grezzi
  NOME_FOGLIO = "clean_results"
  FILE_OUTPUT = os.path.join(BASE_DIR, "Database_Normalizzato_Fogli_Separati.xlsx")
  ```
* **Come eseguirlo:**
  ```bash
  python matrix_normalization_explode.py
  ```
* **Output:** file Excel (`Database_Normalizzato_Fogli_Separati.xlsx`) con 8 fogli distinti, uno per entità:
  `Status_IUCN_Global`, `Status_IUCN_Europe`, `Status_IUCN_Mediterranean`, `Growth_Forms`, `Threats`, `Uses_and_Trade`, `Habitats`, `Stresses`.

---

## Note sulla sicurezza e `.gitignore`

Per evitare di caricare accidentalmente dati personali, token riservati o file pesanti su GitHub, assicurati che nella radice del progetto sia presente un file `.gitignore` con questo contenuto:

```gitignore
# Variabili d'ambiente e credenziali (MAI caricare i token)
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

# Eccezione: eventuale dataset dimostrativo di piccole dimensioni
!esempio_input.xlsx

# Ambienti virtuali Python
venv/
.venv/
__pycache__/
```

Se un token è stato caricato per errore, **revocalo e generane uno nuovo**: cancellare il file dal repository non basta, perché resta nella cronologia di Git.

---

## Licenza

Il codice è distribuito con licenza **MIT**. Vedi il file [`LICENSE`](LICENSE) per il testo completo.

I dati ottenuti tramite API e backbone esterni (IUCN, Species+, GBIF, WCVP, WFO, IPNI) restano soggetti alle condizioni d'uso dei rispettivi fornitori.

---

## Come citare

Se usi questa pipeline in un lavoro di ricerca, puoi citarla così:

> Gastaudo, A. M. (2026). *COrALp: Database & Pipeline Computazionale* (Progetto Interreg ALCOTRA COrALp, Università degli Studi di Torino). GitHub. https://github.com/alixgasta/COrALp

GitHub mostra anche il pulsante **"Cite this repository"**, generato dal file [`CITATION.cff`](CITATION.cff).

---

## Autore e contatti

**Alasia Maria Gastaudo**
Università degli Studi di Torino · Progetto Interreg ALCOTRA COrALp

* GitHub: [github.com/alixgasta](https://github.com/alixgasta)
* LinkedIn: [www.linkedin.com/in/alasia-maria-gastaudo-343419287](www.linkedin.com/in/alasia-maria-gastaudo-343419287)
* Email: alasia.gastaudo@edu.unito.it
