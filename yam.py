import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import os
import math
from folium.plugins import Draw
from streamlit_js_eval import get_geolocation
# Importation pour la cartographie dynamique interactive
import folium
from streamlit_folium import st_folium

# Imports pour l'intégration de Supabase
from supabase import create_client, Client

# Imports pour les exports PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# 1. CONFIGURATION DE LA PAGE & DESIGN ÉPURÉ
# ==========================================
st.set_page_config(
    page_title="AgriGestion YAM",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Création du dossier pour stocker les fichiers médias et rapports partagés
UPLOAD_DIR = "uploads_workspace"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg,#f7faf8 0%,#eef5f0 100%); color:#17251d; }
        [data-testid="stSidebar"] { background: linear-gradient(180deg,#10281d 0%,#173b29 100%); }
        [data-testid="stSidebar"] * { color:#f5fbf7 !important; }
        .main-header { background:linear-gradient(135deg,#ffffff,#eef7f0); padding:22px 28px; border:1px solid #d7e7dc; border-radius:22px; box-shadow:0 12px 35px rgba(20,70,40,.10); margin:8px 0 22px; display:flex; justify-content:space-between; align-items:center; gap:16px; }
        .brand-title { font-size:30px; font-weight:900; color:#123b28; letter-spacing:-.5px; }
        .brand-subtitle { font-size:13px; color:#5b6f63; margin-top:3px; }
        .user-badge { background:#dff2e6; color:#17482d; border:1px solid #bddbc8; padding:9px 14px; border-radius:999px; font-weight:700; white-space:nowrap; }
        .card-container { background:rgba(255,255,255,.96); padding:22px; border:1px solid #dce9df; border-radius:18px; box-shadow:0 10px 30px rgba(24,68,42,.08); margin-bottom:18px; }
        div.stButton > button { border-radius:12px; font-weight:750; min-height:42px; border:1px solid #cfe0d4; background:#ffffff; color:#163b27; }
        div.stButton > button:hover { border-color:#4e9c6b; color:#123b28; box-shadow:0 5px 18px rgba(37,110,65,.13); }
        .stTabs [data-baseweb="tab-list"] { gap:8px; background:#ffffff; padding:8px; border:1px solid #dce9df; border-radius:16px; box-shadow:0 8px 25px rgba(20,70,40,.07); }
        .stTabs [data-baseweb="tab"] { height:44px; border-radius:11px; font-weight:800; color:#315342; }
        .stTabs [aria-selected="true"] { background:#dff2e6; color:#0e4a2a !important; }
        .stTextInput input,.stNumberInput input,.stTextArea textarea { color:#17251d !important; background:#ffffff !important; }
        label, .stMarkdown, .stCaption, .stSelectbox, .stTextInput, .stNumberInput, .stTextArea { color:#17251d !important; }
        [data-testid="stMetricValue"] { color:#123b28; font-weight:900; }
        @media(max-width:768px){ .main-header{flex-direction:column;align-items:flex-start}.user-badge{white-space:normal}.brand-title{font-size:24px} }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. GESTION DE LA BASE DE DONNÉES SUPABASE & SÉCURITÉ XXL
# ==========================================
@st.cache_resource
def init_supabase() -> Client:
    # Récupération sécurisée des clés depuis st.secrets ou variables d'environnement
    supabase_url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
    supabase_key = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))
    
    if not supabase_url or not supabase_key:
        # Fallback pour éviter le crash visuel si les secrets ne sont pas saisis immédiatement
        st.error("⚠️ Veuillez configurer SUPABASE_URL et SUPABASE_KEY dans vos secrets Streamlit (.streamlit/secrets.toml).")
    return create_client(supabase_url, supabase_key)

supabase = init_supabase()

def init_db_supabase():
    try:
        # Vérification initiale ou auto-initialisation de l'administrateur principal dans Supabase
        res = supabase.table("whitelist_users").select("*").eq("email", "iy@2012").execute()
        if not res.data:
            supabase.table("whitelist_users").insert({
                "email": "iy@2012",
                "password": "issayoume2026",
                "prenom": "Issa",
                "nom": "Youme",
                "role": "Administration",
                "modules_autorises": "TOUS"
            }).execute()
    except Exception as e:
        # Gère les cas où les tables distantes n'ont pas encore été créées dans le dashboard Supabase
        pass

init_db_supabase()

@st.cache_data(ttl=60)
def load_table(table_name):
    try:
        response = supabase.table(table_name).select("*").execute()
        data = response.data
        if data:
            return pd.DataFrame(data)
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

def execute_query(query_type, table_name, data=None, match_col=None, match_val=None, action_desc="", user_info=None):
    try:
        if query_type == "INSERT":
            supabase.table(table_name).insert(data).execute()
        elif query_type == "DELETE":
            supabase.table(table_name).delete().eq(match_col, match_val).execute()
        elif query_type == "UPDATE":
            supabase.table(table_name).update(data).eq(match_col, match_val).execute()
            
        if action_desc and user_info:
            date_act = datetime.now().strftime("%d/%m/%Y à %H:%M")
            supabase.table("historique_modifications").insert({
                "date_heure": date_act,
                "utilisateur": f"{user_info.get('prenom', '')} {user_info.get('nom', '')}",
                "email": user_info.get('gmail', ''),
                "role": user_info.get('role', ''),
                "action": action_desc,
                "details": "Succès"
            }).execute()
            
        load_table.clear()
        return True
    except Exception as e:
        st.error(f"Erreur Supabase ({action_desc}) : {e}")
        return False

# ==========================================
# 3. AUTHENTIFICATION DYNAMIQUE & TRANSAPOLITE
# ==========================================
def auth_system():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.markdown("<br><br>", unsafe_allow_html=True)
        col_auth1, col_auth2, col_auth3 = st.columns([1, 1.5, 1])
        with col_auth2:
            st.markdown("""
                <div style="background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);">
                    <h2 style="text-align: center; color: #10b981; margin-bottom: 5px;">🌾 AgriGestion Pro</h2>
                    <p style="text-align: center; color: #6b7280; font-size: 14px; margin-bottom: 25px;">Plateforme Intégrée de Gestion Agricole (Supabase)</p>
            """, unsafe_allow_html=True)

            with st.form("form_login_admin"):
                email_input = st.text_input("Adresse e-mail professionnelle *", placeholder="iy@2012")
                password_input = st.text_input("Mot de passe d'accès *", type="password")
                st.markdown("<br>", unsafe_allow_html=True)
                submit_login = st.form_submit_button("Se Connecter", use_container_width=True, type="primary")

                if submit_login:
                    email_propre = email_input.strip().lower()
                    try:
                        res = supabase.table("whitelist_users").select("*").ilike("email", email_propre).execute()
                        user_records = res.data
                        
                        if user_records and password_input == user_records[0].get("password"):
                            user_record = user_records[0]
                            st.session_state.authenticated = True
                            st.session_state.registered_tech = {
                                "nom": user_record.get("nom", ""),
                                "prenom": user_record.get("prenom", ""),
                                "gmail": email_propre,
                                "role": user_record.get("role", "Technicien"),
                                "modules_autorises": user_record.get("modules_autorises", "TOUS")
                            }
                            st.rerun()
                        else:
                            st.error("❌ Identifiants incorrects ou non autorisés.")
                    except Exception as ex:
                        st.error(f"❌ Erreur de connexion à la base de données : {ex}")
            st.markdown("</div>", unsafe_allow_html=True)
        return False
    return True

if not auth_system():
    st.stop()

# ==========================================
# 4. EXPORTATIONS PDF FORMAT A4 STRICT
# ==========================================
def export_fiche_parcelle_a4(nom_p, surf_p, cult_p, lat_p, lon_p, stat_p):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=15, alignment=1, textColor=colors.HexColor('#10b981'), spaceAfter=10)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#1e3d59'), spaceBefore=10, spaceAfter=6)
    normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#333333'), leading=14)
    
    elements.append(Paragraph("AGRIGESTION PRO — FICHE TECHNIQUE DE PARCELLE", title_style))
    elements.append(Paragraph(f"<b>Date d'édition :</b> {datetime.now().strftime('%d/%m/%Y à %H:%M')}", normal_style))
    elements.append(Spacer(1, 10))
    
    elements.append(Paragraph("1. Spécifications Générales", subtitle_style))
    data_fiche = [
        ["Nom de la Parcelle", str(nom_p)],
        ["Superficie Exploitable", f"{surf_p} Hectares"],
        ["Culture Actuelle", str(cult_p)],
        ["Statut Phénologique", str(stat_p)],
        ["Repérage GPS (Lat, Lon)", f"{lat_p} , {lon_p}"]
    ]
    t = Table(data_fiche, colWidths=[180, 320], hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1f2937')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("2. Note d'Exploitation & Suivi", subtitle_style))
    elements.append(Paragraph("Cette fiche certifie l'enregistrement de la parcelle dans le système de gestion agricole intégré AgriGestion Pro (Supabase).", normal_style))
    doc.build(elements)
    return buffer.getvalue()

def export_parcelle_pdf(champ_nom, date_rapport):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    tech = st.session_state.get('registered_tech', {})
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=15, alignment=1, textColor=colors.HexColor('#1e3d59'), spaceAfter=10)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#10b981'), spaceBefore=12, spaceAfter=6)
    normal_style = styles['Normal']
    
    elements.append(Paragraph(f"RAPPORT EXHAUSTIF : {champ_nom.upper()}", title_style))
    header_info = f"<b>Date :</b> {date_rapport.strftime('%d/%m/%Y')} | <b>Établi par :</b> {tech.get('prenom', '')} {tech.get('nom', '')} ({tech.get('role', '')})"
    elements.append(Paragraph(header_info, normal_style))
    elements.append(Spacer(1, 10))

    df_c = load_table('champs')
    champ_id = None
    if not df_c.empty and 'nom' in df_c.columns:
        champ_info = df_c[df_c['nom'] == champ_nom]
        if not champ_info.empty:
            champ_id = int(champ_info['id'].values[0])

    tables_to_export = {}
    if champ_id:
        df_pt = load_table('pointage')
        if not df_pt.empty and 'champ_nom' in df_pt.columns:
            df_pt_filtered = df_pt[df_pt['champ_nom'].astype(str).str.strip().str.lower() == str(champ_nom).strip().lower()]
            tables_to_export["1. Pointages & Présences (Membres & Groupes)"] = df_pt_filtered[['date', 'employe_nom', 'groupe_nom', 'tache_effectuee', 'heures_travaillees']] if not df_pt_filtered.empty else pd.DataFrame()
        else:
            tables_to_export["1. Pointages & Présences (Membres & Groupes)"] = pd.DataFrame()
        
        df_rec = load_table('recoltes')
        tables_to_export["2. Récoltes de la Parcelle"] = df_rec[df_rec['champ_id'] == champ_id][['culture', 'date_recolte', 'quantite_kg', 'prix_unitaire']] if not df_rec.empty and 'champ_id' in df_rec.columns else pd.DataFrame()
        
        df_dep = load_table('depenses')
        tables_to_export["3. Dépenses & Intrants"] = df_dep[df_dep['champ_id'] == champ_id][['type', 'montant', 'date']] if not df_dep.empty and 'champ_id' in df_dep.columns else pd.DataFrame()

    for section_title, df_sec in tables_to_export.items():
        elements.append(Paragraph(section_title, subtitle_style))
        if not df_sec.empty:
            data = [df_sec.columns.tolist()] + df_sec.astype(str).values.tolist()
            t = Table(data, hAlign='LEFT')
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("<i>Aucune donnée enregistrée spécifiquement pour cette parcelle.</i>", normal_style))
        elements.append(Spacer(1, 6))

    doc.build(elements)
    return buffer.getvalue()

# ==========================================
# 5. NAVIGATION PREMIUM EN 5 GRANDS ONGLETS
# ==========================================
tech = st.session_state.get('registered_tech', {})
prenom_tech = tech.get('prenom', 'Utilisateur')
nom_tech = tech.get('nom', '')
role_tech = tech.get('role', 'Technicien')
email_connecte = tech.get('gmail', '').lower()

# Menu stable : uniquement les composants natifs Streamlit sont utilisés.
# Cela évite les conflits React/DOM du type "removeChild" provoqués par du JavaScript
# ou des éléments HTML qui modifient l'arbre DOM de Streamlit.
menu_administration = [
    "🔐 Paramètres & Liste Blanche", "📜 Historique"
]
menu_gestionnaire = [
    "📊 Tableau de Bord", "👥 Groupes & Membres", "💰 Finances & Marges",
    "📦 Stocks d'Intrants", "🚜 Maintenance Matériel", "📈 Rentabilité & ROI"
]
menu_techniciens = [
    "🌱 Cartographie & Parcelles", "⏰ Pointage des Horaires", "📅 Planning & Travaux",
    "🌾 Récoltes & Rendements", "🌧️ Pluviométrie", "⚠️ Incidents",
    "🏷️ Traçabilité & Lots", "💧 Irrigation & Eau", "🌤️ Risques & Météo",
    "📑 EXPORT RAPPORT PARCELLE"
]
menu_commun = ["💬 Espace Collaboration & Workspace"]

if role_tech == "Administration" or email_connecte == "iy@2012":
    accessibles = menu_commun + menu_administration + menu_gestionnaire + menu_techniciens
elif role_tech in ("Gestionnaire", "Propriétaire"):
    accessibles = menu_commun + menu_gestionnaire + menu_techniciens
else:
    accessibles = menu_commun + menu_techniciens

groupes = {
    "🏠 ACCUEIL": [m for m in ["📊 Tableau de Bord"] if m in accessibles],
    "🌱 EXPLOITATION": [m for m in ["🌱 Cartographie & Parcelles", "📅 Planning & Travaux", "🌾 Récoltes & Rendements", "🌧️ Pluviométrie", "💧 Irrigation & Eau", "🌤️ Risques & Météo"] if m in accessibles],
    "👥 ÉQUIPE & OPÉRATIONS": [m for m in ["👥 Groupes & Membres", "⏰ Pointage des Horaires", "⚠️ Incidents", "🏷️ Traçabilité & Lots", "💬 Espace Collaboration & Workspace"] if m in accessibles],
    "💰 GESTION & MATÉRIEL": [m for m in ["💰 Finances & Marges", "📦 Stocks d'Intrants", "🚜 Maintenance Matériel", "📈 Rentabilité & ROI"] if m in accessibles],
    "⚙️ ADMINISTRATION": [m for m in ["🔐 Paramètres & Liste Blanche", "📜 Historique", "📑 EXPORT RAPPORT PARCELLE"] if m in accessibles],
}

# Mémoriser la page courante sans jamais supposer qu'une variable `menu` existe.
if "selected_menu" not in st.session_state or st.session_state.selected_menu not in accessibles:
    st.session_state.selected_menu = accessibles[0] if accessibles else "📊 Tableau de Bord"

st.markdown(f"""
<div class="main-header">
  <div>
    <div class="brand-title">🌾 AgriGestion YAM</div>
    <div class="brand-subtitle">Pilotage agricole intelligent · espace sécurisé</div>
  </div>
  <div class="user-badge">👤 {prenom_tech} {nom_tech} · {role_tech}</div>
</div>
""", unsafe_allow_html=True)

tab_labels = list(groupes.keys())
tabs = st.tabs(tab_labels)
for tab, label in zip(tabs, tab_labels):
    with tab:
        items = groupes[label]
        if items:
            # Navigation secondaire native, horizontale, en haut de la page.
            cols = st.columns(min(len(items), 5))
            for i, item in enumerate(items):
                with cols[i % len(cols)]:
                    if st.button(item, key=f"topnav_{label}_{i}", use_container_width=True):
                        st.session_state.selected_menu = item
                        st.rerun()
        else:
            st.caption("Aucune fonctionnalité disponible pour votre rôle.")

menu = st.session_state.get("selected_menu", accessibles[0] if accessibles else "📊 Tableau de Bord")

with st.sidebar:
    st.markdown("## 🌾 AgriGestion YAM")
    st.caption(f"Connecté : {prenom_tech} {nom_tech}")
    st.markdown("### 📍 Page active")
    st.info(menu)
    st.markdown("---")
    st.markdown("### 🧭 Accès rapide")
    for item in accessibles:
        if st.button(item, key=f"side_{item}", use_container_width=True):
            st.session_state.selected_menu = item
            st.rerun()
    st.markdown("---")
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

db_champs = load_table('champs')
champ_id_actif = None
champ_selectionne = "Aucune parcelle"

# Sélecteur de parcelle uniquement hors cartographie.
if menu != "🌱 Cartographie & Parcelles":
    if not db_champs.empty and 'nom' in db_champs.columns and 'id' in db_champs.columns:
        liste_champs = {row['nom']: row['id'] for _, row in db_champs.iterrows()}
        if liste_champs:
            col_sel1, col_sel2 = st.columns([3, 1])
            with col_sel1:
                champ_selectionne = st.selectbox("📍 Parcelle active", list(liste_champs.keys()))
                champ_id_actif = liste_champs[champ_selectionne]
                row_champ_actuel = db_champs[db_champs['id'] == champ_id_actif].iloc[0]
                pin_enreg = row_champ_actuel.get('code_pin')
                has_pin = pin_enreg is not None and str(pin_enreg).strip() not in ("", "None", "nan")
                if has_pin:
                    if f"pin_ok_{champ_id_actif}" not in st.session_state:
                        st.session_state[f"pin_ok_{champ_id_actif}"] = False
                    if not st.session_state[f"pin_ok_{champ_id_actif}"]:
                        st.warning(f"🔒 Parcelle protégée : {champ_selectionne}")
                        saisie_pin = st.text_input("Code PIN", type="password", key=f"input_pin_{champ_id_actif}")
                        if st.button("🔓 Déverrouiller", key=f"btn_unlock_{champ_id_actif}"):
                            if saisie_pin == str(pin_enreg):
                                st.session_state[f"pin_ok_{champ_id_actif}"] = True
                                st.success("✅ Accès autorisé")
                                st.rerun()
                            else:
                                st.error("❌ Code PIN incorrect")
            with col_sel2:
                st.write("")
                if st.button("➕ Nouvelle parcelle", use_container_width=True):
                    st.session_state.selected_menu = "🌱 Cartographie & Parcelles"
                    st.rerun()
    st.divider()

# ==========================================
# 6. MODULES APPLICATIFS STRUCTURÉS
# ==========================================

if menu == "📊 Tableau de Bord":
    st.title("📊 Tableau de Bord Global (Espace Gestionnaire)")
    m1, m2, m3, m4 = st.columns(4)
    df_c = load_table('champs')
    df_e = load_table('employes')
    df_eq = load_table('equipes')
    df_r = load_table('recoltes')
    
    tot_surf = df_c['superficie_ha'].sum() if not df_c.empty and 'superficie_ha' in df_c.columns else 0
    tot_ouv = len(df_e) if not df_e.empty else 0
    tot_eq = len(df_eq) if not df_eq.empty else 0
    tot_rec = df_r['quantite_kg'].sum() if not df_r.empty and 'quantite_kg' in df_r.columns else 0
    
    m1.metric("Superficie Totale", f"{tot_surf:.2f} Ha")
    m2.metric("Groupes Actifs", f"{tot_eq}")
    m3.metric("Effectif Global", f"{tot_ouv}")
    m4.metric("Récoltes Totales", f"{tot_rec/1000:.2f} T")
    st.divider()
    if df_c.empty:
        st.info("👋 Aucune parcelle enregistrée.")
    else:
        st.subheader("📍 Aperçu Global des Parcelles")
        colonnes_affichees = [col for col in ["nom", "superficie_ha", "culture_actuelle", "statut"] if col in df_c.columns]
        st.dataframe(df_c[colonnes_affichees], use_container_width=True)

elif menu == "🌱 Cartographie & Parcelles":
    st.title("🌱 Cartographie & Éditeur de Parcelles (YAM Gestion)")
    
    if 'lat_active' not in st.session_state:
        st.session_state['lat_active'] = 14.6937
    if 'lon_active' not in st.session_state:
        st.session_state['lon_active'] = -17.4441

    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    st.subheader("🗺️ 1. Éditeur de Dessin SIG & Navigation Google Maps")
    
    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        search_query = st.text_input("🔍 Rechercher une zone / village / localité :", placeholder="Ex: Touba, Bambey, Niakhar, Diourbel...")
        if search_query:
            try:
                from geopy.geocoders import Nominatim
                geolocator = Nominatim(user_agent="agrigestion_app")
                location = geolocator.geocode(search_query + ", Senegal")
                if location:
                    st.session_state['lat_active'] = location.latitude
                    st.session_state['lon_active'] = location.longitude
                    st.success(f"📍 Navigation vers : {location.address}")
            except Exception:
                st.info("Saisissez un nom de lieu valide.")
    with col_s2:
        st.write(" ")
        st.write(" ")
        st.caption("ℹ️ Utilisez la barre d'outils à gauche de la carte pour dessiner votre parcelle.")

    df_c = load_table('champs')
    
    m = folium.Map(
        location=[float(st.session_state['lat_active']), float(st.session_state['lon_active'])], 
        zoom_start=15,
        tiles=None
    )

    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        attr="Google",
        name="🛰️ Google Satellite / Hybride",
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
        attr="Google",
        name="🏔️ Google Relief / Topographie",
        overlay=False,
        control=True
    ).add_to(m)

    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        attr="Google",
        name="🗺️ Google Plan Standard",
        overlay=False,
        control=True
    ).add_to(m)

    if not df_c.empty and 'latitude' in df_c.columns and 'longitude' in df_c.columns:
        for _, r in df_c.iterrows():
            folium.Marker(
                location=[r['latitude'], r['longitude']],
                popup=f"<b>{r.get('nom','')}</b><br>Culture: {r.get('culture_actuelle','')}<br>Superficie: {r.get('superficie_ha','')} Ha",
                icon=folium.Icon(color="green", icon="leaf")
            ).add_to(m)

    draw = Draw(
        export=False,
        position='topleft',
        draw_options={
            'polyline': False,
            'polygon': True,
            'rectangle': True,
            'circle': False,
            'marker': True,
            'circlemarker': False
        },
        edit_options={
            'poly': {'allowIntersection': False},
            'edit': True,
            'remove': True
        }
    )
    draw.add_to(m)

    folium.LayerControl(position="topright", collapsed=False).add_to(m)
    
    output = st_folium(
        m, 
        width="100%", 
        height=400, 
        key=f"map_arcgis_editor_{st.session_state['lat_active']}_{st.session_state['lon_active']}",
        returned_objects=["all_drawings"]
    )

    calc_surf_ha = 0.0
    center_lat_val = float(st.session_state['lat_active'])
    center_lon_val = float(st.session_state['lon_active'])

    if output and output.get("all_drawings"):
        drawings = output["all_drawings"]
        if len(drawings) > 0:
            last_geometry = drawings[-1].get("geometry", {})
            geom_type = last_geometry.get("type")
            coords = last_geometry.get("coordinates", [])

            if geom_type in ["Polygon", "Rectangle"] and len(coords) > 0:
                ring = coords[0]
                lats = [pt[1] for pt in ring]
                lons = [pt[0] for pt in ring]
                
                center_lat_val = round(sum(lats) / len(lats), 6)
                center_lon_val = round(sum(lons) / len(lons), 6)

                lat_avg = math.radians(center_lat_val)
                m_per_deg_lat = 111139.0
                m_per_deg_lon = 111139.0 * math.cos(lat_avg)
                
                xy = [(pt[0] * m_per_deg_lon, pt[1] * m_per_deg_lat) for pt in ring]
                area = 0.0
                n = len(xy)
                for i in range(n):
                    j = (i + 1) % n
                    area += xy[i][0] * xy[j][1]
                    area -= xy[j][0] * xy[i][1]
                area_m2 = abs(area) / 2.0
                calc_surf_ha = round(area_m2 / 10000.0, 2)
                if calc_surf_ha == 0:
                    calc_surf_ha = 0.01

                st.success(f"📐 **Emprise capturée ({geom_type}) :** Centre GPS ({center_lat_val}, {center_lon_val}) | Superficie : **{calc_surf_ha} Ha**")

            elif geom_type == "Point" and len(coords) >= 2:
                center_lon_val = round(coords[0], 6)
                center_lat_val = round(coords[1], 6)
                st.info(f"📍 **Point sélectionné :** GPS ({center_lat_val}, {center_lon_val})")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    st.subheader("➕ 2. Enregistrement de la Parcelle & Génération Fiche A4")
    
    with st.form("form_champ_arcgis_sync"):
        col_f_1, col_f_2 = st.columns(2)
        with col_f_1:
            nom_p = st.text_input("Nom de la parcelle *", placeholder="Ex: Parcelle Nord 01")
            surf_p = st.number_input("Superficie (Ha)", min_value=0.01, value=float(calc_surf_ha if calc_surf_ha > 0 else 1.0), step=0.1)
            cult_p = st.text_input("Culture principale", placeholder="Ex: Maïs, Arachide, Oignon...")
            stat_p = st.selectbox("Statut initial", ["En préparation", "Semé", "En croissance", "Prêt à récolter"])
        with col_f_2:
            lat_p = st.number_input("Latitude Centre GPS", value=float(center_lat_val), format="%.6f")
            lon_p = st.number_input("Longitude Centre GPS", value=float(center_lon_val), format="%.6f")
            pin_p = st.text_input("Code PIN de sécurité (optionnel)", type="password")
        
        submit_parcelle = st.form_submit_button("💾 Enregistrer la Parcelle & Générer la Fiche A4", use_container_width=True, type="primary")
        if submit_parcelle:
            if nom_p.strip():
                data_dict = {
                    "nom": nom_p.strip(),
                    "superficie_ha": surf_p,
                    "latitude": lat_p,
                    "longitude": lon_p,
                    "culture_actuelle": cult_p,
                    "statut": stat_p,
                    "icone_lieu": "leaf",
                    "code_pin": pin_p.strip() if pin_p else ""
                }
                success_ins = execute_query("INSERT", "champs", data=data_dict, action_desc=f"Création de la parcelle '{nom_p.strip()}'", user_info=tech)
                if success_ins:
                    st.success(f"✅ Parcelle **{nom_p.strip()}** enregistrée avec succès !")
                    try:
                        pdf_data = export_fiche_parcelle_a4(nom_p.strip(), surf_p, cult_p, lat_p, lon_p, stat_p)
                        st.session_state['last_created_pdf'] = pdf_data
                        st.session_state['last_created_name'] = nom_p.strip()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur lors de la génération du PDF : {e}")
            else:
                st.warning("⚠️ Indiquez un nom de parcelle.")
    
    if 'last_created_pdf' in st.session_state:
        st.markdown("---")
        st.download_button(
            label=f"📄 Télécharger la Fiche A4 Officielle ({st.session_state.get('last_created_name', 'Parcelle')})", 
            data=st.session_state['last_created_pdf'], 
            file_name=f"fiche_a4_{st.session_state.get('last_created_name', 'parcelle')}.pdf", 
            mime="application/pdf", 
            use_container_width=True,
            type="primary"
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    st.subheader("🗑️ Liste & Suppression des Parcelles")
    if not df_c.empty and 'id' in df_c.columns:
        for _, cp in df_c.iterrows():
            col_cp1, col_cp2 = st.columns([4, 1])
            with col_cp1:
                st.write(f"📍 **{cp.get('nom','')}** — {cp.get('superficie_ha','')} Ha | GPS : ({cp.get('latitude','')}, {cp.get('longitude','')}) | Culture : {cp.get('culture_actuelle','')}")
            with col_cp2:
                if st.button("🗑️ Supprimer", key=f"del_champ_{cp['id']}"):
                    execute_query("DELETE", "champs", match_col="id", match_val=cp['id'], action_desc=f"Suppression parcelle '{cp.get('nom','')}'", user_info=tech)
                    st.success("Parcelle supprimée !")
                    st.rerun()
    else:
        st.info("Aucune parcelle enregistrée.")
    st.markdown("</div>", unsafe_allow_html=True)

elif menu == "👥 Groupes & Membres":
    st.title("👥 Gestion des Groupes & Membres (Espace Gestionnaire)")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("1️⃣ Groupes de Travail")
        with st.form("form_grp"):
            nom_g = st.text_input("Nom du groupe")
            chef_g = st.text_input("Chef de groupe")
            if st.form_submit_button("Ajouter le Groupe", use_container_width=True):
                if nom_g.strip():
                    execute_query("INSERT", "equipes", data={"nom_groupe": nom_g.strip(), "chef_groupe": chef_g.strip()}, action_desc=f"Création groupe '{nom_g}'", user_info=tech)
                    st.success("✅ Groupe créé !")
                    st.rerun()
        
        df_eq_list = load_table('equipes')
        if not df_eq_list.empty and 'id' in df_eq_list.columns:
            st.markdown("---")
            st.write("**Liste des groupes :**")
            for _, g in df_eq_list.iterrows():
                cg1, cg2 = st.columns([3, 1])
                cg1.write(f"👥 **{g.get('nom_groupe','')}** (Chef : {g.get('chef_groupe','')})")
                if cg2.button("🗑️", key=f"del_eq_{g['id']}"):
                    execute_query("DELETE", "equipes", match_col="id", match_val=g['id'], action_desc=f"Suppression groupe '{g.get('nom_groupe','')}'", user_info=tech)
                    st.success("Groupe supprimé !")
                    st.rerun()

    with col_g2:
        st.subheader("2️⃣ Membres / Employés")
        df_eq_disp = load_table('equipes')
        groupes_noms = df_eq_disp['nom_groupe'].tolist() if not df_eq_disp.empty and 'nom_groupe' in df_eq_disp.columns else []
        with st.form("form_emp"):
            nom_emp = st.text_input("Nom et Prénom")
            role_emp = st.text_input("Rôle (ex: Ouvrier, Mécanicien)")
            grp_emp = st.selectbox("Groupe assigné", groupes_noms if groupes_noms else ["Aucun"])
            tarif = st.number_input("Tarif journalier (FCFA)", min_value=0.0, value=2500.0)
            if st.form_submit_button("Ajouter l'Employé", use_container_width=True):
                if nom_emp.strip():
                    execute_query("INSERT", "employes", data={"nom": nom_emp.strip(), "role": role_emp.strip(), "groupe_nom": grp_emp, "tarif_journalier": tarif}, action_desc=f"Ajout employé '{nom_emp}'", user_info=tech)
                    st.success("✅ Employé ajouté !")
                    st.rerun()
        
        df_emp_list = load_table('employes')
        if not df_emp_list.empty and 'id' in df_emp_list.columns:
            st.markdown("---")
            st.write("**Liste des employés :**")
            for _, emp in df_emp_list.iterrows():
                ce1, ce2 = st.columns([3, 1])
                ce1.write(f"👤 **{emp.get('nom','')}** ({emp.get('role','')})")
                if ce2.button("🗑️", key=f"del_emp_{emp['id']}"):
                    execute_query("DELETE", "employes", match_col="id", match_val=emp['id'], action_desc=f"Suppression employé '{emp.get('nom','')}'", user_info=tech)
                    st.success("Employé supprimé !")
                    st.rerun()

elif menu == "⏰ Pointage des Horaires":
    st.title(f"⏰ Pointage des Horaires — {champ_selectionne} (Espace Technicien)")
    if champ_selectionne == "Aucune parcelle":
        st.warning("⚠️ Veuillez sélectionner une parcelle active.")
    else:
        df_emp = load_table('employes')
        if df_emp.empty:
            st.warning("⚠️ Aucun employé enregistré.")
        else:
            groupes_disponibles = df_emp['groupe_nom'].dropna().unique().tolist() if 'groupe_nom' in df_emp.columns else []
            
            with st.form("form_pointage_params"):
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    groupes_selectionnes = st.multiselect("Filtrer par Groupe(s) :", groupes_disponibles, default=groupes_disponibles)
                with col_f2:
                    date_p = st.date_input("Date du pointage", value=date.today())
                with col_f3:
                    tache_globale = st.selectbox("Tâche par défaut :", ["Travaux", "Labour", "Semis", "Désherbage", "Récolte", "Irrigation"])
                
                df_emp_filtre = df_emp[df_emp['groupe_nom'].isin(groupes_selectionnes)] if groupes_selectionnes and 'groupe_nom' in df_emp.columns else df_emp
                
                lignes = [{
                    "Présent": True, 
                    "Employé": f"{e.get('nom','')} - {e.get('role','')}", 
                    "Groupe": e.get('groupe_nom',''), 
                    "Tâche": tache_globale, 
                    "Heures": 8.0, 
                    "Remarque": ""
                } for _, e in df_emp_filtre.iterrows()]
                
                edited = st.data_editor(pd.DataFrame(lignes), hide_index=True, use_container_width=True)
                if st.form_submit_button("💾 Enregistrer le Pointage Global", use_container_width=True, type="primary"):
                    for _, r in edited.iterrows():
                        if r["Présent"]:
                            execute_query(
                                "INSERT", "pointage",
                                data={
                                    "date": str(date_p),
                                    "employe_nom": r["Employé"],
                                    "groupe_nom": r["Groupe"],
                                    "champ_nom": champ_selectionne,
                                    "statut_presence": "Présent",
                                    "tache_effectuee": r["Tâche"],
                                    "heures_travaillees": float(r["Heures"]),
                                    "remarque": str(r["Remarque"])
                                },
                                action_desc=f"Pointage de {r['Employé']} sur {champ_selectionne}",
                                user_info=tech
                            )
                    st.success("✅ Pointage enregistré avec succès !")
                    st.rerun()

        st.markdown("---")
        st.subheader("📜 Historique des pointages de la parcelle")
        df_pts = load_table('pointage')
        df_pts_champ = df_pts[df_pts['champ_nom'].astype(str).str.strip().str.lower() == str(champ_selectionne).strip().lower()] if not df_pts.empty and 'champ_nom' in df_pts.columns else pd.DataFrame()
        
        if not df_pts_champ.empty and 'id' in df_pts_champ.columns:
            for _, pt in df_pts_champ.iterrows():
                cp1, cp2 = st.columns([4, 1])
                cp1.write(f"📅 {pt.get('date','')} | Groupe: **{pt.get('groupe_nom', 'N/A')}** | Membre: **{pt.get('employe_nom','')}** — Tâche : {pt.get('tache_effectuee','')} ({pt.get('heures_travaillees','')}h)")
                if cp2.button("🗑️ Supprimer", key=f"del_pt_{pt['id']}"):
                    execute_query("DELETE", "pointage", match_col="id", match_val=pt['id'], action_desc="Suppression d'un pointage", user_info=tech)
                    st.success("Pointage supprimé !")
                    st.rerun()
        else:
            st.info("Aucun pointage enregistré spécifiquement pour cette parcelle.")

elif menu == "📅 Planning & Travaux":
    st.title(f"📅 Planning & Travaux — {champ_selectionne}")
    if champ_id_actif:
        with st.form("form_plan"):
            t_trav = st.selectbox("Type de travaux", ["Labour", "Semis", "Désherbage", "Fertilisation", "Récolte"])
            d_tache = st.date_input("Date prévue", value=date.today())
            hrs = st.number_input("Heures prévues", value=8.0)
            if st.form_submit_button("💾 Planifier", use_container_width=True):
                execute_query("INSERT", "taches", data={"champ_id": champ_id_actif, "groupe_id": 1, "type_travail": t_trav, "date_tache": str(d_tache), "heures_travaillees": hrs, "statut": "Planifié"}, action_desc=f"Planification '{t_trav}'", user_info=tech)
                st.success("✅ Planifié !")
                st.rerun()
        
        df_t = load_table('taches')
        df_t_champ = df_t[df_t['champ_id'] == champ_id_actif] if not df_t.empty and 'champ_id' in df_t.columns else pd.DataFrame()
        st.markdown("---")
        st.subheader("Liste des tâches planifiées")
        if not df_t_champ.empty and 'id' in df_t_champ.columns:
            for _, tc in df_t_champ.iterrows():
                ct1, ct2 = st.columns([4, 1])
                ct1.write(f"📌 **{tc.get('type_travail','')}** (Prévu le : {tc.get('date_tache','')} — {tc.get('heures_travaillees','')}h)")
                if ct2.button("🗑️", key=f"del_tc_{tc['id']}"):
                    execute_query("DELETE", "taches", match_col="id", match_val=tc['id'], action_desc=f"Suppression tâche '{tc.get('type_travail','')}'", user_info=tech)
                    st.success("Tâche supprimée !")
                    st.rerun()
        else:
            st.info("Aucune tâche planifiée.")

elif menu == "🌾 Récoltes & Rendements":
    st.title(f"🌾 Récoltes & Rendements — {champ_selectionne}")
    if champ_id_actif:
        with st.form("form_rec"):
            cult = st.text_input("Culture")
            qte = st.number_input("Quantité (Kg)", min_value=0.0)
            pu = st.number_input("Prix unitaire (FCFA)", min_value=0.0, value=300.0)
            if st.form_submit_button("Enregistrer Récolte", use_container_width=True):
                execute_query("INSERT", "recoltes", data={"champ_id": champ_id_actif, "culture": cult, "date_recolte": str(date.today()), "quantite_kg": qte, "prix_unitaire": pu}, action_desc=f"Récolte '{cult}' ({qte} Kg)", user_info=tech)
                st.success("✅ Enregistré !")
                st.rerun()
        
        df_r = load_table('recoltes')
        df_r_champ = df_r[df_r['champ_id'] == champ_id_actif] if not df_r.empty and 'champ_id' in df_r.columns else pd.DataFrame()
        st.markdown("---")
        st.subheader("Historique des récoltes")
        if not df_r_champ.empty and 'id' in df_r_champ.columns:
            for _, rc in df_r_champ.iterrows():
                cr1, cr2 = st.columns([4, 1])
                cr1.write(f"🌾 **{rc.get('culture','')}** : {rc.get('quantite_kg','')} Kg à {rc.get('prix_unitaire','')} FCFA/Kg ({rc.get('date_recolte','')})")
                if cr2.button("🗑️", key=f"del_rc_{rc['id']}"):
                    execute_query("DELETE", "recoltes", match_col="id", match_val=rc['id'], action_desc="Suppression d'une récolte", user_info=tech)
                    st.success("Récolte supprimée !")
                    st.rerun()
        else:
            st.info("Aucune récolte enregistrée.")

elif menu == "💰 Finances & Marges":
    st.title(f"💰 Finances & Marges — {champ_selectionne} (Espace Gestionnaire)")
    if champ_id_actif:
        with st.form("form_fin"):
            motif = st.text_input("Motif de la dépense (ex: Achat Engrais)")
            mnt = st.number_input("Montant (FCFA)", min_value=0.0)
            if st.form_submit_button("Enregistrer Dépense", use_container_width=True):
                execute_query("INSERT", "depenses", data={"champ_id": champ_id_actif, "type": motif, "montant": mnt, "date": str(date.today()), "facture_nom": "Aucune"}, action_desc=f"Dépense '{motif}' ({mnt} FCFA)", user_info=tech)
                st.success("✅ Dépense enregistrée !")
                st.rerun()
        
        df_d = load_table('depenses')
        df_d_champ = df_d[df_d['champ_id'] == champ_id_actif] if not df_d.empty and 'champ_id' in df_d.columns else pd.DataFrame()
        st.markdown("---")
        st.subheader("Liste des dépenses")
        if not df_d_champ.empty and 'id' in df_d_champ.columns:
            for _, dp in df_d_champ.iterrows():
                cd1, cd2 = st.columns([4, 1])
                cd1.write(f"💸 **{dp.get('type','')}** : {dp.get('montant','')} FCFA ({dp.get('date','')})")
                if cd2.button("🗑️", key=f"del_dp_{dp['id']}"):
                    execute_query("DELETE", "depenses", match_col="id", match_val=dp['id'], action_desc=f"Suppression dépense '{dp.get('type','')}'", user_info=tech)
                    st.success("Dépense supprimée !")
                    st.rerun()
        else:
            st.info("Aucune dépense enregistrée.")

elif menu == "📦 Stocks d'Intrants":
    st.title("📦 Stocks d'Intrants (Espace Gestionnaire)")
    with st.form("form_int"):
        nom_i = st.text_input("Nom de l'intrant")
        cat_i = st.selectbox("Catégorie", ["Engrais", "Semence", "Pesticide", "Carburant"])
        stk = st.number_input("Stock actuel", min_value=0.0)
        unite = st.text_input("Unité (Sacs, Litres, Kg)")
        if st.form_submit_button("Ajouter l'intrant", use_container_width=True):
            execute_query("INSERT", "intrants", data={"nom": nom_i, "categorie": cat_i, "stock_actuel": stk, "unite": unite, "seuil_alerte": 2.0, "facture_nom": "Aucune"}, action_desc=f"Ajout intrant '{nom_i}'", user_info=tech)
            st.success("✅ Ajouté !")
            st.rerun()
            
    df_i = load_table('intrants')
    st.markdown("---")
    st.subheader("Liste des stocks")
    if not df_i.empty and 'id' in df_i.columns:
        for _, in_t in df_i.iterrows():
            ci1, ci2 = st.columns([4, 1])
            ci1.write(f"📦 **{in_t.get('nom','')}** ({in_t.get('categorie','')}) — Stock : {in_t.get('stock_actuel','')} {in_t.get('unite','')}")
            if ci2.button("🗑️", key=f"del_in_{in_t['id']}"):
                execute_query("DELETE", "intrants", match_col="id", match_val=in_t['id'], action_desc=f"Suppression intrant '{in_t.get('nom','')}'", user_info=tech)
                st.success("Intrant supprimé !")
                st.rerun()
    else:
        st.info("Aucun intrant en stock.")

elif menu == "🌧️ Pluviométrie":
    st.title(f"🌧️ Pluviométrie — {champ_selectionne}")
    if champ_id_actif:
        with st.form("form_plu"):
            mm = st.number_input("Hauteur de pluie (mm)", min_value=0.0)
            if st.form_submit_button("Enregistrer", use_container_width=True):
                execute_query("INSERT", "pluviometrie", data={"champ_id": champ_id_actif, "date": str(date.today()), "pluie_mm": mm}, action_desc=f"Pluviométrie {mm} mm", user_info=tech)
                st.success("✅ Enregistré !")
                st.rerun()
                
        df_plu = load_table('pluviometrie')
        df_plu_champ = df_plu[df_plu['champ_id'] == champ_id_actif] if not df_plu.empty and 'champ_id' in df_plu.columns else pd.DataFrame()
        st.markdown("---")
        st.subheader("Historique des relevés pluviométriques")
        if not df_plu_champ.empty and 'id' in df_plu_champ.columns:
            for _, plu in df_plu_champ.iterrows():
                cpl1, cpl2 = st.columns([4, 1])
                cpl1.write(f"🌧️ Date : {plu.get('date','')} — **{plu.get('pluie_mm','')} mm**")
                if cpl2.button("🗑️", key=f"del_plu_{plu['id']}"):
                    execute_query("DELETE", "pluviometrie", match_col="id", match_val=plu['id'], action_desc="Suppression relevé pluviométrique", user_info=tech)
                    st.success("Relevé supprimé !")
                    st.rerun()
        else:
            st.info("Aucun relevé pluviométrique.")

elif menu == "⚠️ Incidents":
    st.title(f"⚠️ Incidents — {champ_selectionne}")
    if champ_id_actif:
        with st.form("form_inc"):
            desc = st.text_area("Description de l'incident")
            grav = st.selectbox("Gravité", ["Faible", "Modéré", "Critique"])
            if st.form_submit_button("Déclarer l'incident", use_container_width=True):
                execute_query("INSERT", "incidents", data={"champ_id": champ_id_actif, "date": str(date.today()), "description": desc, "gravite": grav, "action": "En attente"}, action_desc=f"Incident ({grav})", user_info=tech)
                st.success("✅ Déclaré !")
                st.rerun()
                
        df_inc = load_table('incidents')
        df_inc_champ = df_inc[df_inc['champ_id'] == champ_id_actif] if not df_inc.empty and 'champ_id' in df_inc.columns else pd.DataFrame()
        st.markdown("---")
        st.subheader("Liste des incidents déclarés")
        if not df_inc_champ.empty and 'id' in df_inc_champ.columns:
            for _, inc in df_inc_champ.iterrows():
                cin1, cin2 = st.columns([4, 1])
                cin1.write(f"⚠️ [{inc.get('gravite','')}] {inc.get('date','')} : {inc.get('description','')}")
                if cin2.button("🗑️", key=f"del_inc_{inc['id']}"):
                    execute_query("DELETE", "incidents", match_col="id", match_val=inc['id'], action_desc="Suppression incident", user_info=tech)
                    st.success("Incident supprimé !")
                    st.rerun()
        else:
            st.info("Aucun incident déclaré.")

elif menu == "🚜 Maintenance Matériel":
    st.title("🚜 Maintenance Matériel (Espace Gestionnaire)")
    with st.form("form_mat"):
        nom_eq = st.text_input("Nom de l'équipement")
        cat_eq = st.selectbox("Catégorie", ["Tracteur", "Motopompe", "Semoir", "Pulvérisateur"])
        stat_m = st.selectbox("Statut", ["Opérationnel", "En panne", "En révision"])
        d_rev = st.date_input("Dernière révision", value=date.today())
        p_rev = st.date_input("Prochaine révision", value=date.today())
        if st.form_submit_button("Ajouter le Matériel", use_container_width=True):
            execute_query("INSERT", "materiel", data={"nom_equipement": nom_eq, "categorie": cat_eq, "statut_marche": stat_m, "date_derniere_revision": str(d_rev), "prochaine_revision": str(p_rev)}, action_desc=f"Ajout matériel '{nom_eq}'", user_info=tech)
            st.success("✅ Ajouté !")
            st.rerun()
            
    df_mat = load_table('materiel')
    st.markdown("---")
    st.subheader("Parc matériel")
    if not df_mat.empty and 'id' in df_mat.columns:
        for _, mat in df_mat.iterrows():
            cmat1, cmat2 = st.columns([4, 1])
            cmat1.write(f"🚜 **{mat.get('nom_equipement','')}** ({mat.get('categorie','')}) — Statut : {mat.get('statut_marche','')}")
            if cmat2.button("🗑️", key=f"del_mat_{mat['id']}"):
                execute_query("DELETE", "materiel", match_col="id", match_val=mat['id'], action_desc=f"Suppression matériel '{mat.get('nom_equipement','')}'", user_info=tech)
                st.success("Matériel supprimé !")
                st.rerun()
    else:
        st.info("Aucun matériel enregistré.")

elif menu == "🏷️ Traçabilité & Lots":
    st.title(f"🏷️ Traçabilité & Lots — {champ_selectionne}")
    if champ_id_actif:
        with st.form("form_trac"):
            lot = st.text_input("Code du lot", placeholder="Ex: LOT-TOMATE-2026-01")
            cult_tr = st.text_input("Culture associée")
            norme = st.text_input("Norme de certification (ex: GlobalGAP)")
            acheteur = st.text_input("Acheteur / Destination")
            if st.form_submit_button("Enregistrer le Lot", use_container_width=True):
                if lot.strip():
                    execute_query("INSERT", "tracabilite", data={"champ_id": champ_id_actif, "lot_code": lot.strip(), "culture": cult_tr, "date_recolte": str(date.today()), "norme_certification": norme, "acheteur": acheteur}, action_desc=f"Lot '{lot}'", user_info=tech)
                    st.success("✅ Lot enregistré !")
                    st.rerun()
                    
        df_trac = load_table('tracabilite')
        df_trac_champ = df_trac[df_trac['champ_id'] == champ_id_actif] if not df_trac.empty and 'champ_id' in df_trac.columns else pd.DataFrame()
        st.markdown("---")
        st.subheader("Lots enregistrés")
        if not df_trac_champ.empty and 'id' in df_trac_champ.columns:
            for _, tr in df_trac_champ.iterrows():
                ctr1, ctr2 = st.columns([4, 1])
                ctr1.write(f"🏷️ **{tr.get('lot_code','')}** ({tr.get('culture','')}) — Acheteur : {tr.get('acheteur','')}")
                if ctr2.button("🗑️", key=f"del_tr_{tr['id']}"):
                    execute_query("DELETE", "tracabilite", match_col="id", match_val=tr['id'], action_desc=f"Suppression lot '{tr.get('lot_code','')}'", user_info=tech)
                    st.success("Lot supprimé !")
                    st.rerun()
        else:
            st.info("Aucun lot enregistré.")

elif menu == "💧 Irrigation & Eau":
    st.title(f"💧 Irrigation & Eau — {champ_selectionne}")
    if champ_id_actif:
        with st.form("form_irrig"):
            vol_eau = st.number_input("Volume d'eau (m3)", min_value=0.0, value=50.0)
            methode = st.selectbox("Méthode d'irrigation", ["Goutte-à-goutte", "Aspersion", "Gravitaire"])
            duree = st.number_input("Durée (heures)", min_value=0.1, value=2.0)
            if st.form_submit_button("Enregistrer", use_container_width=True):
                execute_query("INSERT", "irrigation", data={"champ_id": champ_id_actif, "date": str(date.today()), "volume_eau_m3": vol_eau, "methode": methode, "duree_heures": duree}, action_desc=f"Irrigation {vol_eau}m3", user_info=tech)
                st.success("✅ Enregistré !")
                st.rerun()
                
        df_irrig = load_table('irrigation')
        df_irrig_champ = df_irrig[df_irrig['champ_id'] == champ_id_actif] if not df_irrig.empty and 'champ_id' in df_irrig.columns else pd.DataFrame()
        st.markdown("---")
        st.subheader("Historique des irrigations")
        if not df_irrig_champ.empty and 'id' in df_irrig_champ.columns:
            for _, ir in df_irrig_champ.iterrows():
                cir1, cir2 = st.columns([4, 1])
                cir1.write(f"💧 {ir.get('date','')} — **{ir.get('volume_eau_m3','')} m³** ({ir.get('methode','')}, {ir.get('duree_heures','')}h)")
                if cir2.button("🗑️", key=f"del_ir_{ir['id']}"):
                    execute_query("DELETE", "irrigation", match_col="id", match_val=ir['id'], action_desc="Suppression irrigation", user_info=tech)
                    st.success("Irrigation supprimée !")
                    st.rerun()
        else:
            st.info("Aucune irrigation enregistrée.")

elif menu == "🌤️ Risques & Météo":
    st.title(f"🌤️ Risques & Météo — {champ_selectionne}")
    if champ_id_actif:
        with st.form("form_meteo"):
            risque = st.selectbox("Type de risque", ["Sécheresse", "Inondation", "Vents violents", "Attaque parasitaire"])
            niveau = st.selectbox("Niveau d'alerte", ["Faible", "Modéré", "Élevé", "Critique"])
            reco = st.text_area("Recommandations techniques")
            if st.form_submit_button("Enregistrer Alerte", use_container_width=True):
                execute_query("INSERT", "alertes_meteo", data={"champ_id": champ_id_actif, "date": str(date.today()), "type_risque": risque, "niveau_alerte": niveau, "recommandation_ts": reco}, action_desc=f"Alerte '{risque}'", user_info=tech)
                st.success("✅ Alerte enregistrée !")
                st.rerun()
                
        df_meteo = load_table('alertes_meteo')
        df_meteo_champ = df_meteo[df_meteo['champ_id'] == champ_id_actif] if not df_meteo.empty and 'champ_id' in df_meteo.columns else pd.DataFrame()
        st.markdown("---")
        st.subheader("Alertes météo enregistrées")
        if not df_meteo_champ.empty and 'id' in df_meteo_champ.columns:
            for _, alt in df_meteo_champ.iterrows():
                cal1, cal2 = st.columns([4, 1])
                cal1.write(f"🌤️ [{alt.get('niveau_alerte','')}] **{alt.get('type_risque','')}** ({alt.get('date','')}) — {alt.get('recommandation_ts','')}")
                if cal2.button("🗑️", key=f"del_alt_{alt['id']}"):
                    execute_query("DELETE", "alertes_meteo", match_col="id", match_val=alt['id'], action_desc="Suppression alerte météo", user_info=tech)
                    st.success("Alerte supprimée !")
                    st.rerun()
        else:
            st.info("Aucune alerte enregistrée.")

elif menu == "📈 Rentabilité & ROI":
    st.title(f"📈 Rentabilité & ROI — {champ_selectionne} (Espace Gestionnaire)")
    if champ_id_actif:
        df_d = load_table('depenses')
        df_r = load_table('recoltes')
        df_d_champ = df_d[df_d['champ_id'] == champ_id_actif] if not df_d.empty and 'champ_id' in df_d.columns else pd.DataFrame()
        df_r_champ = df_r[df_r['champ_id'] == champ_id_actif] if not df_r.empty and 'champ_id' in df_r.columns else pd.DataFrame()
        
        total_dep = df_d_champ['montant'].sum() if not df_d_champ.empty and 'montant' in df_d_champ.columns else 0
        total_rec = (df_r_champ['quantite_kg'] * df_r_champ['prix_unitaire']).sum() if not df_r_champ.empty and 'quantite_kg' in df_r_champ.columns and 'prix_unitaire' in df_r_champ.columns else 0
        marge = total_rec - total_dep
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Dépenses", f"{total_dep:,.0f} FCFA")
        col2.metric("Ventes", f"{total_rec:,.0f} FCFA")
        col3.metric("Marge Nette", f"{marge:,.0f} FCFA")
    else:
        st.warning("Sélectionnez une parcelle active.")

elif menu == "💬 Espace Collaboration & Workspace":
    st.title("💬 Espace Collaboration & Espace de Travail Multimédia")
    
    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    st.subheader("📹 Réunions en Ligne & Liens Google Meet")
    col_meet1, col_meet2 = st.columns(2)
    with col_meet1:
        st.link_button("🚀 Créer une nouvelle réunion Google Meet", "https://meet.google.com/new", use_container_width=True)
    with col_meet2:
        custom_meet_link = st.text_input("Ou coller/partager un lien Google Meet personnalisé :", placeholder="Ex: https://meet.google.com/abc-defg-hij")
        if custom_meet_link.strip():
            st.markdown(f"🔗 **Lien prêt à rejoindre :** [{custom_meet_link}]({custom_meet_link})")
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.divider()
    
    st.subheader("📁 Partager un rapport, une photo, une vidéo ou un document")
    
    df_users_wl = load_table('whitelist_users')
    emails_disponibles = df_users_wl['email'].tolist() if not df_users_wl.empty and 'email' in df_users_wl.columns else []
    
    with st.form("form_workspace_media", clear_on_submit=False):
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            destinataire = st.selectbox("Destinataire visé (Cible) :", ["Tous", "Techniciens", "Gestionnaires", "Propriétaires", "Utilisateur Spécifique"])
        with col_c2:
            priorite = st.selectbox("Priorité :", ["Normal", "Important ⚠️", "Urgent 🚨"])
        with col_c3:
            type_contenu = st.selectbox("Type de contenu :", ["Note textuelle", "Rapport PDF", "Photo 📷", "Vidéo 🎥", "Document 📄", "Lien Réunion 📹"])
            
        destinataire_email = ""
        if destinataire == "Utilisateur Spécifique":
            if emails_disponibles:
                destinataire_email = st.selectbox("Sélectionner l'E-mail du Destinataire :", emails_disponibles)
            else:
                destinataire_email = st.text_input("Saisir l'E-mail du destinataire :", placeholder="destinataire@exemple.com")
        
# S'assure de charger ou d'utiliser le bon DataFrame (df_champs)
        noms_champs_list = df_champs['nom'].values.tolist() if 'df_champs' in locals() and not df_champs.empty and 'nom' in df_champs.columns else []
        champ_concerne = st.selectbox("Parcelle liée (Optionnel) :", ["Aucune"] + noms_champs_list)
        texte_message = st.text_area("Légende / Message descriptif ou lien Google Meet collé :", placeholder="Ex: Rapport d'inspection ou collez le lien de la réunion ici...")
        
        uploaded_file = st.file_uploader("Joindre un fichier (Photos, Vidéos, Docs, Rapports)", type=["png", "jpg", "jpeg", "mp4", "pdf", "docx", "xlsx"])
        
        st.markdown("---")
        st.markdown("### 🔍 Vérification & Confirmation avant envoi")
        confirmer_envoi = st.checkbox("✅ Je confirme l'exactitude des informations et l'envoi/publication vers les destinataires sélectionnés.")
        
        submit_msg = st.form_submit_button("📤 Valider et Publier dans l'Espace", use_container_width=True, type="primary")
        
        if submit_msg:
            if not confirmer_envoi:
                st.warning("⚠️ Veuillez cocher la case de confirmation avant de valider l'envoi.")
            else:
                fichier_path = ""
                nom_fichier = ""
                if uploaded_file is not None:
                    nom_fichier = uploaded_file.name
                    fichier_path = os.path.join(UPLOAD_DIR, nom_fichier)
                    with open(fichier_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                
                if texte_message.strip() or uploaded_file is not None:
                    auteur_complet = f"{tech.get('prenom', '')} {tech.get('nom', '')}".strip()
                    date_heure_actuelle = datetime.now().strftime("%d/%m/%Y à %H:%M")
                    
                    data_msg = {
                        "auteur": auteur_complet,
                        "email": email_connecte,
                        "role": role_tech,
                        "destinataire": destinataire,
                        "destinataire_email": destinataire_email,
                        "priorite": priorite,
                        "texte": texte_message.strip(),
                        "date_heure": date_heure_actuelle,
                        "type_contenu": type_contenu,
                        "fichier_path": fichier_path,
                        "nom_fichier": nom_fichier,
                        "champ_concerne": champ_concerne
                    }
                    execute_query("INSERT", "messages_workspace", data=data_msg, action_desc=f"Publication workspace ({type_contenu}) pour {destinataire}", user_info=tech)
                    st.success(f"✅ Publication validée et partagée avec succès depuis l'e-mail **{email_connecte}** vers **{destinataire}** !")
                    st.rerun()
                else:
                    st.warning("⚠️ Veuillez saisir un message ou joindre un fichier.")

    st.divider()
    st.subheader("📜 Fil d'actualité, Médias, Rapports & Consignes de l'Exploitation")
    df_messages = load_table('messages_workspace')
    if not df_messages.empty and 'id' in df_messages.columns:
        for _, msg in df_messages.iloc[::-1].iterrows():
            m_auteur = msg.get('auteur', 'Inconnu')
            m_email = msg.get('email', 'Email non spécifié')
            m_role = msg.get('role', 'Rôle')
            m_dest = msg.get('destinataire', 'Tous')
            m_dest_email = msg.get('destinataire_email', '')
            m_priorite = msg.get('priorite', 'Normal')
            m_texte = msg.get('texte', '')
            m_date = msg.get('date_heure', '')
            m_champ = msg.get('champ_concerne', 'Aucune')
            m_id = msg.get('id', 0)
            
            dest_affichage = f"<b>{m_dest}</b>"
            if m_dest_email and str(m_dest_email).strip() != "" and str(m_dest_email).strip() != "None":
                dest_affichage += f" (E-mail destinataire : &lt;{m_dest_email}&gt;)"
            
            col_m1, col_m2 = st.columns([10, 1])
            with col_m1:
                st.markdown(f"""
                    <div style="background: white; padding: 15px; border-radius: 10px; border-left: 4px solid #10b981; margin-bottom: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
                        <div style="display: flex; justify-content: space-between;">
                            <small style="color: #6b7280;"><b>{m_auteur}</b> &lt;{m_email}&gt; ({m_role}) ➔ Cible : {dest_affichage} {f"| 📍 <i>{m_champ}</i>" if m_champ != 'Aucune' else ''}</small>
                            <small style="color: #ef4444; font-weight: bold;">{m_priorite}</small>
                        </div>
                        <p style="margin: 10px 0; color: #1f2937; font-size: 14px;">{m_texte}</p>
                """, unsafe_allow_html=True)
                
                f_path = msg.get('fichier_path', '')
                f_name = msg.get('nom_fichier', '')
                f_type = msg.get('type_contenu', '')
                
                if f_path and isinstance(f_path, str) and os.path.exists(f_path):
                    if f_type == "Photo 📷" or f_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                        st.image(f_path, caption=f_name, width=400)
                    elif f_type == "Vidéo 🎥" or f_name.lower().endswith(('.mp4', '.mov')):
                        st.video(f_path)
                    else:
                        with open(f_path, "rb") as file_download:
                            st.download_button(
                                label=f"📥 Télécharger le fichier joint : {f_name}",
                                data=file_download,
                                file_name=f_name,
                                key=f"dl_ws_{m_id}"
                            )
                
                st.markdown(f"""
                        <div style="text-align: right; margin-top: 5px;"><small style="color: #9ca3af; font-size: 11px;">{m_date}</small></div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col_m2:
                st.write("")
                if st.button("🗑️", key=f"del_msg_{m_id}", help="Supprimer cette publication"):
                    execute_query("DELETE", "messages_workspace", match_col="id", match_val=m_id, action_desc="Suppression publication workspace", user_info=tech)
                    st.success("Publication supprimée !")
                    st.rerun()
    else:
        st.info("Aucun contenu dans l'espace de travail.")

elif menu == "📜 Historique":
    st.title("📜 Historique des Modifications (Espace Administration)")
    df_h = load_table('historique_modifications')
    st.dataframe(df_h.iloc[::-1].reset_index(drop=True) if not df_h.empty else df_h, use_container_width=True)

elif menu == "🔐 Paramètres & Liste Blanche":
    st.title("🔐 Paramètres, Liste Blanche & Synchronisation Supabase (Administration)")
    
    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    st.subheader("☁️ Statut de la Connexion Supabase")
    st.write("Votre application est désormais connectée à distance à votre base de données relationnelle PostgreSQL hébergée sur Supabase.")
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    with st.form("form_add_user"):
        st.subheader("Ajouter un nouvel utilisateur / rôle (Propriétaire, Gestionnaire, etc.)")
        mail_new = st.text_input("E-mail professionnel")
        pwd_new = st.text_input("Mot de passe", type="password")
        prenom_new = st.text_input("Prénom")
        nom_new = st.text_input("Nom")
        role_new = st.selectbox("Rôle attribué", ["Administration", "Gestionnaire", "Propriétaire", "Technicien"])
        if st.form_submit_button("Enregistrer l'utilisateur", use_container_width=True):
            if mail_new.strip():
                data_usr = {
                    "email": mail_new.strip().lower(),
                    "password": pwd_new,
                    "prenom": prenom_new,
                    "nom": nom_new,
                    "role": role_new,
                    "modules_autorises": "TOUS"
                }
                execute_query("INSERT", "whitelist_users", data=data_usr, action_desc=f"Ajout utilisateur {mail_new}", user_info=tech)
                st.success("✅ Utilisateur ajouté avec succès sur Supabase !")
                st.rerun()
                
    st.markdown("---")
    st.subheader("Utilisateurs autorisés")
    df_wl = load_table('whitelist_users')
    if not df_wl.empty and 'id' in df_wl.columns:
        for _, usr in df_wl.iterrows():
            cu1, cu2 = st.columns([4, 1])
            cu1.write(f"👤 **{usr.get('prenom','')} {usr.get('nom','')}** ({usr.get('email','')}) — Rôle : **{usr.get('role','')}**")
            if str(usr.get('email','')).lower() != "iy@2012":
                if cu2.button("🗑️ Supprimer", key=f"del_usr_{usr['id']}"):
                    execute_query("DELETE", "whitelist_users", match_col="id", match_val=usr['id'], action_desc=f"Suppression utilisateur '{usr.get('email','')}'", user_info=tech)
                    st.success("Utilisateur supprimé !")
                    st.rerun()
            else:
                cu2.text("Admin Principal")
    else:
        st.info("Aucun utilisateur.")

elif menu == "📑 EXPORT RAPPORT PARCELLE":
    st.title(f"📑 Export Rapport A4 — {champ_selectionne} (Espace Technicien)")
    date_exp = st.date_input("Date officielle du rapport", value=date.today())
    if champ_selectionne and champ_selectionne != "Aucune parcelle":
        pdf_bytes = export_parcelle_pdf(champ_selectionne, date_exp)
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                label=f"📥 Télécharger le Rapport A4 de '{champ_selectionne}'",
                data=pdf_bytes,
                file_name=f"rapport_parcelle_{champ_selectionne}.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary"
            )
        with col_dl2:
            if st.button("📤 Envoyer & Archiver ce Rapport dans l'Espace de Travail", use_container_width=True):
                nom_fic_pdf = f"Rapport_{champ_selectionne}_{date.today().strftime('%Y%m%d')}.pdf"
                f_path = os.path.join(UPLOAD_DIR, nom_fic_pdf)
                with open(f_path, "wb") as f:
                    f.write(pdf_bytes)
                
                auteur_complet = f"{tech.get('prenom', '')} {tech.get('nom', '')}".strip()
                date_heure_actuelle = datetime.now().strftime("%d/%m/%Y à %H:%M")
                
                data_arch = {
                    "auteur": auteur_complet,
                    "email": email_connecte,
                    "role": role_tech,
                    "destinataire": "Tous",
                    "destinataire_email": "",
                    "priorite": "Important ⚠️",
                    "texte": f"Rapport technique officiel généré pour la parcelle {champ_selectionne}.",
                    "date_heure": date_heure_actuelle,
                    "type_contenu": "Rapport PDF",
                    "fichier_path": f_path,
                    "nom_fichier": nom_fic_pdf,
                    "champ_concerne": champ_selectionne
                }
                execute_query("INSERT", "messages_workspace", data=data_arch, action_desc=f"Archivage rapport PDF {champ_selectionne} dans workspace", user_info=tech)
                st.success("✅ Rapport envoyé et archivé avec succès dans l'Espace Collaboration & Workspace !")
    else:
        st.warning("⚠️ Veuillez sélectionner une parcelle active valide pour générer le rapport.")
