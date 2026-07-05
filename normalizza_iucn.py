import pandas as pd
import os

# ─────────────────────────────────────────────
#  CONFIGURAZIONE
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Il tuo mega-database di partenza (lettura)
FILE_INPUT  = os.path.join(BASE_DIR, "NEW_db.xlsx")
NOME_FOGLIO = "clean_results" 

# 2. Il NUOVO file che verrà creato con tutte le pagine separate
FILE_OUTPUT = os.path.join(BASE_DIR, "Database_Normalizzato_Fogli_Separati.xlsx")

print("Caricamento del database gigante in corso...")
df = pd.read_excel(FILE_INPUT, sheet_name=NOME_FOGLIO)

print("\n--- COLONNE CHE PYTHON VEDE NEL TUO FILE ---")
print(df.columns.tolist())
print("--------------------------------------------\n")

# ─────────────────────────────────────────────
#  FUNZIONE MOTORE AGGIORNATA
# ─────────────────────────────────────────────
def estrai_e_pulisci(df, colonna_target):
    if colonna_target not in df.columns:
        print(f"   ❌ ERRORE: La colonna '{colonna_target}' NON ESISTE! Controlla i nomi esatti.")
        return pd.DataFrame()

    # Seleziona le colonne base ('Nome', 'ID') in modo dinamico se esistono
    colonne_base = ['Nome', 'ID']
    colonne_presenti = [c for c in colonne_base if c in df.columns]
    
    df_subset = df[colonne_presenti + [colonna_target]].copy()
    
    # 1. Rimuove i veri valori nulli (NaN di pandas) per evitare crash
    df_subset = df_subset.dropna(subset=[colonna_target])
    
    # Converte in stringa 
    df_subset[colonna_target] = df_subset[colonna_target].astype(str).str.strip()
    
    # 2. GESTIONE RELAZIONE N:N (Split)
    # Dividiamo PRIMA sulle barre verticali " | ", così isoliamo ogni singolo record
    df_subset[colonna_target] = df_subset[colonna_target].str.split(r'\s*\|\s*')
    
    # Creiamo una riga separata per ogni elemento della lista (esplosione N:N)
    df_esploso = df_subset.explode(colonna_target)
    
    # 3. PULIZIA DELLA SINTASSI JSON / DIZIONARIO
    # Rimuove `{'en': '` all'inizio e `'}` alla fine di ogni elemento
    df_esploso[colonna_target] = df_esploso[colonna_target].str.replace(r"\{'en':\s*['\"]", "", regex=True)
    df_esploso[colonna_target] = df_esploso[colonna_target].str.replace(r"['\"]\s*\}", "", regex=True)
    df_esploso[colonna_target] = df_esploso[colonna_target].str.strip()
    
    # 4. FILTRO VALORI DA SCARTARE (Ora manteniamo 'not found')
    # Scartiamo solo i valori vuoti o nulli di sistema
    valori_da_scartare = ['nan', 'none', '', '<na>', 'null']
    df_esploso = df_esploso[~df_esploso[colonna_target].str.lower().isin(valori_da_scartare)]
    
    # 5. ELIMINAZIONE DUPLICATI
    # Pulisce i record multipli per la stessa specie (inclusi i multipli 'not found')
    df_esploso = df_esploso.drop_duplicates()
    
    print(f"   ✓ Perfetto! Trovati ed esplosi {len(df_esploso)} record univoci per '{colonna_target}'.")
    return df_esploso

# ─────────────────────────────────────────────
#  ESECUZIONE E CREAZIONE DEL NUOVO FILE (8 FOGLI)
# ─────────────────────────────────────────────

# In questo dizionario puoi mappare il nome esatto della colonna (a sinistra) 
# con il nome che vuoi dare alla pagina Excel (a destra - max 31 caratteri)
colonne_da_elaborare = {
    'status_iucn_global': 'Status_IUCN_Global',
    'status_iucn_europe': 'Status_IUCN_Europe',
    'status_iucn_mediterranean': 'Status_IUCN_Mediterranean',
    'growth_forms': 'Growth_Forms',
    'threats': 'Threats',
    'uses_and_trade': 'Uses_and_Trade',
    'habitats': 'Habitats',
    'stresses': 'Stresses'
}

print(f"Avvio elaborazione di {len(colonne_da_elaborare)} colonne richieste...")

file_creato = False

# Usiamo ExcelWriter per inserire più fogli (pagine) nello stesso file Excel
with pd.ExcelWriter(FILE_OUTPUT, engine='openpyxl') as writer:
    for colonna_excel, nome_foglio in colonne_da_elaborare.items():
        print(f"\nElaborazione colonna: '{colonna_excel}'...")
        
        # Chiamata alla funzione di pulizia ed esplosione
        df_risultato = estrai_e_pulisci(df, colonna_excel)
        
        # Se il dataframe risultante non è vuoto, lo salviamo in una pagina dedicata
        if not df_risultato.empty:
            df_risultato.to_excel(writer, sheet_name=nome_foglio, index=False)
            file_creato = True
        else:
            print(f"  ⚠️ Pagina '{nome_foglio}' SALTATA: colonna non trovata o senza dati validi.")

# Messaggio finale di controllo
if file_creato:
    print(f"\n✅ Operazione completata! Il nuovo file è pronto: {FILE_OUTPUT}")
    print("Ogni colonna è stata isolata nella sua pagina con Nome, ID e valori correttamente scomposti.")
else:
    print("\n❌ ERRORE: Nessun foglio conteneva dati validi. Controlla i messaggi di errore precedenti.")