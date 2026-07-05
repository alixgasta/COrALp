# COrALp
Repository ufficiale della pipeline computazionale per il progetto Interreg COrALp. Include gli script in R e Python per l’integrazione, la riconciliazione tassonomica e l’arricchimento ecologico-conservazionistico (IUCN/Species+) della flora delle Alpi Latine, con la struttura del database relazionale normalizzato (1NF).


## conservation_enrichment_complete.py
Questo modulo costituisce il motore di data mining automatizzato in Python progettato per l'arricchimento del nucleo floristico normalizzato del progetto Interreg COrALp (composto da 5.451 entità tassonomiche uniche). Lo script interroga in parallelo e in modo deterministico le API internazionali di riferimento per estrarre metadati legati allo status di conservazione, alle minacce antropiche, ai tratti ecologici e ai vincoli legislativi transfrontalieri della flora alpina.

## Fonti Interrogate e Tratti Estratti
1. **IUCN Red List API (v4)**:
   * Categoria di rischio su tre scale geografiche (Globale, Europeo, Mediterraneo) per analisi geoecologiche comparative.
   * Classificazione degli habitat naturali (Habitats Classification Scheme v3.1).
   * Minacce attive (Threats) e fattori di stress biologico indotto (Stresses).
   * Forme di crescita macro-strutturali (Growth Forms) e profili di utilizzo etnobotanico (Use and Trade).
2. **Species+ API (v1) / UNEP-WCMC**:
   * Grado di tutela cogente internazionale (Appendici CITES I, II, III).
   * Vincoli normativi di conservazione a scala comunitaria (Allegati della Direttiva Habitat 92/43/CEE).

## Architettura e Tolleranza ai Guasti (Fault Tolerance)
Data la natura massiva dell'estrazione (oltre 8 ore di elaborazione remota) e i rigidi limiti di frequenza (*Rate-Limiting*) imposti dagli endpoint ufficiali, lo script integra un'architettura robusta per la persistenza dello stato:
* **Cache di Stato Locale (SQLite)**: Un database locale (`specie_conservazione_completa.db`) tiene traccia dei progressi riga per riga tramite gli stati `DA_ELABORARE` e `COMPLETATO`. In caso di interruzione della rete o crash del sistema, lo script riprende l'elaborazione esattamente dall'ultimo record valido, fungendo da checkpoint di ripristino.
* **Retry Logic ed Exponential Backoff**: Gestione automatica degli errori HTTP 429 (Too Many Requests) e dei timeout di rete mediante cicli di attesa progressivi.
* **Logging di Sistema**: Tracciamento asincrono dettagliato delle metriche e delle risposte API nel file `enrichment_completo.log`.

## Prerequisiti
Le chiavi digitali di autenticazione devono essere memorizzate in un file `.env` locale nella directory radice dello script:
IUCN_TOKEN="il_tuo_token_iucn"
SPECIES_TOKEN="il_tuo_token_species_plus"


# matrix_normalization_explode.py
Questo script automatizza la scomposizione e la normalizzazione delle variabili multivalore generate dalle pipeline di data mining (API IUCN). Nel database floristico originario, attributi ecologici complessi come minacce (Threats), habitat (Habitats), forme di crescita (Growth Forms) e fattori di stress (Stresses) sono memorizzati come stringhe concatenate e nidificate in formato pseudo-JSON, separate dal delimitatore verticale `|`.

Al fine di convertire queste relazioni molti-a-molti (N:N) in strutture atomiche compatibili con i principi della Prima Forma Normale (1NF) e con l'architettura del database relazionale SQLite del progetto COrALp, lo script esegue una procedura di splitting testuale e un'operazione di *explode* mediante la libreria `pandas`. 

## Funzionalità Principali
* **Caricamento Dinamico**: Lettura controllata del foglio `clean_results` dal database centralizzato.
* **Esplosione delle Relazioni N:N**: Scomposizione delle stringhe multivalore e generazione di righe indipendenti per ciascun attributo ecologico associato al taxon.
* **Pulizia Sintattica**: Rimozione deterministica tramite espressioni regolari (Regex) dei marcatori residuali dei dizionari e delle stringhe JSON (es. `{'en': '...``).
* **Filtro del Rumore**: Eliminazione automatica di valori nulli di sistema (`NaN`, `None`, `null`, `stringhe vuote`).
* **Deduplicazione Globale**: Rimozione delle ridondanze nominali per garantire l'atomicità e l'integrità referenziale delle matrici risultanti.

## Output Generato
Lo script produce un file Excel denominato `Database_Normalizzato_Fogli_Separati.xlsx` articolato in 8 fogli relazionali indipendenti e pronti per l'importazione nel DBMS:
1. `Status_IUCN_Global`
2. `Status_IUCN_Europe`
3. `Status_IUCN_Mediterranean`
4. `Growth_Forms`
5. `Threats`
6. `Uses_and_Trade`
7. `Habitats`
8. `Stresses`


