# ============================================================
# SCRIPT DI RICONCILIAZIONE TASSONOMICA (WCVP > WFO) + IPNI  -  v2
# Colonne attese nel file di input:
#   row_id, species_name, infra_rank, parsed_name, parsed_author,
#   family, is_edible, lifeform_description, wcvp_id, wfo_id
# Logica: se wcvp_id / wfo_id esistono -> lookup esatto per ID;
#         altrimenti -> matching per nome (exact + fuzzy).
# ============================================================

# ---------------- LIBRERIE ----------------
library(dplyr)
library(stringr)
library(tibble)
library(readxl)
library(openxlsx)
library(readr)

# remotes::install_github("matildabrown/rWCVP")
# install.packages("WorldFlora")
library(rWCVP)
library(WorldFlora)

# ---------------- SETTAGGI UTENTE ----------------
input_file <- "C:/Users/alixg/Downloads/RICONCILIAZIONE/NEW_WCVP_taxonomic_enrichment.xlsx"
sheet_name <- "LatinAlps_SpeciesDB_v0.2"

wcvp_backbone_csv <- "wcvp_backbone_csv.csv"   # separatore "|"
wfo_backbone_csv  <- "wfo_backbone_csv.csv"    # separatore tab

output_file <- "Enriched_FINAL_taxonomic_reconciliation2.0.xlsx"

# ---------------- FUNZIONI DI SERVIZIO ----------------
# Aggiunge come NA le colonne mancanti (evita errori se cambiano i nomi tra versioni)
ensure_cols <- function(df, cols) {
  for (cc in cols) if (!cc %in% names(df)) df[[cc]] <- NA_character_
  df
}

# Primo valore non vuoto di un vettore
first_non_na <- function(x) {
  x <- x[!is.na(x) & x != ""]
  if (length(x)) x[1] else NA_character_
}

# ---------------- 1. LETTURA DATI ----------------
message("Lettura del file originale...")
dat <- read_excel(input_file, sheet = sheet_name)
names(dat) <- trimws(names(dat))

# Controllo colonne essenziali
stopifnot("parsed_name" %in% names(dat))
dat <- ensure_cols(dat, c("wcvp_id", "wfo_id"))
dat <- dat %>% mutate(across(c(wcvp_id, wfo_id), as.character))

# NOMI UNICI + eventuali ID già presenti nel dataset
unique_taxa <- dat %>%
  filter(!is.na(parsed_name)) %>%
  group_by(parsed_name) %>%
  summarise(
    in_wcvp_id = first_non_na(wcvp_id),
    in_wfo_id  = first_non_na(wfo_id),
    .groups = "drop"
  ) %>%
  mutate(match_id = row_number())

message(paste("Trovati", nrow(unique_taxa), "nomi unici da interrogare."))
message(paste("  - con wcvp_id già presente:", sum(!is.na(unique_taxa$in_wcvp_id))))
message(paste("  - con wfo_id già presente: ", sum(!is.na(unique_taxa$in_wfo_id))))

# ---------------- 2. WCVP ----------------
message("Caricamento backbone WCVP locale...")
wcvp_db <- read_delim(wcvp_backbone_csv, delim = "|",
                      col_types = cols(.default = "c"), show_col_types = FALSE)
names(wcvp_db) <- tolower(trimws(names(wcvp_db)))
wcvp_db <- ensure_cols(wcvp_db, c("plant_name_id", "ipni_id", "accepted_plant_name_id",
                                  "taxon_name", "taxon_authors", "taxon_status",
                                  "family", "lifeform_description"))

# Tabella standardizzata: una riga per ogni plant_name_id
wcvp_std <- wcvp_db %>%
  transmute(
    wcvp_id            = plant_name_id,
    wcvp_ipni_id       = ipni_id,
    wcvp_accepted_id   = coalesce(accepted_plant_name_id, plant_name_id),
    wcvp_accepted_name = taxon_name,   # nome matchato (come nello script originale)
    wcvp_author        = taxon_authors,
    wcvp_status        = taxon_status,
    wcvp_family        = family,
    wcvp_lifeform      = lifeform_description
  ) %>%
  distinct(wcvp_id, .keep_all = TRUE)

# IPNI del nome ACCETTATO
wcvp_accepted_ipni <- wcvp_std %>%
  transmute(wcvp_accepted_id = wcvp_id, wcvp_ipni_id_accepted = wcvp_ipni_id)

# Funzione di matching per nome su WCVP -> restituisce match_id, wcvp_id
match_wcvp <- function(df) {   # df: match_id, name
  if (nrow(df) == 0) return(tibble(match_id = integer(), wcvp_id = character()))
  inp <- df %>% transmute(match_id, taxon_name = name, taxon_author = NA_character_)
  res <- rWCVP::wcvp_match_names(
    names_df   = inp,
    wcvp_names = wcvp_db,
    name_col   = "taxon_name",
    id_col     = "match_id"
  )
  res <- ensure_cols(res, "wcvp_id")
  res %>%
    mutate(wcvp_id = as.character(wcvp_id)) %>%
    filter(!is.na(wcvp_id)) %>%
    group_by(match_id) %>%
    slice(1) %>%
    ungroup() %>%
    select(match_id, wcvp_id)
}

# 2a. Lookup per ID
wcvp_by_id <- unique_taxa %>%
  filter(!is.na(in_wcvp_id), in_wcvp_id %in% wcvp_std$wcvp_id) %>%
  transmute(match_id, wcvp_id = in_wcvp_id, wcvp_match_method = "ID")

# 2b. Matching per nome (solo per chi non ha ID valido)
message("Matching per nome su WCVP...")
todo <- unique_taxa %>% filter(!match_id %in% wcvp_by_id$match_id)

wcvp_by_name <- match_wcvp(todo %>% transmute(match_id, name = parsed_name)) %>%
  mutate(wcvp_match_method = "Name")

# 2c. Secondo tentativo per ibridi senza il simbolo "×"
todo2 <- todo %>%
  filter(!match_id %in% wcvp_by_name$match_id, str_detect(parsed_name, "^×")) %>%
  transmute(match_id, name = str_remove(parsed_name, "^×\\s*"))

wcvp_by_name2 <- match_wcvp(todo2) %>%
  mutate(wcvp_match_method = "Name (no hybrid sign)")

wcvp_best <- bind_rows(wcvp_by_id, wcvp_by_name, wcvp_by_name2) %>%
  left_join(wcvp_std, by = "wcvp_id") %>%
  left_join(wcvp_accepted_ipni, by = "wcvp_accepted_id") %>%
  mutate(wcvp_genus = str_split_i(wcvp_accepted_name, " ", 1))

# ---------------- 3. WFO ----------------
message("Caricamento backbone WFO locale...")
wfo_db <- read_delim(wfo_backbone_csv, delim = "\t",
                     col_types = cols(.default = "c"), show_col_types = FALSE)
wfo_db <- ensure_cols(wfo_db, c("taxonID", "scientificNameID", "scientificName",
                                "scientificNameAuthorship", "taxonomicStatus", "family"))

wfo_std <- wfo_db %>%
  transmute(
    wfo_id            = taxonID,
    wfo_accepted_name = scientificName,
    wfo_author        = scientificNameAuthorship,
    wfo_status        = taxonomicStatus,
    wfo_family        = family,
    wfo_sci_name_id   = scientificNameID
  ) %>%
  distinct(wfo_id, .keep_all = TRUE) %>%
  mutate(
    wfo_genus = str_split_i(wfo_accepted_name, " ", 1),
    # estrae "123456-1" solo se l'ID è un LSID IPNI (altrimenti NA: può essere Tropicos ecc.)
    wfo_ipni_id = ifelse(str_detect(wfo_sci_name_id, "ipni"),
                         str_extract(wfo_sci_name_id, "[0-9]+-[0-9]+$"),
                         NA_character_)
  )

# Funzione di matching per nome su WFO -> restituisce match_id, wfo_id
match_wfo <- function(df) {   # df: match_id, name
  if (nrow(df) == 0) return(tibble(match_id = integer(), wfo_id = character()))
  inp <- df %>% transmute(match_id, parsed_name = name) %>% as.data.frame()
  res <- WorldFlora::WFO.match(
    spec.data = inp,
    spec.name = "parsed_name",
    WFO.data  = wfo_db,
    Fuzzy     = 2,
    Fuzzy.min = FALSE
  )
  res <- ensure_cols(res, "taxonID")
  res %>%
    mutate(wfo_id = as.character(taxonID)) %>%
    filter(!is.na(wfo_id), wfo_id != "") %>%
    group_by(match_id) %>%
    slice(1) %>%
    ungroup() %>%
    select(match_id, wfo_id)
}

# 3a. Lookup per ID
wfo_by_id <- unique_taxa %>%
  filter(!is.na(in_wfo_id), in_wfo_id %in% wfo_std$wfo_id) %>%
  transmute(match_id, wfo_id = in_wfo_id, wfo_match_method = "ID")

# 3b. Matching per nome
message("Matching per nome su WFO...")
todo <- unique_taxa %>% filter(!match_id %in% wfo_by_id$match_id)

wfo_by_name <- match_wfo(todo %>% transmute(match_id, name = parsed_name)) %>%
  mutate(wfo_match_method = "Name")

# 3c. Secondo tentativo per ibridi senza "×"
todo2 <- todo %>%
  filter(!match_id %in% wfo_by_name$match_id, str_detect(parsed_name, "^×")) %>%
  transmute(match_id, name = str_remove(parsed_name, "^×\\s*"))

wfo_by_name2 <- match_wfo(todo2) %>%
  mutate(wfo_match_method = "Name (no hybrid sign)")

wfo_best <- bind_rows(wfo_by_id, wfo_by_name, wfo_by_name2) %>%
  left_join(wfo_std, by = "wfo_id")

# ---------------- 4. CONSOLIDAMENTO (PRIORITÀ WCVP) ----------------
message("Consolidamento dei risultati (Priorità WCVP > WFO)...")

resolved_unique_taxa <- unique_taxa %>%
  left_join(wcvp_best, by = "match_id") %>%
  left_join(wfo_best,  by = "match_id") %>%
  mutate(
    has_wcvp = !is.na(wcvp_accepted_name),
    has_wfo  = !is.na(wfo_accepted_name),
    
    Final_Taxon_Name = ifelse(has_wcvp, wcvp_accepted_name,
                              ifelse(has_wfo, wfo_accepted_name, parsed_name)),
    Final_Author     = ifelse(has_wcvp, wcvp_author, wfo_author),
    Final_Genus      = ifelse(has_wcvp, wcvp_genus,  wfo_genus),
    Final_Family     = ifelse(has_wcvp, wcvp_family, wfo_family),
    Final_Status     = ifelse(has_wcvp, wcvp_status, wfo_status),
    Final_Lifeform   = wcvp_lifeform,          # presente solo su WCVP
    Final_WCVP_ID    = wcvp_id,
    Final_WFO_ID     = wfo_id,
    
    # --- IPNI ---
    IPNI_ID          = ifelse(has_wcvp, wcvp_ipni_id, wfo_ipni_id),   # nome matchato
    IPNI_ID_Accepted = ifelse(has_wcvp, wcvp_ipni_id_accepted, NA_character_),
    IPNI_URL         = ifelse(!is.na(IPNI_ID),
                              paste0("https://www.ipni.org/n/", IPNI_ID),
                              NA_character_),
    
    WCVP_Match_Method = wcvp_match_method,
    WFO_Match_Method  = wfo_match_method,
    Source_Used      = ifelse(has_wcvp, "WCVP", ifelse(has_wfo, "WFO", "Not Found"))
  ) %>%
  select(parsed_name, Final_Taxon_Name, Final_Author, Final_Genus, Final_Family,
         Final_Lifeform, Final_Status, Final_WCVP_ID, Final_WFO_ID,
         IPNI_ID, IPNI_ID_Accepted, IPNI_URL,
         WCVP_Match_Method, WFO_Match_Method, Source_Used)

# ---------------- 5. TABELLE DI OUTPUT ----------------

# Foglio 1: "Unique_Taxa" -> resolved_unique_taxa

# Foglio 2: "Source_Summary" -> relazionale (usa le colonne ID che esistono)
source_summary <- dat %>%
  select(any_of(c("row_id", "row_id_db", "db_id")), parsed_name)

# Foglio 3: "FULL_Enriched" -> dati originali + tassonomia (nessun duplicato eliminato)
full_enriched <- dat %>%
  left_join(resolved_unique_taxa, by = "parsed_name") %>%
  mutate(
    # TRUE se la famiglia originale differisce da quella del backbone
    Family_Check = case_when(
      is.na(family) | is.na(Final_Family) ~ NA,
      family != Final_Family              ~ TRUE,
      TRUE                                ~ FALSE
    )
  )

# ---------------- 6. ESPORTAZIONE IN EXCEL ----------------
message("Esportazione su Excel...")
wb <- createWorkbook()

addWorksheet(wb, "Unique_Taxa")
addWorksheet(wb, "Source_Summary")
addWorksheet(wb, "FULL_Enriched")

writeDataTable(wb, "Unique_Taxa", resolved_unique_taxa)
writeDataTable(wb, "Source_Summary", source_summary)
writeDataTable(wb, "FULL_Enriched", full_enriched)

saveWorkbook(wb, output_file, overwrite = TRUE)

# ---------------- RIEPILOGO ----------------
message("======================================")
message("ELABORAZIONE COMPLETATA!")
message(paste("File salvato come:", output_file))
print(table(resolved_unique_taxa$Source_Used, useNA = "ifany"))
message(paste("Taxa con IPNI_ID:", sum(!is.na(resolved_unique_taxa$IPNI_ID)),
              "su", nrow(resolved_unique_taxa)))
message(paste("Righe con famiglia discordante:",
              sum(full_enriched$Family_Check, na.rm = TRUE)))
message("======================================")
