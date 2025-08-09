import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ---- CONFIG (da Secrets) ----
SHEET_ID = st.secrets["SHEET"]["id"]
WORKSHEET_NAME = st.secrets["SHEET"].get("worksheet", None)
SERVICE_ACCOUNT_INFO = st.secrets["gcp_service_account"]

# ---- Nomi colonne ----
COL_CHAR = "caratteri"
COL_PINYIN = "pinyin"
COL_TRAD = "traduzione"
COL_APPR = "appr"

# ---- GSpread ----
@st.cache_resource(show_spinner=False)
def get_ws():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    return sh.worksheet(WORKSHEET_NAME) if WORKSHEET_NAME else sh.sheet1

def read_df(ws):
    data = ws.get_all_records(numericise_ignore=["all"])
    df = pd.DataFrame(data)
    df.columns = df.columns.str.strip().str.lower()
    if COL_APPR in df.columns:
        df[COL_APPR] = pd.to_numeric(df[COL_APPR], errors="coerce")
    return df

def header_and_cols(ws):
    header = [h.strip().lower() for h in ws.row_values(1)]
    col_map = {name: (header.index(name) + 1) if name in header else None
               for name in [COL_CHAR, COL_PINYIN, COL_TRAD, COL_APPR]}
    return 1, col_map

def update_appr(ws, row_1based, value=1):
    _, col_map = header_and_cols(ws)
    c_appr = col_map[COL_APPR]
    if c_appr is None:
        raise ValueError(f"Colonna '{COL_APPR}' non trovata.")
    ws.update_cell(row_1based, c_appr, value)

# ---- UI state ----
if "current_row_index" not in st.session_state:
    st.session_state.current_row_index = None
if "revealed" not in st.session_state:
    st.session_state.revealed = False
if "correct" not in st.session_state:
    st.session_state.correct = 0
if "attempts" not in st.session_state:
    st.session_state.attempts = 0
if "ended" not in st.session_state:
    st.session_state.ended = False

st.set_page_config(page_title="Quiz Cinese", page_icon="🀄", layout="centered")
st.title("🀄 Quiz di Cinese")
st.caption("Pesca casualmente tra le righe con appr ≠ 1. Mostra pinyin+traduzione, poi i caratteri.")

ws = get_ws()
df = read_df(ws)

# Controllo colonne
required = [COL_CHAR, COL_PINYIN, COL_TRAD, COL_APPR]
missing = [c for c in required if c not in df.columns]
if missing:
    st.error(f"Mancano colonne nel foglio: {missing}")
    st.stop()

# Pool: appr è NaN oppure diverso da 1
pool = df[(df[COL_APPR].isna()) | (df[COL_APPR] != 1)]

# Fine sessione
if st.session_state.ended:
    st.subheader("📊 Risultati della sessione")
    st.write(f"**Corrette:** {st.session_state.correct}")
    st.write(f"**Tentativi:** {st.session_state.attempts}")
    perc = (st.session_state.correct / st.session_state.attempts * 100) if st.session_state.attempts else 0
    st.write(f"**Accuratezza:** {perc:.0f}%")
    st.info("Ricarica la pagina per ricominciare.")
    st.stop()

if pool.empty:
    st.success("🎉 Tutte le parole risultano già apprese (appr = 1).")
else:
    colA, colB, colC, colD, colE = st.columns([1,1,1,1,1])
    with colA:
        if st.button("🎲 Nuovo termine", use_container_width=True):
            st.session_state.current_row_index = pool.sample(1).index[0]
            st.session_state.revealed = False
    with colB:
        if st.button("👁 Mostra caratteri", use_container_width=True):
            st.session_state.revealed = True
    with colC:
        if st.button("✅ Lo conosco", use_container_width=True, disabled=st.session_state.current_row_index is None):
            if st.session_state.current_row_index is not None:
                header_row, _ = header_and_cols(ws)
                row_idx = st.session_state.current_row_index
                sheet_row = header_row + row_idx + 1
                try:
                    update_appr(ws, sheet_row, 1)
                    st.session_state.correct += 1
                    st.session_state.attempts += 1
                    st.session_state.current_row_index = None
                    st.session_state.revealed = False
                    st.toast("Aggiornato (appr = 1)", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore aggiornando il foglio: {e}")
    with colD:
        if st.button("🤔 Non ancora", use_container_width=True, disabled=st.session_state.current_row_index is None):
            st.session_state.attempts += 1
            st.session_state.current_row_index = None
            st.session_state.revealed = False
    with colE:
        if st.button("❌ Termina sessione", use_container_width=True):
            st.session_state.ended = True
            st.rerun()

    if st.session_state.current_row_index is not None:
        row = df.loc[st.session_state.current_row_index]
        st.subheader("🎯 Termine estratto")
        st.markdown(f"**Pinyin:** {row[COL_PINYIN]}")
        st.markdown(f"**Traduzione:** {row[COL_TRAD]}")
        if st.session_state.revealed:
            st.markdown(f"**Caratteri:** {row[COL_CHAR]}")
        else:
            st.info("Premi **👁 Mostra caratteri** per vedere gli ideogrammi.")

st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Corrette", st.session_state.correct)
c2.metric("Tentativi", st.session_state.attempts)
perc = (st.session_state.correct / st.session_state.attempts * 100) if st.session_state.attempts else 0
c3.metric("Accuratezza", f"{perc:.0f}%")
st.caption("Suggerimento: tocca **🎲 Nuovo termine** per iniziare.")
