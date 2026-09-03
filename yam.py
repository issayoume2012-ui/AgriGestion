# ============================================================
# YouAgronoMe (YAM) — Agriculture Operations Platform
# Version refondue : modules, rôles, Supabase Storage, IA agricole,
# rapports PDF intelligents et gestion professionnelle du temps.
#
# Dépendances :
#   pip install streamlit pandas supabase reportlab folium
#               streamlit-folium openai pillow
#
# Secrets Streamlit (.streamlit/secrets.toml) :
#   SUPABASE_URL = "https://....supabase.co"
#   SUPABASE_KEY = "..."
#   SUPABASE_BUCKET = "yam-media"
#   OPENAI_API_KEY = "sk-..."
#   OPENAI_MODEL = "gpt-5.6-sol"
#
# IMPORTANT :
#   - Les mots de passe existants de l'ancien projet sont conservés
#     pour compatibilité. Pour une vraie production, migrer vers
#     Supabase Auth et ne plus stocker de mots de passe en clair.
#   - Le fichier SQL fourni avec cette version crée les colonnes/tables
#     nécessaires et le bucket Storage.
# ============================================================

import io
import os
import re
import json
import math
import hashlib
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from supabase import create_client, Client

import folium
from folium.plugins import Draw
from streamlit_folium import st_folium

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image as RLImage, KeepTogether
)

try:
    from PIL import Image
except Exception:
    Image = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# ============================================================
# 1. CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="YouAgronoMe — YAM",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

try:
    st.set_option("client.toolbarMode", "minimal")
except Exception:
    pass

APP_NAME = "YouAgronoMe"
APP_SHORT = "YAM"
UPLOAD_DIR = Path("uploads_workspace")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ROLES = [
    "Administration",
    "Propriétaire",
    "Gestionnaire",
    "Technicien Supérieur",
    "Technicien",
    "Stagiaire",
]

ROLE_LEVEL = {
    "Stagiaire": 10,
    "Technicien": 20,
    "Technicien Supérieur": 30,
    "Gestionnaire": 40,
    "Propriétaire": 50,
    "Administration": 100,
}

# Titres/modules de la liste blanche.
MODULES = {
    "📊 Tableau de Bord": "pilotage",
    "🧭 Centre Opérations": "operations",
    "🌱 Cartographie & Parcelles": "parcelles",
    "⏰ Temps & Pointage": "temps",
    "📅 Planning & Travaux": "travaux",
    "🌾 Récoltes & Rendements": "recoltes",
    "🌧️ Pluviométrie": "pluviometrie",
    "💧 Irrigation & Eau": "irrigation",
    "⚠️ Incidents & Observations": "incidents",
    "🏷️ Traçabilité & Lots": "tracabilite",
    "📦 Intrants & Stocks": "stocks",
    "🚜 Matériel & Maintenance": "materiel",
    "💰 Finances & Coûts": "finances",
    "📈 Rentabilité & ROI": "roi",
    "🌤️ Risques & Météo": "risques",
    "🤖 IA Agricole": "ia",
    "💬 Collaboration & Workspace": "workspace",
    "📑 Rapports Professionnels": "rapports",
    "🔐 Liste Blanche & Administration": "admin",
    "📜 Journal d'Audit": "audit",
}

DEFAULT_ROLE_MODULES = {
    "Administration": list(MODULES.keys()),
    "Propriétaire": [
        "📊 Tableau de Bord", "🧭 Centre Opérations",
        "🌱 Cartographie & Parcelles", "📅 Planning & Travaux",
        "🌾 Récoltes & Rendements", "📦 Intrants & Stocks",
        "🚜 Matériel & Maintenance", "💰 Finances & Coûts",
        "📈 Rentabilité & ROI", "🌤️ Risques & Météo",
        "🤖 IA Agricole", "💬 Collaboration & Workspace",
        "📑 Rapports Professionnels",
    ],
    "Gestionnaire": [
        "📊 Tableau de Bord", "🧭 Centre Opérations",
        "🌱 Cartographie & Parcelles", "⏰ Temps & Pointage",
        "📅 Planning & Travaux", "🌾 Récoltes & Rendements",
        "🌧️ Pluviométrie", "💧 Irrigation & Eau",
        "⚠️ Incidents & Observations", "🏷️ Traçabilité & Lots",
        "📦 Intrants & Stocks", "🚜 Matériel & Maintenance",
        "💰 Finances & Coûts", "📈 Rentabilité & ROI",
        "🌤️ Risques & Météo", "🤖 IA Agricole",
        "💬 Collaboration & Workspace", "📑 Rapports Professionnels",
    ],
    "Technicien Supérieur": [
        "📊 Tableau de Bord", "🧭 Centre Opérations",
        "🌱 Cartographie & Parcelles", "⏰ Temps & Pointage",
        "📅 Planning & Travaux", "🌾 Récoltes & Rendements",
        "🌧️ Pluviométrie", "💧 Irrigation & Eau",
        "⚠️ Incidents & Observations", "🏷️ Traçabilité & Lots",
        "📦 Intrants & Stocks", "🚜 Matériel & Maintenance",
        "🌤️ Risques & Météo", "🤖 IA Agricole",
        "💬 Collaboration & Workspace", "📑 Rapports Professionnels",
    ],
    "Technicien": [
        "🧭 Centre Opérations", "🌱 Cartographie & Parcelles",
        "⏰ Temps & Pointage", "📅 Planning & Travaux",
        "🌾 Récoltes & Rendements", "🌧️ Pluviométrie",
        "💧 Irrigation & Eau", "⚠️ Incidents & Observations",
        "🏷️ Traçabilité & Lots", "📦 Intrants & Stocks",
        "🌤️ Risques & Météo", "🤖 IA Agricole",
        "💬 Collaboration & Workspace", "📑 Rapports Professionnels",
    ],
    "Stagiaire": [
        "🧭 Centre Opérations", "🌱 Cartographie & Parcelles",
        "⏰ Temps & Pointage", "📅 Planning & Travaux",
        "⚠️ Incidents & Observations", "🌧️ Pluviométrie",
        "🤖 IA Agricole", "💬 Collaboration & Workspace",
    ],
}

# Alias pour les anciens intitulés.
MODULE_ALIASES = {
    "⏰ Pointage des Horaires": "⏰ Temps & Pointage",
    "⚠️ Incidents": "⚠️ Incidents & Observations",
    "💰 Finances & Marges": "💰 Finances & Coûts",
    "📦 Stocks d'Intrants": "📦 Intrants & Stocks",
    "🚜 Maintenance Matériel": "🚜 Matériel & Maintenance",
    "🌤️ Risques & Météo": "🌤️ Risques & Météo",
    "💬 Espace Collaboration & Workspace": "💬 Collaboration & Workspace",
    "📑 EXPORT RAPPORT PARCELLE": "📑 Rapports Professionnels",
    "📈 Rentabilité & ROI": "📈 Rentabilité & ROI",
}


# ============================================================
# 2. STYLE
# ============================================================

st.markdown(
    """
<style>
.stApp {
    background: linear-gradient(135deg,#f6faf7 0%,#edf5ef 100%);
    color:#17251d;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#10281d 0%,#173b29 100%);
}
[data-testid="stSidebar"] * { color:#f5fbf7 !important; }
.main-header {
    background:linear-gradient(135deg,#ffffff,#eef7f0);
    padding:22px 28px;
    border:1px solid #d7e7dc;
    border-radius:22px;
    box-shadow:0 12px 35px rgba(20,70,40,.10);
    margin:8px 0 18px;
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:16px;
}
.brand-title {font-size:30px;font-weight:900;color:#123b28;}
.brand-subtitle {font-size:13px;color:#5b6f63;margin-top:3px;}
.user-badge {
    background:#dff2e6;color:#17482d;border:1px solid #bddbc8;
    padding:9px 14px;border-radius:999px;font-weight:700;
}
.card {
    background:rgba(255,255,255,.97);
    padding:20px;
    border:1px solid #dce9df;
    border-radius:18px;
    box-shadow:0 10px 30px rgba(24,68,42,.08);
    margin-bottom:16px;
}
.kpi {
    background:#fff;
    border:1px solid #dce9df;
    border-radius:16px;
    padding:16px;
    box-shadow:0 6px 20px rgba(24,68,42,.06);
}
.ai-box {
    background:linear-gradient(135deg,#eef8f1,#ffffff);
    border:1px solid #b9dcc5;
    border-left:5px solid #0e6b3b;
    border-radius:16px;
    padding:18px;
}
.warning-box {
    background:#fffaf0;
    border:1px solid #efd7a2;
    border-left:5px solid #d99000;
    border-radius:14px;
    padding:14px;
}
.danger-box {
    background:#fff5f5;
    border:1px solid #edc3c3;
    border-left:5px solid #b42318;
    border-radius:14px;
    padding:14px;
}
div.stButton > button {
    border-radius:12px;
    font-weight:750;
    min-height:42px;
}
.stTabs [data-baseweb="tab-list"] {
    gap:6px;background:#fff;padding:7px;
    border:1px solid #dce9df;border-radius:15px;
}
.stTabs [data-baseweb="tab"] {
    height:42px;border-radius:10px;font-weight:800;
}
.stTabs [aria-selected="true"] {background:#dff2e6;color:#0e4a2a !important;}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# 3. SUPABASE
# ============================================================

@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
    key = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY", ""))
    if not url or not key:
        st.error("SUPABASE_URL et SUPABASE_KEY sont obligatoires.")
        st.stop()
    return create_client(url, key)


supabase = init_supabase()
SUPABASE_BUCKET = st.secrets.get(
    "SUPABASE_BUCKET", os.getenv("SUPABASE_BUCKET", "yam-media")
)


def db_error_message(exc: Exception) -> str:
    return str(exc).replace("\n", " ")[:600]


@st.cache_data(ttl=15)
def load_table(table_name: str) -> pd.DataFrame:
    try:
        res = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(res.data or [])
    except Exception:
        return pd.DataFrame()


def clear_caches():
    try:
        load_table.clear()
    except Exception:
        pass
    try:
        load_accessible_champs.clear()
    except Exception:
        pass


def db_insert(table: str, data: Dict[str, Any], action: str = "") -> Optional[Dict]:
    try:
        res = supabase.table(table).insert(data).execute()
        clear_caches()
        if action:
            audit_log(action, table, "INSERT", data)
        return (res.data or [None])[0]
    except Exception as exc:
        st.error(f"Erreur Supabase — {table}: {db_error_message(exc)}")
        return None


def db_update(
    table: str, match_col: str, match_val: Any,
    data: Dict[str, Any], action: str = ""
) -> bool:
    try:
        supabase.table(table).update(data).eq(match_col, match_val).execute()
        clear_caches()
        if action:
            audit_log(action, table, "UPDATE", data)
        return True
    except Exception as exc:
        st.error(f"Erreur Supabase — {table}: {db_error_message(exc)}")
        return False


def db_delete(
    table: str, match_col: str, match_val: Any, action: str = ""
) -> bool:
    try:
        supabase.table(table).delete().eq(match_col, match_val).execute()
        clear_caches()
        if action:
            audit_log(action, table, "DELETE", {"match": match_val})
        return True
    except Exception as exc:
        st.error(f"Erreur Supabase — {table}: {db_error_message(exc)}")
        return False


# ============================================================
# 4. SESSION / AUTHENTIFICATION / LISTE BLANCHE
# ============================================================

def current_user() -> Dict[str, Any]:
    return st.session_state.get("yam_user", {}) or {}


def user_email() -> str:
    return str(current_user().get("email", "")).strip().lower()


def user_role() -> str:
    return str(current_user().get("role", "Stagiaire")).strip()


def is_admin() -> bool:
    return user_role() == "Administration" or user_email() == "iy@2012"


def parse_modules(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        values = value
    else:
        text = str(value).strip()
        if not text or text.upper() == "TOUS":
            return ["TOUS"]
        try:
            parsed = json.loads(text)
            values = parsed if isinstance(parsed, list) else text.replace(";", ",").split(",")
        except Exception:
            values = text.replace(";", ",").split(",")
    result = []
    for item in values:
        item = str(item).strip()
        if item in MODULE_ALIASES:
            item = MODULE_ALIASES[item]
        if item:
            result.append(item)
    return result


def allowed_modules() -> List[str]:
    if is_admin():
        return list(MODULES.keys())

    stored = parse_modules(current_user().get("modules_autorises"))
    if "TOUS" in [x.upper() for x in stored]:
        return list(MODULES.keys())

    role_defaults = DEFAULT_ROLE_MODULES.get(user_role(), [])
    # La liste blanche est une restriction supplémentaire.
    if stored:
        return [m for m in role_defaults if m in stored]
    return role_defaults


def module_allowed(module: str) -> bool:
    return module in allowed_modules()


def require_module(module: str) -> bool:
    if module_allowed(module):
        return True
    st.error("🔒 Ce module n'est pas autorisé pour votre rôle / votre liste blanche.")
    return False


def init_admin_if_needed():
    # Compatibilité avec la structure de l'ancien projet.
    try:
        found = (
            supabase.table("whitelist_users")
            .select("*")
            .eq("email", "iy@2012")
            .execute()
        )
        if not found.data:
            supabase.table("whitelist_users").insert({
                "email": "iy@2012",
                "password": "issayoume2026",
                "prenom": "Issa",
                "nom": "Youme",
                "role": "Administration",
                "modules_autorises": "TOUS",
            }).execute()
    except Exception:
        pass


def authenticate() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.6, 1])
    with c2:
        st.markdown(
            """
<div class="card">
<h1 style="text-align:center;color:#0e6b3b;">🌾 YouAgronoMe</h1>
<p style="text-align:center;color:#66776d;">
Plateforme professionnelle de centralisation et de pilotage agricole
</p>
</div>
""",
            unsafe_allow_html=True,
        )
        with st.form("login"):
            email = st.text_input("E-mail professionnel")
            password = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button(
                "Se connecter", type="primary", use_container_width=True
            )
            if submitted:
                try:
                    res = (
                        supabase.table("whitelist_users")
                        .select("*")
                        .ilike("email", email.strip().lower())
                        .execute()
                    )
                    record = (res.data or [None])[0]
                    if record and password == str(record.get("password", "")):
                        st.session_state.authenticated = True
                        st.session_state.yam_user = {
                            "id": record.get("id"),
                            "email": email.strip().lower(),
                            "prenom": record.get("prenom", ""),
                            "nom": record.get("nom", ""),
                            "role": record.get("role", "Technicien"),
                            "modules_autorises": record.get("modules_autorises", "TOUS"),
                        }
                        st.rerun()
                    else:
                        st.error("Identifiants incorrects ou compte non autorisé.")
                except Exception as exc:
                    st.error(f"Connexion Supabase impossible : {db_error_message(exc)}")
    return False


init_admin_if_needed()
if not authenticate():
    st.stop()


# ============================================================
# 5. AUDIT
# ============================================================

def audit_log(action: str, table: str = "", operation: str = "", details: Any = None):
    try:
        u = current_user()
        payload = {
            "date_heure": datetime.now().isoformat(timespec="seconds"),
            "utilisateur": f"{u.get('prenom','')} {u.get('nom','')}".strip(),
            "email": u.get("email", ""),
            "role": u.get("role", ""),
            "action": action,
            "table_cible": table,
            "operation": operation,
            "details": json.dumps(details, ensure_ascii=False, default=str)[:4000],
        }
        supabase.table("historique_modifications").insert(payload).execute()
    except Exception:
        # L'audit ne doit jamais casser une opération métier.
        pass


# ============================================================
# 6. PARCELLES / PÉRIMÈTRE
# ============================================================

@st.cache_data(ttl=15)
def load_accessible_champs() -> pd.DataFrame:
    try:
        q = supabase.table("champs").select("*")
        if not is_admin():
            email = user_email()
            if not email:
                return pd.DataFrame()
            # Compatibilité : createur_email reste le propriétaire technique
            # de la parcelle dans le modèle actuel.
            q = q.eq("createur_email", email)
        return pd.DataFrame(q.execute().data or [])
    except Exception:
        return pd.DataFrame()


def accessible_champ_ids() -> List[int]:
    df = load_accessible_champs()
    if df.empty or "id" not in df.columns:
        return []
    return (
        pd.to_numeric(df["id"], errors="coerce")
        .dropna().astype(int).tolist()
    )


def champ_access(champ_id: Any) -> bool:
    if is_admin():
        return True
    try:
        return int(champ_id) in set(accessible_champ_ids())
    except Exception:
        return False


def selected_champ() -> Tuple[Optional[int], str, pd.Series]:
    df = load_accessible_champs()
    if df.empty or "id" not in df.columns or "nom" not in df.columns:
        return None, "Aucune parcelle", pd.Series(dtype=object)

    names = df["nom"].astype(str).tolist()
    name = st.selectbox("📍 Parcelle active", names, key="active_champ")
    row = df[df["nom"].astype(str) == name].iloc[0]
    return row.get("id"), name, row


# ============================================================
# 7. SUPABASE STORAGE — CORRECTION DU PROBLÈME DES PHOTOS
# ============================================================

def safe_filename(name: str) -> str:
    name = os.path.basename(name or "fichier")
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    return name[:180]


def storage_upload(uploaded_file, category: str, entity_id: Any = "") -> Dict[str, str]:
    """
    Upload réel dans Supabase Storage.
    On ne stocke PLUS un chemin local comme référence métier.
    La table reçoit storage_path, storage_bucket et original_name.
    """
    if uploaded_file is None:
        return {}

    try:
        raw = uploaded_file.getvalue()
        original = safe_filename(uploaded_file.name)
        stamp = datetime.now().strftime("%Y%m%d/%H%M%S_%f")
        uid = hashlib.sha256(raw).hexdigest()[:12]
        path = f"{category}/{entity_id or 'general'}/{stamp}_{uid}_{original}"

        content_type = getattr(uploaded_file, "type", None) or "application/octet-stream"

        supabase.storage.from_(SUPABASE_BUCKET).upload(
            path,
            raw,
            {"content-type": content_type, "upsert": "false"},
        )
        return {
            "storage_bucket": SUPABASE_BUCKET,
            "storage_path": path,
            "original_name": original,
            "mime_type": content_type,
            "size_bytes": str(len(raw)),
        }
    except Exception as exc:
        st.error(
            "❌ Upload Supabase Storage impossible. "
            f"Vérifiez le bucket '{SUPABASE_BUCKET}' et les policies Storage. "
            f"Détail : {db_error_message(exc)}"
        )
        return {}


def storage_download(bucket: str, path: str) -> Optional[bytes]:
    if not path:
        return None
    try:
        return supabase.storage.from_(bucket or SUPABASE_BUCKET).download(path)
    except Exception:
        return None


def storage_signed_url(bucket: str, path: str, expires: int = 3600) -> str:
    if not path:
        return ""
    try:
        result = supabase.storage.from_(bucket or SUPABASE_BUCKET).create_signed_url(
            path, expires
        )
        if isinstance(result, dict):
            return result.get("signedURL") or result.get("signedUrl") or ""
        return ""
    except Exception:
        return ""


def render_attachment(
    row: pd.Series,
    path_fields: Tuple[str, ...] = ("storage_path", "piece_jointe_path", "photo_path"),
):
    path = ""
    for field in path_fields:
        val = row.get(field, "")
        if val and isinstance(val, str):
            path = val
            break
    if not path:
        return

    bucket = str(row.get("storage_bucket", SUPABASE_BUCKET))
    name = str(
        row.get("original_name")
        or row.get("piece_jointe_nom")
        or row.get("photo_nom")
        or row.get("facture_nom")
        or Path(path).name
    )
    mime = str(row.get("mime_type", "")).lower()

    if path.startswith("http"):
        url = path
    else:
        url = storage_signed_url(bucket, path)

    if url and (mime.startswith("image/") or name.lower().endswith(
        (".png", ".jpg", ".jpeg", ".webp")
    )):
        st.image(url, caption=name, width=380)
        return

    if url:
        st.link_button(f"📎 Ouvrir {name}", url, use_container_width=False)


def local_or_storage_bytes(row: pd.Series) -> Optional[bytes]:
    path = str(row.get("storage_path", "") or "")
    if path:
        return storage_download(
            str(row.get("storage_bucket", SUPABASE_BUCKET)), path
        )
    old_path = str(
        row.get("piece_jointe_path")
        or row.get("photo_path")
        or row.get("fichier_path")
        or ""
    )
    if old_path and os.path.exists(old_path):
        try:
            return Path(old_path).read_bytes()
        except Exception:
            return None
    return None


# ============================================================
# 8. OUTILS DATA / SÉCURITÉ DES RAPPORTS
# ============================================================

SENSITIVE_COLUMNS = {
    "id", "uuid", "user_id", "utilisateur_id", "champ_id",
    "createur_email", "email", "auteur_email", "user_email",
    "technicien_email", "responsable_email", "employe_email",
    "password", "mot_de_passe", "password_hash", "token",
    "secret", "access_token", "refresh_token", "modules_autorises",
    "permissions", "session", "ip", "ip_address", "security",
    "securite",
}


def clean_report_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()
    keep = [
        c for c in df.columns
        if str(c).strip().lower() not in SENSITIVE_COLUMNS
    ]
    return df[keep].copy()


def filter_by_champ(df: pd.DataFrame, champ_id: Any) -> pd.DataFrame:
    if df is None or df.empty or champ_id is None:
        return pd.DataFrame()
    if "champ_id" not in df.columns:
        return pd.DataFrame()
    try:
        return df[
            pd.to_numeric(df["champ_id"], errors="coerce")
            == int(champ_id)
        ].copy()
    except Exception:
        return df[df["champ_id"].astype(str) == str(champ_id)].copy()


def nonempty(v: Any) -> bool:
    if v is None:
        return False
    if pd.isna(v) if not isinstance(v, (list, dict)) else False:
        return False
    return str(v).strip().lower() not in ("", "none", "nan", "nat")


def df_records(df: pd.DataFrame, max_rows: int = 100) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    work = df.head(max_rows).copy()
    return json.loads(work.to_json(orient="records", date_format="iso"))


def safe_num(df: pd.DataFrame, col: str) -> float:
    if df is None or df.empty or col not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())


# ============================================================
# 9. IA AGRICOLE — ANALYSE MULTISOURCE + VISION
# ============================================================

AGRI_SYSTEM_PROMPT = """
Tu es YAM AGRI-EXPERT, un copilote agricole professionnel destiné à des
propriétaires, gestionnaires, techniciens supérieurs, techniciens, stagiaires
et administrateurs d'exploitation.

Ta mission est d'analyser les données de l'exploitation avec une logique
agronomique, opérationnelle, économique et de traçabilité.

Tu dois :
1. distinguer clairement les faits saisis des hypothèses;
2. détecter incohérences, données manquantes importantes et anomalies;
3. interpréter les tendances (travaux, eau, pluie, incidents, récoltes, coûts,
   intrants, temps de travail, matériel);
4. proposer des actions concrètes, hiérarchisées par urgence;
5. expliquer les risques et les contrôles à effectuer;
6. tenir compte de la parcelle, de la culture, de la date et des mesures;
7. pour une photo, décrire uniquement ce qui est réellement visible et signaler
   les limites de l'analyse visuelle;
8. ne jamais inventer une mesure, une maladie ou un diagnostic certain;
9. pour les traitements phytosanitaires, recommander de confirmer le diagnostic,
   l'étiquette homologuée, la dose autorisée et la réglementation locale;
10. adapter le niveau de langage au rôle de l'utilisateur.

Format recommandé :
- Synthèse exécutive
- Constats factuels
- Anomalies / points de vigilance
- Analyse agronomique
- Priorités 24–48 h
- Actions 7 jours
- Suivi à documenter
- Avis YAM AGRI-EXPERT
- Niveau de confiance
"""

@st.cache_resource
def init_openai():
    key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    if not key or OpenAI is None:
        return None
    return OpenAI(api_key=key)


def ai_model() -> str:
    return st.secrets.get(
        "OPENAI_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
    )


def ai_available() -> bool:
    return init_openai() is not None


def build_ai_context(champ_id: Any, champ_name: str) -> Dict[str, Any]:
    tables = [
        "pointage", "taches", "recoltes", "depenses", "intrants",
        "materiel", "pluviometrie", "incidents", "tracabilite",
        "irrigation", "alertes_meteo",
    ]
    context = {
        "application": APP_NAME,
        "date_analyse": datetime.now().isoformat(timespec="seconds"),
        "utilisateur_role": user_role(),
        "parcelle": {},
        "donnees": {},
    }

    champs = load_accessible_champs()
    if not champs.empty and "id" in champs.columns:
        r = champs[pd.to_numeric(champs["id"], errors="coerce") == int(champ_id)]
        if not r.empty:
            context["parcelle"] = clean_report_df(r).iloc[0].to_dict()

    for table in tables:
        df = filter_by_champ(load_table(table), champ_id)
        context["donnees"][table] = df_records(clean_report_df(df), 80)

    # KPI utiles, calculés à partir des données existantes.
    dep = filter_by_champ(load_table("depenses"), champ_id)
    rec = filter_by_champ(load_table("recoltes"), champ_id)
    plu = filter_by_champ(load_table("pluviometrie"), champ_id)
    irr = filter_by_champ(load_table("irrigation"), champ_id)
    context["indicateurs"] = {
        "depenses_fcfa": safe_num(dep, "montant"),
        "recolte_kg": safe_num(rec, "quantite_kg"),
        "valeur_recoltes_fcfa": (
            float(
                (
                    pd.to_numeric(rec.get("quantite_kg", pd.Series(dtype=float)), errors="coerce").fillna(0)
                    * pd.to_numeric(rec.get("prix_unitaire", pd.Series(dtype=float)), errors="coerce").fillna(0)
                ).sum()
            )
            if not rec.empty else 0.0
        ),
        "pluie_mm": safe_num(plu, "pluie_mm"),
        "eau_m3": safe_num(irr, "volume_eau_m3"),
    }
    return context


def ai_analyse_agricole(
    champ_id: Any,
    champ_name: str,
    question: str = "",
    image_rows: Optional[List[pd.Series]] = None,
) -> str:
    client = init_openai()
    if client is None:
        return (
            "IA non activée : configurez OPENAI_API_KEY dans les secrets "
            "Streamlit. Les données restent utilisables sans l'IA."
        )

    context = build_ai_context(champ_id, champ_name)
    question = question.strip() or (
        "Fais un diagnostic global de cette parcelle et donne les priorités "
        "opérationnelles immédiates, les risques, les incohérences et les "
        "actions de suivi."
    )

    content = [
        {
            "type": "input_text",
            "text": (
                f"Rôle utilisateur : {user_role()}\n"
                f"Parcelle : {champ_name}\n"
                f"Question : {question}\n\n"
                "DONNÉES YAM (JSON) :\n"
                + json.dumps(context, ensure_ascii=False, default=str)
            ),
        }
    ]

    # Vision : jusqu'à 4 images pertinentes, téléchargées depuis Storage.
    for row in (image_rows or [])[:4]:
        raw = local_or_storage_bytes(row)
        if not raw:
            continue
        mime = str(row.get("mime_type", "image/jpeg"))
        if not mime.startswith("image/"):
            continue
        import base64
        encoded = base64.b64encode(raw).decode("utf-8")
        content.append({
            "type": "input_image",
            "image_url": f"data:{mime};base64,{encoded}",
        })

    try:
        response = client.responses.create(
            model=ai_model(),
            instructions=AGRI_SYSTEM_PROMPT,
            input=[{"role": "user", "content": content}],
        )
        return getattr(response, "output_text", "") or str(response)
    except Exception as exc:
        return f"Erreur IA : {db_error_message(exc)}"


# ============================================================
# 10. RAPPORT PDF PROFESSIONNEL
# ============================================================

def pdf_styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "YTitle", parent=ss["Heading1"], fontName="Helvetica-Bold",
            fontSize=19, leading=23, alignment=1,
            textColor=colors.HexColor("#123b28"), spaceAfter=8
        ),
        "subtitle": ParagraphStyle(
            "YSub", parent=ss["Heading2"], fontName="Helvetica-Bold",
            fontSize=11, leading=14, textColor=colors.HexColor("#0e6b3b"),
            spaceBefore=10, spaceAfter=6
        ),
        "normal": ParagraphStyle(
            "YNorm", parent=ss["Normal"], fontName="Helvetica",
            fontSize=8.4, leading=11, textColor=colors.HexColor("#26382d")
        ),
        "small": ParagraphStyle(
            "YSmall", parent=ss["Normal"], fontName="Helvetica",
            fontSize=7, leading=9, textColor=colors.HexColor("#5b6f63")
        ),
        "field": ParagraphStyle(
            "YField", parent=ss["Normal"], fontName="Helvetica-Bold",
            fontSize=7.4, leading=9, textColor=colors.HexColor("#123b28")
        ),
        "ai": ParagraphStyle(
            "YAI", parent=ss["Normal"], fontName="Helvetica",
            fontSize=8.2, leading=11, textColor=colors.HexColor("#244d34")
        ),
    }


def esc(text: Any) -> str:
    if text is None:
        return ""
    s = str(text)
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace("\n", "<br/>")
    )


def add_clean_df(elements, title: str, df: pd.DataFrame, styles, max_rows: int = 80):
    work = clean_report_df(df)
    # Important : on n'affiche aucune section vide.
    if work.empty:
        return

    elements.append(Paragraph(esc(title), styles["subtitle"]))
    for idx, row in work.head(max_rows).iterrows():
        fields = []
        for col in work.columns:
            val = row.get(col, "")
            if not nonempty(val):
                continue
            fields.append([
                Paragraph(esc(col), styles["field"]),
                Paragraph(esc(val), styles["normal"]),
            ])
        if not fields:
            continue
        table = Table(fields, colWidths=[145, 355], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(0,-1), colors.HexColor("#eef6f0")),
            ("GRID", (0,0),(-1,-1), .35, colors.HexColor("#d7e7dc")),
            ("VALIGN", (0,0),(-1,-1), "TOP"),
            ("LEFTPADDING",(0,0),(-1,-1),5),
            ("RIGHTPADDING",(0,0),(-1,-1),5),
            ("TOPPADDING",(0,0),(-1,-1),4),
            ("BOTTOMPADDING",(0,0),(-1,-1),4),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 5))


def add_storage_images(elements, rows: List[pd.Series], styles, max_images=8):
    valid = []
    for row in rows:
        mime = str(row.get("mime_type", "")).lower()
        name = str(
            row.get("original_name")
            or row.get("photo_nom")
            or row.get("piece_jointe_nom")
            or row.get("facture_nom")
            or ""
        )
        if mime.startswith("image/") or name.lower().endswith(
            (".png",".jpg",".jpeg",".webp")
        ):
            valid.append(row)

    if not valid:
        return

    elements.append(Paragraph("ÉVIDENCES PHOTOGRAPHIQUES", styles["subtitle"]))
    for row in valid[:max_images]:
        raw = local_or_storage_bytes(row)
        if not raw:
            continue
        try:
            img_reader = ImageReader(io.BytesIO(raw))
            iw, ih = img_reader.getSize()
            scale = min(490 / float(iw), 285 / float(ih), 1.0)
            elements.append(
                Paragraph(
                    f"<b>Photo :</b> {esc(row.get('original_name','Évidence'))}",
                    styles["normal"]
                )
            )
            elements.append(
                RLImage(io.BytesIO(raw), width=iw*scale, height=ih*scale)
            )
            elements.append(Spacer(1, 8))
        except Exception:
            continue


def generate_pdf_report(
    champ_id: Any,
    champ_name: str,
    report_date: date,
    ai_text: str = "",
) -> bytes:
    buffer = io.BytesIO()
    styles = pdf_styles()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=28, leftMargin=28, topMargin=30, bottomMargin=35
    )

    champs = load_accessible_champs()
    champ_info = pd.DataFrame()
    if not champs.empty and "id" in champs.columns:
        tmp = champs[
            pd.to_numeric(champs["id"], errors="coerce") == int(champ_id)
        ]
        if not tmp.empty:
            champ_info = tmp.iloc[[0]]

    table_titles = [
        ("pointage", "TEMPS & ACTIVITÉS HUMAINES"),
        ("taches", "TRAVAUX & PLANNING"),
        ("recoltes", "RÉCOLTES & RENDEMENTS"),
        ("depenses", "DÉPENSES & ACHATS"),
        ("intrants", "INTRANTS & STOCKS"),
        ("materiel", "MATÉRIEL & MAINTENANCE"),
        ("pluviometrie", "PLUVIOMÉTRIE"),
        ("incidents", "INCIDENTS & OBSERVATIONS"),
        ("tracabilite", "TRAÇABILITÉ & LOTS"),
        ("irrigation", "IRRIGATION & EAU"),
        ("alertes_meteo", "RISQUES & MÉTÉO"),
    ]

    collected = {}
    for table, title in table_titles:
        collected[table] = filter_by_champ(load_table(table), champ_id)

    # Évidences venant des tables métier.
    evidence_rows = []
    for table in ["depenses","intrants","materiel","incidents","tracabilite"]:
        df = collected.get(table, pd.DataFrame())
        if not df.empty:
            for _, row in df.iterrows():
                if local_or_storage_bytes(row):
                    evidence_rows.append(row)

    dep = collected["depenses"]
    rec = collected["recoltes"]
    total_dep = safe_num(dep, "montant")
    total_kg = safe_num(rec, "quantite_kg")
    value = (
        float(
            (
                pd.to_numeric(rec.get("quantite_kg", pd.Series(dtype=float)), errors="coerce").fillna(0)
                * pd.to_numeric(rec.get("prix_unitaire", pd.Series(dtype=float)), errors="coerce").fillna(0)
            ).sum()
        )
        if not rec.empty else 0.0
    )
    margin = value - total_dep

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d7e7dc"))
        canvas.line(28, 25, A4[0]-28, 25)
        canvas.setFont("Helvetica-Bold", 7.2)
        canvas.setFillColor(colors.HexColor("#0e6b3b"))
        canvas.drawString(28, 13, "YouAgronoMe (YAM) • Pilotage • Traçabilité • Décision")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawRightString(A4[0]-28, 13, f"Page {doc_obj.page}")
        canvas.restoreState()

    el = []
    el.append(Spacer(1, 8))
    el.append(Paragraph("YouAgronoMe (YAM)", styles["title"]))
    el.append(Paragraph(
        "RAPPORT PROFESSIONNEL DE SUIVI AGRICOLE",
        ParagraphStyle(
            "cover", parent=styles["subtitle"], alignment=1,
            fontSize=11, spaceBefore=0
        )
    ))
    el.append(Paragraph(
        f"PARCELLE : <b>{esc(champ_name).upper()}</b>",
        ParagraphStyle("cover2", parent=styles["subtitle"], alignment=1)
    ))

    kpi = Table(
        [[
            "Récolte", "Dépenses", "Valeur récoltes", "Marge estimative",
            "Incidents"
        ],[
            f"{total_kg:,.2f} kg",
            f"{total_dep:,.0f} FCFA",
            f"{value:,.0f} FCFA",
            f"{margin:,.0f} FCFA",
            str(len(collected["incidents"])),
        ]],
        colWidths=[100]*5
    )
    kpi.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#123b28")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,1),(-1,1),colors.HexColor("#f3faf5")),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTNAME",(0,1),(-1,1),"Helvetica-Bold"),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("GRID",(0,0),(-1,-1),.5,colors.HexColor("#cbded0")),
        ("FONTSIZE",(0,0),(-1,-1),7.5),
        ("TOPPADDING",(0,0),(-1,-1),6),
        ("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    el.append(kpi)
    el.append(Spacer(1, 10))
    el.append(Paragraph(
        f"Édité le {report_date.strftime('%d/%m/%Y')} à "
        f"{datetime.now().strftime('%H:%M')}. "
        "Seules les informations réellement renseignées sont présentées.",
        styles["small"]
    ))

    add_clean_df(el, "1. IDENTIFICATION DE LA PARCELLE", champ_info, styles)

    for table, title in table_titles:
        add_clean_df(el, title, collected[table], styles)

    # IA : uniquement si elle a effectivement produit un avis.
    if ai_text.strip():
        el.append(PageBreak())
        el.append(Paragraph("AVIS YAM AGRI-EXPERT", styles["subtitle"]))
        for block in ai_text.split("\n"):
            if block.strip():
                el.append(Paragraph(esc(block), styles["ai"]))
                el.append(Spacer(1, 3))

    add_storage_images(el, evidence_rows, styles)

    # Validation/signatures.
    el.append(Paragraph("VALIDATION PROFESSIONNELLE", styles["subtitle"]))
    sig = Table(
        [[
            "RESPONSABLE DU SUIVI",
            "SUPERVISION / PROPRIÉTAIRE"
        ],[
            "Nom : ______________________\nSignature : __________________\nDate : ____ / ____ / ______",
            "Nom : ______________________\nSignature : __________________\nDate : ____ / ____ / ______"
        ]],
        colWidths=[250,250], rowHeights=[22,85]
    )
    sig.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dff2e6")),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("GRID",(0,0),(-1,-1),.6,colors.HexColor("#9ca3af")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("FONTSIZE",(0,0),(-1,-1),8.5),
        ("TOPPADDING",(0,1),(-1,-1),8),
    ]))
    el.append(sig)

    doc.build(el, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


# ============================================================
# 11. NAVIGATION
# ============================================================

u = current_user()
prenom = u.get("prenom", "Utilisateur")
nom = u.get("nom", "")
role = user_role()

st.markdown(
    f"""
<div class="main-header">
<div>
<div class="brand-title">🌾 YouAgronoMe (YAM)</div>
<div class="brand-subtitle">Centralisation agricole intelligente · données · terrain · décision · traçabilité</div>
</div>
<div class="user-badge">👤 {prenom} {nom} · {role}</div>
</div>
""",
    unsafe_allow_html=True,
)

accessible = allowed_modules()
if not accessible:
    st.error("Aucun module n'est autorisé pour ce compte.")
    st.stop()

if "selected_menu" not in st.session_state:
    st.session_state.selected_menu = accessible[0]
if st.session_state.selected_menu not in accessible:
    st.session_state.selected_menu = accessible[0]

# Navigation en groupes.
groups = {
    "🏠 PILOTAGE": [
        "📊 Tableau de Bord", "🧭 Centre Opérations", "🤖 IA Agricole",
        "📑 Rapports Professionnels"
    ],
    "🌱 EXPLOITATION": [
        "🌱 Cartographie & Parcelles", "📅 Planning & Travaux",
        "🌾 Récoltes & Rendements", "🌧️ Pluviométrie",
        "💧 Irrigation & Eau", "🌤️ Risques & Météo"
    ],
    "👷 TERRAIN": [
        "⏰ Temps & Pointage", "⚠️ Incidents & Observations",
        "🏷️ Traçabilité & Lots", "📦 Intrants & Stocks",
        "🚜 Matériel & Maintenance"
    ],
    "💼 GESTION": [
        "💰 Finances & Coûts", "📈 Rentabilité & ROI",
        "💬 Collaboration & Workspace"
    ],
    "🔐 ADMIN": [
        "🔐 Liste Blanche & Administration", "📜 Journal d'Audit"
    ],
}

tabs = st.tabs([g for g in groups])
for tab, group_name in zip(tabs, groups):
    with tab:
        items = [x for x in groups[group_name] if x in accessible]
        if not items:
            st.caption("Aucun module autorisé.")
            continue
        cols = st.columns(min(5, len(items)))
        for i, item in enumerate(items):
            with cols[i % len(cols)]:
                if st.button(item, key=f"nav_{group_name}_{i}", use_container_width=True):
                    st.session_state.selected_menu = item
                    st.rerun()

menu = st.session_state.selected_menu

c1, c2, c3 = st.columns([5,1,1])
with c1:
    st.caption(
        f"Module actif : **{menu}** · "
        f"Dernière synchronisation : **{st.session_state.get('last_sync','À l’ouverture')}**"
    )
with c2:
    if st.button("🔄 Synchroniser", use_container_width=True):
        clear_caches()
        st.session_state.last_sync = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        st.rerun()
with c3:
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.clear()
        st.rerun()


# ============================================================
# 12. SÉLECTION DE PARCELLE
# ============================================================

db_champs = load_accessible_champs()
champ_id = None
champ_name = "Aucune parcelle"
champ_row = pd.Series(dtype=object)

if menu != "🌱 Cartographie & Parcelles" and menu not in (
    "🔐 Liste Blanche & Administration", "📜 Journal d'Audit"
):
    if not db_champs.empty:
        champ_id, champ_name, champ_row = selected_champ()
    else:
        st.info("Aucune parcelle accessible. Créez-en une dans Cartographie & Parcelles.")


# ============================================================
# 13. TABLEAU DE BORD
# ============================================================

if menu == "📊 Tableau de Bord":
    if not require_module(menu):
        st.stop()

    st.title("📊 Tableau de Bord — Pilotage de l'exploitation")
    champs = load_accessible_champs()
    rec = load_table("recoltes")
    dep = load_table("depenses")
    inc = load_table("incidents")
    taches = load_table("taches")

    if not is_admin():
        ids = accessible_champ_ids()
        rec = filter_by_champ(rec, None) if rec.empty else (
            rec[rec["champ_id"].isin(ids)] if "champ_id" in rec.columns else pd.DataFrame()
        )
        dep = dep[dep["champ_id"].isin(ids)] if not dep.empty and "champ_id" in dep.columns else pd.DataFrame()
        inc = inc[inc["champ_id"].isin(ids)] if not inc.empty and "champ_id" in inc.columns else pd.DataFrame()
        taches = taches[taches["champ_id"].isin(ids)] if not taches.empty and "champ_id" in taches.columns else pd.DataFrame()

    surface = safe_num(champs, "superficie_ha")
    kg = safe_num(rec, "quantite_kg")
    couts = safe_num(dep, "montant")
    valeur = (
        float((
            pd.to_numeric(rec.get("quantite_kg", pd.Series(dtype=float)), errors="coerce").fillna(0)
            * pd.to_numeric(rec.get("prix_unitaire", pd.Series(dtype=float)), errors="coerce").fillna(0)
        ).sum()) if not rec.empty else 0
    )

    a,b,c,d,e = st.columns(5)
    a.metric("🌱 Parcelles", len(champs))
    b.metric("📐 Surface", f"{surface:.2f} ha")
    c.metric("🌾 Récolte", f"{kg/1000:.2f} t")
    d.metric("💰 Coûts", f"{couts:,.0f} FCFA")
    e.metric("📈 Valeur récoltes", f"{valeur:,.0f} FCFA")

    st.markdown("### 🔎 Vigilance opérationnelle")
    incidents_ouverts = len(inc)
    if incidents_ouverts:
        st.markdown(
            f'<div class="danger-box"><b>{incidents_ouverts} incident(s)</b> '
            "sont enregistrés dans votre périmètre. Consultez le module Incidents "
            "et demandez une analyse IA si nécessaire.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.success("Aucun incident enregistré dans le périmètre courant.")

    if not champs.empty:
        cols = [c for c in ["nom","superficie_ha","culture_actuelle","statut"] if c in champs.columns]
        st.dataframe(champs[cols], use_container_width=True, hide_index=True)


# ============================================================
# 14. CENTRE OPÉRATIONS
# ============================================================

elif menu == "🧭 Centre Opérations":
    st.title("🧭 Centre Opérations — vue technicien / gestionnaire")
    if champ_id is None:
        st.info("Sélectionnez une parcelle.")
    else:
        tables = {
            "Travaux": filter_by_champ(load_table("taches"), champ_id),
            "Incidents": filter_by_champ(load_table("incidents"), champ_id),
            "Récoltes": filter_by_champ(load_table("recoltes"), champ_id),
            "Irrigation": filter_by_champ(load_table("irrigation"), champ_id),
            "Pluie": filter_by_champ(load_table("pluviometrie"), champ_id),
        }
        a,b,c,d,e = st.columns(5)
        a.metric("Travaux", len(tables["Travaux"]))
        b.metric("Incidents", len(tables["Incidents"]))
        c.metric("Récoltes", len(tables["Récoltes"]))
        d.metric("Irrigations", len(tables["Irrigation"]))
        e.metric("Relevés pluie", len(tables["Pluie"]))

        st.markdown("### 📌 Derniers événements")
        rows = []
        for label, df in tables.items():
            if not df.empty:
                row = df.iloc[-1].to_dict()
                row["module"] = label
                rows.append(row)
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("Aucun événement renseigné.")


# ============================================================
# 15. CARTOGRAPHIE & PARCELLES
# ============================================================

elif menu == "🌱 Cartographie & Parcelles":
    st.title("🌱 Cartographie & Parcelles")
    if not require_module(menu):
        st.stop()

    if "map_lat" not in st.session_state:
        st.session_state.map_lat = 14.6937
    if "map_lon" not in st.session_state:
        st.session_state.map_lon = -17.4441

    col1,col2 = st.columns([3,1])
    with col1:
        search = st.text_input(
            "🔍 Localité / village / zone",
            placeholder="Ex. Bambey, Touba, Diourbel..."
        )
        if search:
            try:
                from geopy.geocoders import Nominatim
                loc = Nominatim(user_agent="yam_agri").geocode(search + ", Senegal")
                if loc:
                    st.session_state.map_lat = loc.latitude
                    st.session_state.map_lon = loc.longitude
                    st.success(f"Position : {loc.address}")
            except Exception:
                st.info("Installez geopy ou saisissez directement les coordonnées.")
    with col2:
        st.metric("Parcelles accessibles", len(db_champs))

    m = folium.Map(
        location=[st.session_state.map_lat, st.session_state.map_lon],
        zoom_start=13,
        tiles="OpenStreetMap",
    )
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        attr="Google",
        name="Satellite",
        overlay=False,
    ).add_to(m)

    if not db_champs.empty and "latitude" in db_champs.columns and "longitude" in db_champs.columns:
        for _, r in db_champs.iterrows():
            try:
                folium.Marker(
                    [float(r["latitude"]), float(r["longitude"])],
                    popup=(
                        f"<b>{r.get('nom','')}</b><br>"
                        f"Culture: {r.get('culture_actuelle','')}<br>"
                        f"Surface: {r.get('superficie_ha','')} ha"
                    ),
                ).add_to(m)
            except Exception:
                continue

    Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": False, "polygon": True, "rectangle": True,
            "circle": False, "marker": True, "circlemarker": False
        },
        edit_options={"poly": {"allowIntersection": False}, "edit": True, "remove": True},
    ).add_to(m)

    output = st_folium(m, width="100%", height=470, returned_objects=["all_drawings"])

    surface_calc = 0.0
    lat_calc = float(st.session_state.map_lat)
    lon_calc = float(st.session_state.map_lon)

    if output and output.get("all_drawings"):
        drawings = output["all_drawings"]
        if drawings:
            geom = drawings[-1].get("geometry", {})
            coords = geom.get("coordinates", [])
            if geom.get("type") in ("Polygon","Rectangle") and coords:
                ring = coords[0]
                lats = [p[1] for p in ring]
                lons = [p[0] for p in ring]
                lat_calc = round(sum(lats)/len(lats),6)
                lon_calc = round(sum(lons)/len(lons),6)
                mlat = math.radians(lat_calc)
                mx = 111139 * math.cos(mlat)
                my = 111139
                xy = [(p[0]*mx,p[1]*my) for p in ring]
                area = 0
                for i in range(len(xy)):
                    j=(i+1)%len(xy)
                    area += xy[i][0]*xy[j][1]-xy[j][0]*xy[i][1]
                surface_calc = round(abs(area)/2/10000,2)
                st.success(
                    f"Emprise : {surface_calc} ha · GPS {lat_calc}, {lon_calc}"
                )
            elif geom.get("type") == "Point" and len(coords) >= 2:
                lon_calc, lat_calc = round(coords[0],6), round(coords[1],6)

    st.markdown("### ➕ Nouvelle parcelle")
    with st.form("new_champ"):
        c1,c2 = st.columns(2)
        with c1:
            nom_p = st.text_input("Nom de la parcelle *")
            surf_p = st.number_input("Superficie (ha)", min_value=0.01, value=max(surface_calc,0.01))
            culture = st.text_input("Culture principale")
            statut = st.selectbox(
                "Statut", ["En préparation","Semé","En croissance","Prêt à récolter","En repos"]
            )
        with c2:
            lat = st.number_input("Latitude", value=float(lat_calc), format="%.6f")
            lon = st.number_input("Longitude", value=float(lon_calc), format="%.6f")
            pin = st.text_input("PIN parcellaire (optionnel)", type="password")

        if st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True):
            if nom_p.strip():
                db_insert(
                    "champs",
                    {
                        "nom": nom_p.strip(),
                        "superficie_ha": surf_p,
                        "latitude": lat,
                        "longitude": lon,
                        "culture_actuelle": culture.strip(),
                        "statut": statut,
                        "icone_lieu": "leaf",
                        "code_pin": pin.strip(),
                        "createur_email": user_email(),
                    },
                    f"Création parcelle {nom_p.strip()}",
                )
                st.success("Parcelle enregistrée dans Supabase.")
                st.rerun()
            else:
                st.warning("Le nom de parcelle est obligatoire.")

    st.markdown("### 🗂️ Parcelles accessibles")
    if not db_champs.empty:
        st.dataframe(
            db_champs[
                [c for c in ["id","nom","superficie_ha","culture_actuelle","statut","latitude","longitude"]
                 if c in db_champs.columns]
            ],
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# 16. TEMPS & POINTAGE
# ============================================================

elif menu == "⏰ Temps & Pointage":
    st.title("⏰ Temps & Pointage — heures réelles, présence et productivité")
    if not require_module(menu):
        st.stop()

    # Le nouveau schéma utilise time_entries. Fallback sur pointage si nécessaire.
    employees = load_table("employes")
    with st.form("time_entry"):
        c1,c2,c3 = st.columns(3)
        with c1:
            employee = st.selectbox(
                "Personne",
                employees["nom"].astype(str).tolist()
                if not employees.empty and "nom" in employees.columns
                else [f"{prenom} {nom}".strip() or user_email()]
            )
            work_date = st.date_input("Date", value=date.today())
        with c2:
            start = st.time_input("Heure d'arrivée", value=time(8,0))
            end = st.time_input("Heure de départ", value=time(17,0))
        with c3:
            pause = st.number_input("Pause (minutes)", min_value=0, max_value=480, value=60)
            task = st.text_input("Activité / chantier", placeholder="Semis, irrigation, entretien...")

        remark = st.text_area("Observation")
        submit = st.form_submit_button("💾 Enregistrer le temps", type="primary", use_container_width=True)

        if submit:
            start_dt = datetime.combine(work_date, start)
            end_dt = datetime.combine(work_date, end)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            minutes = max(0, int((end_dt-start_dt).total_seconds()/60) - int(pause))
            hours = round(minutes/60,2)
            payload = {
                "date": str(work_date),
                "employe_nom": employee,
                "champ_id": champ_id,
                "champ_nom": champ_name,
                "heure_arrivee": start.strftime("%H:%M"),
                "heure_depart": end.strftime("%H:%M"),
                "pause_minutes": pause,
                "heures_travaillees": hours,
                "tache_effectuee": task.strip(),
                "remarque": remark.strip(),
                "statut_presence": "Présent",
            }
            inserted = db_insert(
                "time_entries", payload,
                f"Pointage {employee} — {hours} h — {champ_name}"
            )
            if inserted:
                st.success(f"{hours:.2f} h enregistrées.")
                st.rerun()

    df_time = load_table("time_entries")
    if not df_time.empty:
        if champ_id is not None and "champ_id" in df_time.columns:
            df_time = filter_by_champ(df_time, champ_id)
        st.subheader("Historique")
        st.dataframe(
            df_time[
                [c for c in [
                    "date","employe_nom","heure_arrivee","heure_depart",
                    "pause_minutes","heures_travaillees","tache_effectuee","remarque"
                ] if c in df_time.columns]
            ],
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# 17. PLANNING & TRAVAUX
# ============================================================

elif menu == "📅 Planning & Travaux":
    st.title(f"📅 Planning & Travaux — {champ_name}")
    if champ_id is None:
        st.warning("Sélectionnez une parcelle.")
    else:
        with st.form("task_form"):
            c1,c2,c3 = st.columns(3)
            with c1:
                task_type = st.selectbox(
                    "Travail", [
                        "Préparation sol","Labour","Semis","Désherbage",
                        "Fertilisation","Traitement","Irrigation",
                        "Entretien","Récolte","Autre"
                    ]
                )
                planned = st.date_input("Date prévue", value=date.today())
            with c2:
                priority = st.selectbox("Priorité", ["Normale","Haute","Urgente"])
                duration = st.number_input("Durée prévue (h)", min_value=0.0, value=8.0)
            with c3:
                status = st.selectbox("Statut", ["Planifié","En cours","Terminé","Reporté","Annulé"])
                responsible = st.text_input("Responsable / équipe")
            note = st.text_area("Consignes techniques")
            if st.form_submit_button("💾 Planifier", type="primary", use_container_width=True):
                db_insert(
                    "taches",
                    {
                        "champ_id": champ_id,
                        "type_travail": task_type,
                        "date_tache": str(planned),
                        "heures_travaillees": duration,
                        "statut": status,
                        "priorite": priority,
                        "responsable": responsible.strip(),
                        "consigne": note.strip(),
                    },
                    f"Planification {task_type} sur {champ_name}",
                )
                st.success("Travail planifié.")
                st.rerun()

        df = filter_by_champ(load_table("taches"), champ_id)
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================
# 18. RÉCOLTES
# ============================================================

elif menu == "🌾 Récoltes & Rendements":
    st.title(f"🌾 Récoltes & Rendements — {champ_name}")
    if champ_id is not None:
        with st.form("harvest_form"):
            c1,c2,c3 = st.columns(3)
            with c1:
                culture = st.text_input("Culture", value=str(champ_row.get("culture_actuelle","")))
                harvest_date = st.date_input("Date", value=date.today())
            with c2:
                quantity = st.number_input("Quantité récoltée (kg)", min_value=0.0)
                quality = st.selectbox("Qualité", ["Non renseignée","Bonne","Moyenne","À trier"])
            with c3:
                price = st.number_input("Prix unitaire (FCFA/kg)", min_value=0.0)
                lot = st.text_input("Lot associé (optionnel)")
            remark = st.text_area("Observation")
            if st.form_submit_button("💾 Enregistrer la récolte", type="primary", use_container_width=True):
                db_insert(
                    "recoltes",
                    {
                        "champ_id": champ_id,
                        "culture": culture.strip(),
                        "date_recolte": str(harvest_date),
                        "quantite_kg": quantity,
                        "prix_unitaire": price,
                        "qualite": quality,
                        "lot_code": lot.strip(),
                        "remarque": remark.strip(),
                    },
                    f"Récolte {culture} — {quantity} kg — {champ_name}",
                )
                st.success("Récolte enregistrée.")
                st.rerun()

        df = filter_by_champ(load_table("recoltes"), champ_id)
        if not df.empty:
            qty = safe_num(df, "quantite_kg")
            val = float((
                pd.to_numeric(df.get("quantite_kg",pd.Series(dtype=float)),errors="coerce").fillna(0)
                * pd.to_numeric(df.get("prix_unitaire",pd.Series(dtype=float)),errors="coerce").fillna(0)
            ).sum())
            a,b = st.columns(2)
            a.metric("Quantité cumulée", f"{qty:,.2f} kg")
            b.metric("Valeur estimative", f"{val:,.0f} FCFA")
            st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================
# 19. PLUVIOMÉTRIE
# ============================================================

elif menu == "🌧️ Pluviométrie":
    st.title(f"🌧️ Pluviométrie — {champ_name}")
    if champ_id is not None:
        with st.form("rain_form"):
            d = st.date_input("Date", value=date.today())
            mm = st.number_input("Pluie (mm)", min_value=0.0)
            method = st.text_input("Méthode / station / source")
            remark = st.text_area("Observation")
            if st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True):
                db_insert(
                    "pluviometrie",
                    {
                        "champ_id": champ_id,
                        "date": str(d),
                        "pluie_mm": mm,
                        "source": method.strip(),
                        "remarque": remark.strip(),
                    },
                    f"Pluie {mm} mm — {champ_name}",
                )
                st.success("Relevé enregistré.")
                st.rerun()
        df = filter_by_champ(load_table("pluviometrie"), champ_id)
        if not df.empty:
            st.metric("Pluie cumulée enregistrée", f"{safe_num(df,'pluie_mm'):.1f} mm")
            st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================
# 20. IRRIGATION
# ============================================================

elif menu == "💧 Irrigation & Eau":
    st.title(f"💧 Irrigation & Eau — {champ_name}")
    if champ_id is not None:
        with st.form("irrigation_form"):
            c1,c2,c3 = st.columns(3)
            with c1:
                d = st.date_input("Date", value=date.today())
                volume = st.number_input("Volume d'eau (m³)", min_value=0.0)
            with c2:
                method = st.selectbox("Méthode", ["Goutte-à-goutte","Aspersion","Gravitaire","Autre"])
                duration = st.number_input("Durée (heures)", min_value=0.0)
            with c3:
                source = st.text_input("Source d'eau")
                operator = st.text_input("Opérateur")
            remark = st.text_area("Observation")
            if st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True):
                db_insert(
                    "irrigation",
                    {
                        "champ_id": champ_id,
                        "date": str(d),
                        "volume_eau_m3": volume,
                        "methode": method,
                        "duree_heures": duration,
                        "source_eau": source.strip(),
                        "operateur": operator.strip(),
                        "remarque": remark.strip(),
                    },
                    f"Irrigation {volume} m³ — {champ_name}",
                )
                st.success("Irrigation enregistrée.")
                st.rerun()
        df = filter_by_champ(load_table("irrigation"), champ_id)
        if not df.empty:
            st.metric("Eau cumulée", f"{safe_num(df,'volume_eau_m3'):,.1f} m³")
            st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================
# 21. INCIDENTS & OBSERVATIONS + PHOTOS STORAGE
# ============================================================

elif menu == "⚠️ Incidents & Observations":
    st.title(f"⚠️ Incidents & Observations — {champ_name}")
    if champ_id is not None:
        with st.form("incident_form"):
            c1,c2 = st.columns(2)
            with c1:
                d = st.date_input("Date", value=date.today())
                category = st.selectbox(
                    "Catégorie",
                    ["Maladie","Ravageur","Dégât climatique","Irrigation",
                     "Matériel","Sécurité","Travail","Autre"]
                )
                severity = st.selectbox("Gravité", ["Faible","Modérée","Élevée","Critique"])
            with c2:
                status = st.selectbox("Statut", ["Ouvert","En analyse","Action engagée","Résolu"])
                action = st.text_area("Action immédiate / recommandation")
                photo = st.file_uploader(
                    "📷 Photo d'évidence",
                    type=["png","jpg","jpeg","webp"],
                    key="incident_photo"
                )
            description = st.text_area("Description détaillée *")
            if st.form_submit_button("🚨 Déclarer l'incident", type="primary", use_container_width=True):
                if not description.strip():
                    st.warning("Décrivez l'incident.")
                else:
                    # 1) créer le record pour obtenir l'id si disponible
                    rec = db_insert(
                        "incidents",
                        {
                            "champ_id": champ_id,
                            "date": str(d),
                            "categorie": category,
                            "description": description.strip(),
                            "gravite": severity,
                            "statut": status,
                            "action": action.strip(),
                        },
                        f"Incident {category} — {severity} — {champ_name}",
                    )
                    if rec and photo is not None:
                        meta = storage_upload(photo, "incidents", rec.get("id", "new"))
                        if meta:
                            db_update(
                                "incidents",
                                "id", rec.get("id"),
                                meta,
                                f"Photo incident ajoutée — {champ_name}"
                            )
                    st.success("Incident enregistré avec l'évidence dans Supabase Storage.")
                    st.rerun()

        df = filter_by_champ(load_table("incidents"), champ_id)
        if not df.empty:
            for _, row in df.iloc[::-1].iterrows():
                with st.container(border=True):
                    st.markdown(
                        f"**{row.get('date','')} · {row.get('categorie','')} · "
                        f"{row.get('gravite','')} · {row.get('statut','')}**"
                    )
                    st.write(row.get("description",""))
                    if nonempty(row.get("action","")):
                        st.caption(f"Action : {row.get('action')}")
                    render_attachment(row)


# ============================================================
# 22. TRAÇABILITÉ
# ============================================================

elif menu == "🏷️ Traçabilité & Lots":
    st.title(f"🏷️ Traçabilité & Lots — {champ_name}")
    if champ_id is not None:
        with st.form("lot_form"):
            c1,c2 = st.columns(2)
            with c1:
                lot = st.text_input("Code du lot *")
                culture = st.text_input("Culture")
                standard = st.text_input("Norme / certification")
                harvest_date = st.date_input("Date de production / récolte", value=date.today())
            with c2:
                buyer = st.text_input("Acheteur / destination")
                supplier = st.text_input("Fournisseur / origine")
                quantity = st.number_input("Quantité", min_value=0.0)
                unit = st.text_input("Unité (kg, sac, caisse, L...)")
            proof = st.file_uploader(
                "📎 Preuve : certificat, étiquette, facture ou photo",
                type=["png","jpg","jpeg","webp","pdf"],
                key="lot_proof"
            )
            if st.form_submit_button("💾 Enregistrer le lot", type="primary", use_container_width=True):
                if lot.strip():
                    rec = db_insert(
                        "tracabilite",
                        {
                            "champ_id": champ_id,
                            "lot_code": lot.strip(),
                            "culture": culture.strip(),
                            "date_recolte": str(harvest_date),
                            "norme_certification": standard.strip(),
                            "acheteur": buyer.strip(),
                            "fournisseur": supplier.strip(),
                            "quantite_achetee": quantity,
                            "unite_quantite": unit.strip(),
                        },
                        f"Lot {lot.strip()} — {champ_name}",
                    )
                    if rec and proof is not None:
                        meta = storage_upload(proof, "tracabilite", rec.get("id","new"))
                        if meta:
                            db_update("tracabilite","id",rec.get("id"),meta,"Preuve lot ajoutée")
                    st.success("Lot enregistré.")
                    st.rerun()
                else:
                    st.warning("Le code du lot est obligatoire.")

        df = filter_by_champ(load_table("tracabilite"), champ_id)
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
            for _, row in df.iterrows():
                render_attachment(row)


# ============================================================
# 23. INTRANTS & STOCKS
# ============================================================

elif menu == "📦 Intrants & Stocks":
    st.title("📦 Intrants & Stocks — gestion achats, consommation et seuils")
    with st.form("stock_form"):
        c1,c2,c3 = st.columns(3)
        with c1:
            name = st.text_input("Intrant *")
            category = st.selectbox("Catégorie", ["Semence","Engrais","Phytosanitaire","Carburant","Autre"])
            unit = st.text_input("Unité")
        with c2:
            purchased = st.number_input("Quantité achetée", min_value=0.0)
            current = st.number_input("Stock actuel", min_value=0.0)
            threshold = st.number_input("Seuil d'alerte", min_value=0.0)
        with c3:
            price = st.number_input("Prix unitaire (FCFA)", min_value=0.0)
            supplier = st.text_input("Fournisseur")
            purchase_date = st.date_input("Date d'achat", value=date.today())
        proof = st.file_uploader(
            "📷 Facture / bon / photo",
            type=["png","jpg","jpeg","webp","pdf"],
            key="stock_proof"
        )
        if st.form_submit_button("💾 Ajouter / réceptionner", type="primary", use_container_width=True):
            if name.strip():
                rec = db_insert(
                    "intrants",
                    {
                        "nom": name.strip(),
                        "categorie": category,
                        "stock_actuel": current,
                        "seuil_alerte": threshold,
                        "unite": unit.strip(),
                        "quantite_achetee": purchased,
                        "prix_achat_unitaire": price,
                        "fournisseur": supplier.strip(),
                        "date_achat": str(purchase_date),
                    },
                    f"Intrant {name.strip()} — réception {purchased}",
                )
                if rec and proof is not None:
                    meta = storage_upload(proof, "intrants", rec.get("id","new"))
                    if meta:
                        db_update("intrants","id",rec.get("id"),meta,"Justificatif intrant ajouté")
                st.success("Stock enregistré.")
                st.rerun()

    df = load_table("intrants")
    if not df.empty:
        for _, row in df.iterrows():
            stock = float(pd.to_numeric(pd.Series([row.get("stock_actuel",0)]), errors="coerce").fillna(0).iloc[0])
            threshold = float(pd.to_numeric(pd.Series([row.get("seuil_alerte",0)]), errors="coerce").fillna(0).iloc[0])
            if threshold and stock <= threshold:
                st.warning(f"⚠️ Stock bas : {row.get('nom','')} — {stock} {row.get('unite','')}")
        st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================
# 24. MATÉRIEL & MAINTENANCE
# ============================================================

elif menu == "🚜 Matériel & Maintenance":
    st.title("🚜 Matériel & Maintenance")
    with st.form("equipment_form"):
        c1,c2,c3 = st.columns(3)
        with c1:
            name = st.text_input("Équipement *")
            category = st.selectbox("Catégorie", ["Tracteur","Motopompe","Semoir","Pulvérisateur","Véhicule","Autre"])
        with c2:
            status = st.selectbox("État", ["Opérationnel","En révision","En panne","Hors service"])
            last = st.date_input("Dernière révision", value=date.today())
        with c3:
            next_rev = st.date_input("Prochaine révision", value=date.today())
            meter = st.number_input("Compteur / heures machine", min_value=0.0)
        notes = st.text_area("Observations")
        photo = st.file_uploader(
            "📷 Photo / preuve maintenance",
            type=["png","jpg","jpeg","webp","pdf"],
            key="equipment_photo"
        )
        if st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True):
            if name.strip():
                rec = db_insert(
                    "materiel",
                    {
                        "nom_equipement": name.strip(),
                        "categorie": category,
                        "statut_marche": status,
                        "date_derniere_revision": str(last),
                        "prochaine_revision": str(next_rev),
                        "compteur_heures": meter,
                        "observations": notes.strip(),
                    },
                    f"Matériel {name.strip()}",
                )
                if rec and photo is not None:
                    meta = storage_upload(photo, "materiel", rec.get("id","new"))
                    if meta:
                        db_update("materiel","id",rec.get("id"),meta,"Photo matériel ajoutée")
                st.success("Matériel enregistré.")
                st.rerun()

    df = load_table("materiel")
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        for _, row in df.iterrows():
            render_attachment(row)


# ============================================================
# 25. FINANCES & COÛTS
# ============================================================

elif menu == "💰 Finances & Coûts":
    st.title(f"💰 Finances & Coûts — {champ_name}")
    if champ_id is not None:
        with st.form("expense_form"):
            c1,c2,c3 = st.columns(3)
            with c1:
                kind = st.text_input("Nature de la dépense *")
                d = st.date_input("Date", value=date.today())
            with c2:
                amount = st.number_input("Montant (FCFA)", min_value=0.0)
                supplier = st.text_input("Fournisseur")
            with c3:
                payment = st.selectbox("Mode de paiement", ["Espèces","Virement","Mobile Money","Crédit","Autre"])
                ref = st.text_input("Référence")
            note = st.text_area("Observation")
            proof = st.file_uploader(
                "📷 Facture / reçu / justificatif",
                type=["png","jpg","jpeg","webp","pdf"],
                key="expense_proof"
            )
            if st.form_submit_button("💾 Enregistrer la dépense", type="primary", use_container_width=True):
                if kind.strip():
                    rec = db_insert(
                        "depenses",
                        {
                            "champ_id": champ_id,
                            "type": kind.strip(),
                            "montant": amount,
                            "date": str(d),
                            "fournisseur": supplier.strip(),
                            "mode_paiement": payment,
                            "reference": ref.strip(),
                            "remarque": note.strip(),
                        },
                        f"Dépense {kind.strip()} — {amount} FCFA — {champ_name}",
                    )
                    if rec and proof is not None:
                        meta = storage_upload(proof, "depenses", rec.get("id","new"))
                        if meta:
                            db_update("depenses","id",rec.get("id"),meta,"Justificatif dépense ajouté")
                    st.success("Dépense enregistrée dans Supabase.")
                    st.rerun()

        df = filter_by_champ(load_table("depenses"), champ_id)
        if not df.empty:
            st.metric("Coûts cumulés", f"{safe_num(df,'montant'):,.0f} FCFA")
            st.dataframe(df, use_container_width=True, hide_index=True)
            for _, row in df.iterrows():
                render_attachment(row)


# ============================================================
# 26. ROI
# ============================================================

elif menu == "📈 Rentabilité & ROI":
    st.title(f"📈 Rentabilité & ROI — {champ_name}")
    if champ_id is not None:
        dep = filter_by_champ(load_table("depenses"), champ_id)
        rec = filter_by_champ(load_table("recoltes"), champ_id)
        costs = safe_num(dep, "montant")
        sales = (
            float((
                pd.to_numeric(rec.get("quantite_kg",pd.Series(dtype=float)),errors="coerce").fillna(0)
                * pd.to_numeric(rec.get("prix_unitaire",pd.Series(dtype=float)),errors="coerce").fillna(0)
            ).sum()) if not rec.empty else 0
        )
        margin = sales-costs
        roi = (margin/costs*100) if costs else None

        a,b,c,d = st.columns(4)
        a.metric("Coûts", f"{costs:,.0f} FCFA")
        b.metric("Valeur récoltes", f"{sales:,.0f} FCFA")
        c.metric("Marge", f"{margin:,.0f} FCFA")
        d.metric("ROI", f"{roi:.1f}%" if roi is not None else "—")

        st.markdown("### 📊 Lecture")
        if roi is None:
            st.info("ROI non calculable : aucune dépense enregistrée.")
        elif roi < 0:
            st.error("Marge négative : analysez les postes de coût et le rendement.")
        elif roi < 20:
            st.warning("Rentabilité faible : demandez une analyse IA ciblée.")
        else:
            st.success("Rentabilité positive sur les données enregistrées.")


# ============================================================
# 27. RISQUES & MÉTÉO
# ============================================================

elif menu == "🌤️ Risques & Météo":
    st.title(f"🌤️ Risques & Météo — {champ_name}")
    if champ_id is not None:
        with st.form("risk_form"):
            c1,c2 = st.columns(2)
            with c1:
                risk = st.selectbox(
                    "Risque",
                    ["Sécheresse","Inondation","Vents violents",
                     "Ravageur","Maladie","Chaleur","Autre"]
                )
                level = st.selectbox("Niveau", ["Faible","Modéré","Élevé","Critique"])
            with c2:
                expected = st.date_input("Date / période de suivi", value=date.today())
                source = st.text_input("Source de l'information")
            recommendation = st.text_area("Recommandation technique")
            if st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True):
                db_insert(
                    "alertes_meteo",
                    {
                        "champ_id": champ_id,
                        "date": str(expected),
                        "type_risque": risk,
                        "niveau_alerte": level,
                        "recommandation_ts": recommendation.strip(),
                        "source": source.strip(),
                    },
                    f"Alerte {risk} — {level} — {champ_name}",
                )
                st.success("Alerte enregistrée.")
                st.rerun()

        df = filter_by_champ(load_table("alertes_meteo"), champ_id)
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================
# 28. IA AGRICOLE
# ============================================================

elif menu == "🤖 IA Agricole":
    st.title(f"🤖 YAM AGRI-EXPERT — analyse intelligente de {champ_name}")
    if champ_id is None:
        st.warning("Sélectionnez une parcelle.")
    else:
        if not ai_available():
            st.warning(
                "IA non activée. Ajoutez OPENAI_API_KEY dans Streamlit secrets. "
                "Le reste de l'application fonctionne sans l'IA."
            )

        st.markdown(
            """
<div class="ai-box">
<b>🧠 Ce que l'IA analyse :</b>
parcelle, culture, travaux, temps de travail, pluie, eau, incidents,
intrants, coûts, récoltes, matériel, risques et, si vous les sélectionnez,
les photos stockées dans Supabase Storage.
</div>
""",
            unsafe_allow_html=True,
        )

        question = st.text_area(
            "Question / mission de l'expert",
            value=(
                "Analyse l'état de la parcelle, détecte les problèmes prioritaires "
                "et propose un plan d'action concret à 48 h et 7 jours."
            ),
        )

        # Sélection d'images depuis les incidents.
        incident_df = filter_by_champ(load_table("incidents"), champ_id)
        image_rows = []
        if not incident_df.empty:
            image_candidates = []
            for idx, row in incident_df.iterrows():
                if local_or_storage_bytes(row):
                    label = (
                        f"{row.get('date','')} — {row.get('categorie','')} — "
                        f"{row.get('description','')[:70]}"
                    )
                    image_candidates.append((idx, label))
            selected_indices = st.multiselect(
                "📷 Photos à analyser par vision",
                [x[0] for x in image_candidates],
                format_func=lambda x: dict(image_candidates).get(x, str(x)),
            )
            image_rows = [incident_df.loc[i] for i in selected_indices]

        if st.button("🧠 Lancer l'analyse agricole", type="primary", use_container_width=True):
            with st.spinner("YAM AGRI-EXPERT analyse les données et les évidences..."):
                analysis = ai_analyse_agricole(
                    champ_id, champ_name, question, image_rows=image_rows
                )
            st.session_state.ai_last = analysis

        if st.session_state.get("ai_last"):
            st.markdown("### 📝 Avis de l'expert")
            st.markdown(st.session_state.ai_last)
            st.caption(f"Modèle : {ai_model()} · Analyse fondée sur les données disponibles.")


# ============================================================
# 29. RAPPORTS PROFESSIONNELS
# ============================================================

elif menu == "📑 Rapports Professionnels":
    st.title(f"📑 Rapport professionnel — {champ_name}")
    if champ_id is None:
        st.warning("Sélectionnez une parcelle.")
    else:
        report_date = st.date_input("Date officielle du rapport", value=date.today())

        include_ai = st.checkbox(
            "🤖 Inclure l'avis YAM AGRI-EXPERT dans le rapport",
            value=True,
        )
        ai_text = ""
        if include_ai:
            if st.session_state.get("ai_last"):
                ai_text = st.session_state.ai_last
            else:
                st.info(
                    "Aucun avis IA déjà calculé. Vous pouvez générer le rapport "
                    "sans IA ou lancer une analyse dans le module IA."
                )

        if st.button("📄 Générer le rapport A4 professionnel", type="primary", use_container_width=True):
            with st.spinner("Génération du rapport..."):
                pdf = generate_pdf_report(
                    champ_id, champ_name, report_date, ai_text=ai_text
                )
            st.session_state.report_pdf = pdf
            st.session_state.report_name = (
                f"Rapport_YAM_{safe_filename(champ_name)}_{report_date}.pdf"
            )
            st.success("Rapport généré.")

        if st.session_state.get("report_pdf"):
            st.download_button(
                "📥 TÉLÉCHARGER LE RAPPORT PDF",
                st.session_state.report_pdf,
                file_name=st.session_state.report_name,
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )

            if st.button("☁️ Archiver le rapport dans Supabase Storage"):
                fake = type(
                    "UploadLike",
                    (),
                    {
                        "name": st.session_state.report_name,
                        "type": "application/pdf",
                        "getvalue": lambda self: st.session_state.report_pdf,
                    },
                )()
                meta = storage_upload(fake, "rapports", champ_id)
                if meta:
                    db_insert(
                        "messages_workspace",
                        {
                            "auteur": f"{prenom} {nom}".strip(),
                            "email": user_email(),
                            "role": role,
                            "destinataire": "Tous",
                            "priorite": "Important",
                            "texte": f"Rapport professionnel {champ_name}",
                            "date_heure": datetime.now().isoformat(timespec="seconds"),
                            "type_contenu": "Rapport PDF",
                            "champ_concerne": champ_name,
                            **meta,
                        },
                        f"Archivage rapport {champ_name}",
                    )
                    st.success("Rapport archivé dans Supabase Storage.")


# ============================================================
# 30. COLLABORATION & WORKSPACE
# ============================================================

elif menu == "💬 Collaboration & Workspace":
    st.title("💬 Collaboration & Workspace")
    st.link_button(
        "🚀 Créer une réunion Google Meet",
        "https://meet.google.com/new",
        use_container_width=True,
    )

    with st.form("workspace_form"):
        c1,c2 = st.columns(2)
        with c1:
            target = st.selectbox(
                "Destinataire",
                ["Tous","Techniciens","Gestionnaires","Propriétaires","Utilisateur spécifique"]
            )
            priority = st.selectbox("Priorité", ["Normal","Important","Urgent"])
        with c2:
            content_type = st.selectbox(
                "Type", ["Note","Photo","Vidéo","Document","Rapport PDF","Lien"]
            )
            target_email = st.text_input("E-mail cible (si nécessaire)")
        linked_champ = (
            st.selectbox(
                "Parcelle liée",
                ["Aucune"] + db_champs["nom"].astype(str).tolist()
                if not db_champs.empty and "nom" in db_champs.columns else ["Aucune"]
            )
        )
        text = st.text_area("Message / consigne / lien")
        attachment = st.file_uploader(
            "Joindre un fichier",
            type=["png","jpg","jpeg","webp","mp4","pdf","docx","xlsx"],
            key="workspace_file",
        )
        confirm = st.checkbox("Je confirme la publication.")
        if st.form_submit_button("📤 Publier", type="primary", use_container_width=True):
            if confirm and (text.strip() or attachment is not None):
                meta = storage_upload(
                    attachment, "workspace", datetime.now().strftime("%Y%m%d")
                ) if attachment is not None else {}
                db_insert(
                    "messages_workspace",
                    {
                        "auteur": f"{prenom} {nom}".strip(),
                        "email": user_email(),
                        "role": role,
                        "destinataire": target,
                        "destinataire_email": target_email.strip(),
                        "priorite": priority,
                        "texte": text.strip(),
                        "date_heure": datetime.now().isoformat(timespec="seconds"),
                        "type_contenu": content_type,
                        "champ_concerne": linked_champ,
                        **meta,
                    },
                    f"Publication workspace {content_type}",
                )
                st.success("Publication enregistrée.")
                st.rerun()
            else:
                st.warning("Confirmez et saisissez un message ou joignez un fichier.")

    st.subheader("📜 Fil de travail")
    df = load_table("messages_workspace")
    if not df.empty:
        for _, row in df.iloc[::-1].iterrows():
            with st.container(border=True):
                st.markdown(
                    f"**{row.get('auteur','')}** · {row.get('role','')} · "
                    f"{row.get('date_heure','')} · {row.get('priorite','')}"
                )
                if nonempty(row.get("champ_concerne","")):
                    st.caption(f"Parcelle : {row.get('champ_concerne')}")
                st.write(row.get("texte",""))
                render_attachment(row)


# ============================================================
# 31. LISTE BLANCHE & ADMINISTRATION
# ============================================================

elif menu == "🔐 Liste Blanche & Administration":
    if not is_admin():
        st.error("🔒 Accès réservé à l'administration.")
        st.stop()

    st.title("🔐 Liste Blanche, rôles, modules et paramètres")
    st.info(
        "La liste blanche détermine les comptes autorisés. "
        "Le rôle définit le socle fonctionnel et modules_autorises peut encore restreindre ce socle."
    )

    with st.form("new_user"):
        c1,c2,c3 = st.columns(3)
        with c1:
            email = st.text_input("E-mail *")
            password = st.text_input("Mot de passe", type="password")
            first = st.text_input("Prénom")
        with c2:
            last = st.text_input("Nom")
            new_role = st.selectbox("Rôle", ROLES)
            modules = st.multiselect(
                "Modules autorisés",
                list(MODULES.keys()),
                default=DEFAULT_ROLE_MODULES.get(new_role, []),
            )
        with c3:
            st.markdown("**Droits du rôle**")
            st.write({
                "Niveau": ROLE_LEVEL.get(new_role, 0),
                "Nombre de modules": len(modules),
            })

        if st.form_submit_button("➕ Ajouter à la liste blanche", type="primary", use_container_width=True):
            if email.strip():
                db_insert(
                    "whitelist_users",
                    {
                        "email": email.strip().lower(),
                        "password": password,
                        "prenom": first.strip(),
                        "nom": last.strip(),
                        "role": new_role,
                        "modules_autorises": json.dumps(modules, ensure_ascii=False),
                    },
                    f"Ajout utilisateur {email.strip().lower()}",
                )
                st.success("Utilisateur ajouté.")
                st.rerun()

    df = load_table("whitelist_users")
    if not df.empty:
        display_cols = [c for c in ["id","email","prenom","nom","role","modules_autorises"] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

        if "id" in df.columns:
            for _, row in df.iterrows():
                if str(row.get("email","")).lower() == "iy@2012":
                    continue
                if st.button(
                    f"🗑️ Supprimer {row.get('email','')}",
                    key=f"delete_user_{row['id']}",
                ):
                    db_delete(
                        "whitelist_users","id",row["id"],
                        f"Suppression utilisateur {row.get('email','')}"
                    )
                    st.rerun()


# ============================================================
# 32. JOURNAL D'AUDIT
# ============================================================

elif menu == "📜 Journal d'Audit":
    if not is_admin():
        st.error("🔒 Accès réservé à l'administration.")
        st.stop()

    st.title("📜 Journal d'Audit")
    df = load_table("historique_modifications")
    if not df.empty:
        st.dataframe(
            df.iloc[::-1].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Aucun événement d'audit enregistré.")


# ============================================================
# 33. FIN
# ============================================================

st.markdown("---")
st.caption(
    "YAM — plateforme de travail agricole centralisée. "
    "Les données non renseignées ne sont pas inventées dans les rapports. "
    "Les pièces jointes nouvelles sont stockées dans Supabase Storage."
)
