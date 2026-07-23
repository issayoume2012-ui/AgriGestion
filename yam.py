import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import sqlite3
import os

# Importation pour la cartographie dynamique interactive
import folium
from streamlit_folium import st_folium

# Imports pour les exports PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# 1. CONFIGURATION DE LA PAGE & DESIGN ÉPURÉ
# ==========================================
st.set_page_config(
    page_title="AgriGestion Pro",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Création du dossier pour stocker les fichiers médias et rapports partagés
UPLOAD_DIR = "uploads_workspace"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

st.markdown("""
    <style>
        .stApp { background-color: #f4f7f6; }
        div.stButton > button { width: 100%; border-radius: 8px; font-weight: 600; padding: 0.5rem 1rem; }
        .main-header { background: white; padding: 15px 20px; border-radius: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
        .card-container { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 15px; }
        .badge-role { background-color: #e5e7eb; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: bold; color: #374151; }
        @media(max-width: 768px) {
            .stMetric { font-size: 14px !important; }
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. GESTION DE LA BASE DE DONNÉES ULTRA-RAPIDE
# ==========================================
def get_connection():
    return sqlite3.connect('agrigestion.db', check_same_thread=False)

@st.cache_resource
def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS champs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        nom TEXT, 
                        superficie_ha REAL, 
                        latitude REAL, 
                        longitude REAL, 
                        culture_actuelle TEXT, 
                        statut TEXT, 
                        icone_lieu TEXT,
                        code_pin TEXT
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS equipes (id INTEGER PRIMARY KEY AUTOINCREMENT, nom_groupe TEXT, chef_groupe TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS employes (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT, role TEXT, groupe_nom TEXT, tarif_journalier REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS pointage (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, employe_nom TEXT, groupe_nom TEXT, champ_nom TEXT, statut_presence TEXT, tache_effectuee TEXT, heures_travaillees REAL, remarque TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS taches (id INTEGER PRIMARY KEY AUTOINCREMENT, champ_id INTEGER, groupe_id INTEGER, type_travail TEXT, date_tache TEXT, heures_travaillees REAL, statut TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS recoltes (id INTEGER PRIMARY KEY AUTOINCREMENT, champ_id INTEGER, culture TEXT, date_recolte TEXT, quantite_kg REAL, prix_unitaire REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS depenses (id INTEGER PRIMARY KEY AUTOINCREMENT, champ_id INTEGER, type TEXT, montant REAL, date TEXT, facture_nom TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS intrants (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT, categorie TEXT, stock_actuel REAL, unite TEXT, seuil_alerte REAL, facture_nom TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS pluviometrie (id INTEGER PRIMARY KEY AUTOINCREMENT, champ_id INTEGER, date TEXT, pluie_mm REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY AUTOINCREMENT, champ_id INTEGER, date TEXT, description TEXT, gravite TEXT, action TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS materiel (id INTEGER PRIMARY KEY AUTOINCREMENT, nom_equipement TEXT, categorie TEXT, statut_marche TEXT, date_derniere_revision TEXT, prochaine_revision TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS tracabilite (id INTEGER PRIMARY KEY AUTOINCREMENT, champ_id INTEGER, lot_code TEXT, culture TEXT, date_recolte TEXT, norme_certification TEXT, acheteur TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS irrigation (id INTEGER PRIMARY KEY AUTOINCREMENT, champ_id INTEGER, date TEXT, volume_eau_m3 REAL, methode TEXT, duree_heures REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS alertes_meteo (id INTEGER PRIMARY KEY AUTOINCREMENT, champ_id INTEGER, date TEXT, type_risque TEXT, niveau_alerte TEXT, recommandation_ts TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages_workspace (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        auteur TEXT,
                        email TEXT,
                        role TEXT,
                        destinataire TEXT,
                        destinataire_email TEXT,
                        priorite TEXT,
                        texte TEXT,
                        date_heure TEXT,
                        type_contenu TEXT,
                        fichier_path TEXT,
                        nom_fichier TEXT,
                        champ_concerne TEXT
                    )''')
    
    colonnes_a_verifier = [
        ("email", "TEXT"),
        ("destinataire_email", "TEXT"),
        ("champ_concerne", "TEXT"),
        ("nom_fichier", "TEXT"),
        ("fichier_path", "TEXT"),
        ("type_contenu", "TEXT"),
        ("priorite", "TEXT"),
        ("destinataire", "TEXT")
    ]
    for col_nom, col_type in colonnes_a_verifier:
        try:
            cursor.execute(f"ALTER TABLE messages_workspace ADD COLUMN {col_nom} {col_type}")
        except sqlite3.OperationalError:
            pass 

    cursor.execute('''CREATE TABLE IF NOT EXISTS whitelist_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        email TEXT UNIQUE, 
                        password TEXT, 
                        prenom TEXT, 
                        nom TEXT, 
                        role TEXT,
                        modules_autorises TEXT
                    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS partage_champs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        champ_nom TEXT,
                        technicien_email TEXT,
                        droit TEXT
                    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS historique_modifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date_heure TEXT,
                        utilisateur TEXT,
                        email TEXT,
                        role TEXT,
                        action TEXT,
                        details TEXT
                    )''')

    cursor.execute("SELECT COUNT(*) FROM whitelist_users")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO whitelist_users (email, password, prenom, nom, role, modules_autorises) VALUES (?, ?, ?, ?, ?, ?)",
            ("issayoume2012@gmail.com", "issayoume2026", "Issa", "Youme", "Administration", "TOUS")
        )

    conn.commit()
    conn.close()
    return True

init_db()

@st.cache_data(ttl=300)
def load_table(table_name):
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    conn.close()
    return df

def execute_query(query, params=(), action_desc="", user_info=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    
    if action_desc and user_info:
        date_act = datetime.now().strftime("%d/%m/%Y à %H:%M")
        cursor.execute(
            "INSERT INTO historique_modifications (date_heure, utilisateur, email, role, action, details) VALUES (?, ?, ?, ?, ?, ?)",
            (date_act, f"{user_info.get('prenom', '')} {user_info.get('nom', '')}", user_info.get('gmail', ''), user_info.get('role', ''), action_desc, "Succès")
        )

    conn.commit()
    conn.close()
    load_table.clear()

# ==========================================
# 3. AUTHENTIFICATION DYNAMIQUE
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
                    <p style="text-align: center; color: #6b7280; font-size: 14px; margin-bottom: 25px;">Plateforme Intégrée de Gestion Agricole</p>
            """, unsafe_allow_html=True)

            with st.form("form_login_admin"):
                email_input = st.text_input("Adresse e-mail professionnelle *", placeholder="issayoume2012@gmail.com")
                password_input = st.text_input("Mot de passe d'accès *", type="password")
                st.markdown("<br>", unsafe_allow_html=True)
                submit_login = st.form_submit_button("Se Connecter", use_container_width=True, type="primary")

                if submit_login:
                    email_propre = email_input.strip().lower()
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT prenom, nom, role, password, modules_autorises FROM whitelist_users WHERE LOWER(email) = ?", (email_propre,))
                    user_record = cursor.fetchone()
                    conn.close()

                    if user_record and password_input == user_record[3]:
                        st.session_state.authenticated = True
                        st.session_state.registered_tech = {
                            "nom": user_record[1],
                            "prenom": user_record[0],
                            "gmail": email_propre,
                            "role": user_record[2],
                            "modules_autorises": user_record[4] if user_record[4] else "TOUS"
                        }
                        st.rerun()
                    else:
                        st.error("❌ Identifiants incorrects ou non autorisés.")
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
    elements.append(Paragraph("Cette fiche certifie l'enregistrement de la parcelle dans le système de gestion agricole intégré AgriGestion Pro.", normal_style))
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
    champ_info = df_c[df_c['nom'] == champ_nom]
    champ_id = int(champ_info['id'].values[0]) if not champ_info.empty else None

    tables_to_export = {}
    if champ_id:
        # Correction stricte : Filtrage rigoureux par nom de parcelle pour les pointages
        df_pt = load_table('pointage')
        if not df_pt.empty and 'champ_nom' in df_pt.columns:
            df_pt_filtered = df_pt[df_pt['champ_nom'].astype(str).str.strip().str.lower() == str(champ_nom).strip().lower()]
            tables_to_export["1. Pointages & Présences (Membres & Groupes)"] = df_pt_filtered[['date', 'employe_nom', 'groupe_nom', 'tache_effectuee', 'heures_travaillees']] if not df_pt_filtered.empty else pd.DataFrame()
        else:
            tables_to_export["1. Pointages & Présences (Membres & Groupes)"] = pd.DataFrame()
        
        df_rec = load_table('recoltes')
        tables_to_export["2. Récoltes de la Parcelle"] = df_rec[df_rec['champ_id'] == champ_id][['culture', 'date_recolte', 'quantite_kg', 'prix_unitaire']] if not df_rec.empty else pd.DataFrame()
        
        df_dep = load_table('depenses')
        tables_to_export["3. Dépenses & Intrants"] = df_dep[df_dep['champ_id'] == champ_id][['type', 'montant', 'date']] if not df_dep.empty else pd.DataFrame()

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
# 5. NAVIGATION & HEADER CLASSIFIÉ PAR RÔLE
# ==========================================
tech = st.session_state.get('registered_tech', {})
prenom_tech = tech.get('prenom', 'Utilisateur')
nom_tech = tech.get('nom', '')
role_tech = tech.get('role', 'Technicien')
email_connecte = tech.get('gmail', '').lower()

st.markdown(f"""
    <div class="main-header">
        <div><b>🌾 AgriGestion Pro</b> | <span style="color: #10b981; font-weight: 600;">{prenom_tech} {nom_tech}</span> — Rôle : <span class="badge-role">{role_tech}</span></div>
    </div>
""", unsafe_allow_html=True)

menu_administration = [
    "🔐 Paramètres & Liste Blanche",
    "📜 Historique"
]

menu_gestionnaire = [
    "📊 Tableau de Bord",
    "👥 Groupes & Membres",
    "💰 Finances & Marges",
    "📦 Stocks d'Intrants",
    "🚜 Maintenance Matériel",
    "📈 Rentabilité & ROI"
]

menu_techniciens = [
    "🌱 Cartographie & Parcelles",
    "⏰ Pointage des Horaires",
    "📅 Planning & Travaux",
    "🌾 Récoltes & Rendements",
    "🌧️ Pluviométrie",
    "⚠️ Incidents",
    "🏷️ Traçabilité & Lots",
    "💧 Irrigation & Eau",
    "🌤️ Risques & Météo",
    "📑 EXPORT RAPPORT PARCELLE"
]

menu_commun = [
    "💬 Espace Collaboration & Workspace"
]

if role_tech == "Administration" or email_connecte == "issayoume2012@gmail.com":
    tous_les_menus = menu_commun + menu_administration + menu_gestionnaire + menu_techniciens
elif role_tech == "Gestionnaire":
    tous_les_menus = menu_commun + menu_gestionnaire + menu_techniciens
else: 
    tous_les_menus = menu_commun + menu_techniciens

if "selected_menu" not in st.session_state:
    st.session_state.selected_menu = tous_les_menus[0]

col_nav1, col_nav2 = st.columns([3, 1])
with col_nav1:
    menu = st.selectbox("📌 Navigation Principale (Classée par Rôle)", tous_les_menus, index=tous_les_menus.index(st.session_state.selected_menu) if st.session_state.selected_menu in tous_les_menus else 0)
    st.session_state.selected_menu = menu
with col_nav2:
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

db_champs = load_table('champs')
champ_id_actif = None
champ_selectionne = "Aucune parcelle"

if menu != "🌱 Cartographie & Parcelles":
    if not db_champs.empty:
        liste_champs = {row['nom']: row['id'] for _, row in db_champs.iterrows()}
        col_sel1, col_sel2 = st.columns([3, 1])
        with col_sel1:
            champ_selectionne = st.selectbox("📍 Parcelle Active en Cours :", list(liste_champs.keys()))
            champ_id_actif = liste_champs[champ_selectionne]
            
            row_champ_actuel = db_champs[db_champs['id'] == champ_id_actif].iloc[0]
            pin_enreg = row_champ_actuel.get('code_pin')
            has_pin = pin_enreg is not None and str(pin_enreg).strip() != "" and str(pin_enreg).strip() != "None"
            
            if has_pin:
                if f"pin_ok_{champ_id_actif}" not in st.session_state:
                    st.session_state[f"pin_ok_{champ_id_actif}"] = False
                if not st.session_state[f"pin_ok_{champ_id_actif}"]:
                    st.warning(f"🔒 Cette parcelle (**{champ_selectionne}**) est protégée par code PIN.")
                    saisie_pin = st.text_input("Entrez le code PIN :", type="password", key=f"input_pin_{champ_id_actif}")
                    if st.button("🔓 Déverrouiller", key=f"btn_unlock_{champ_id_actif}"):
                        if saisie_pin == str(pin_enreg):
                            st.session_state[f"pin_ok_{champ_id_actif}"] = True
                            st.success("✅ Accès autorisé !")
                            st.rerun()
                        else:
                            st.error("❌ Code PIN incorrect.")

        with col_sel2:
            st.write("")
            if st.button("➕ Créer une Parcelle"):
                st.session_state.selected_menu = "🌱 Cartographie & Parcelles"
                st.rerun()

    st.divider()

# ==========================================
# 6. MODULES APPLICATIFS STRUCTURÉS (AVEC SUPPRESSIONS)
# ==========================================

if menu == "📊 Tableau de Bord":
    st.title("📊 Tableau de Bord Global (Espace Gestionnaire)")
    m1, m2, m3, m4 = st.columns(4)
    df_c = load_table('champs')
    df_e = load_table('employes')
    df_eq = load_table('equipes')
    df_r = load_table('recoltes')
    
    tot_surf = df_c['superficie_ha'].sum() if not df_c.empty else 0
    tot_ouv = len(df_e)
    tot_eq = len(df_eq)
    tot_rec = df_r['quantite_kg'].sum() if not df_r.empty else 0
    
    m1.metric("Superficie Totale", f"{tot_surf:.2f} Ha")
    m2.metric("Groupes Actifs", f"{tot_eq}")
    m3.metric("Effectif Global", f"{tot_ouv}")
    m4.metric("Récoltes Totales", f"{tot_rec/1000:.2f} T")
    st.divider()
    if df_c.empty:
        st.info("👋 Aucune parcelle enregistrée.")
    else:
        st.subheader("📍 Aperçu Global des Parcelles")
        st.dataframe(df_c[["nom", "superficie_ha", "culture_actuelle", "statut"]], use_container_width=True)

elif menu == "🌱 Cartographie & Parcelles":
    st.title("🌱 Cartographie & Parcelles (Espace Technicien)")
    
    if 'lat_active' not in st.session_state:
        st.session_state['lat_active'] = 14.6937
    if 'lon_active' not in st.session_state:
        st.session_state['lon_active'] = -17.4441

    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    st.subheader("🗺️ 1. Carte Interactive — Cliquez pour capturer les coordonnées GPS")
    df_c = load_table('champs')
    
    m = folium.Map(location=[float(st.session_state['lat_active']), float(st.session_state['lon_active'])], zoom_start=13)
    for _, r in df_c.iterrows():
        folium.Marker(
            location=[r['latitude'], r['longitude']],
            popup=f"<b>{r['nom']}</b><br>Culture: {r['culture_actuelle']}<br>Superficie: {r['superficie_ha']} Ha",
            icon=folium.Icon(color="green", icon="leaf")
        ).add_to(m)
        
    map_data = st_folium(m, width="100%", height=400, key="map_interactive_fluid_top", returned_objects=["last_clicked"])
    if map_data and map_data.get("last_clicked"):
        st.session_state['lat_active'] = round(map_data["last_clicked"]["lat"], 6)
        st.session_state['lon_active'] = round(map_data["last_clicked"]["lng"], 6)
        st.success(f"📍 Coordonnées GPS capturées : {st.session_state['lat_active']}, {st.session_state['lon_active']}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    st.subheader("➕ 2. Enregistrement d'une Nouvelle Parcelle & Fiche A4")
    with st.form("form_champ_fluide_top"):
        col_f_1, col_f_2 = st.columns(2)
        with col_f_1:
            nom_p = st.text_input("Nom de la parcelle *", placeholder="Ex: Champ Sud 02")
            surf_p = st.number_input("Superficie (Ha)", min_value=0.1, value=2.5, step=0.1)
            cult_p = st.text_input("Culture principale", placeholder="Ex: Tomate, Riz...")
            stat_p = st.selectbox("Statut initial", ["En préparation", "Semé", "En croissance", "Prêt à récolter"])
        with col_f_2:
            lat_p = st.number_input("Latitude GPS", value=float(st.session_state['lat_active']), format="%.6f")
            lon_p = st.number_input("Longitude GPS", value=float(st.session_state['lon_active']), format="%.6f")
            pin_p = st.text_input("Code PIN de sécurité (optionnel)", type="password")
        
        submit_parcelle = st.form_submit_button("💾 Enregistrer la Parcelle & Générer le PDF A4", use_container_width=True, type="primary")
        if submit_parcelle:
            if nom_p.strip():
                execute_query(
                    "INSERT INTO champs (nom, superficie_ha, latitude, longitude, culture_actuelle, statut, icone_lieu, code_pin) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (nom_p.strip(), surf_p, lat_p, lon_p, cult_p, stat_p, "leaf", pin_p.strip() if pin_p else ""),
                    action_desc=f"Création de la parcelle '{nom_p.strip()}'",
                    user_info=tech
                )
                st.success(f"✅ Parcelle **{nom_p.strip()}** enregistrée avec succès !")
                st.session_state['last_created_pdf'] = export_fiche_parcelle_a4(nom_p.strip(), surf_p, cult_p, lat_p, lon_p, stat_p)
                st.session_state['last_created_name'] = nom_p.strip()
            else:
                st.warning("⚠️ Indiquez un nom de parcelle.")
    
    if 'last_created_pdf' in st.session_state:
        st.download_button("📥 Télécharger la Fiche A4 officielle", data=st.session_state['last_created_pdf'], file_name=f"fiche_a4_{st.session_state['last_created_name']}.pdf", mime="application/pdf", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Section Suppression des Parcelles
    st.markdown("<div class='card-container'>", unsafe_allow_html=True)
    st.subheader("🗑️ Gestion / Suppression des Parcelles")
    if not df_c.empty:
        for _, cp in df_c.iterrows():
            col_cp1, col_cp2 = st.columns([4, 1])
            with col_cp1:
                st.write(f"📍 **{cp['nom']}** — {cp['superficie_ha']} Ha | Culture : {cp['culture_actuelle']}")
            with col_cp2:
                if st.button("🗑️ Supprimer", key=f"del_champ_{cp['id']}"):
                    execute_query("DELETE FROM champs WHERE id = ?", (cp['id'],), action_desc=f"Suppression parcelle '{cp['nom']}'", user_info=tech)
                    st.success("Parcelle supprimée !")
                    st.rerun()
    else:
        st.info("Aucune parcelle à supprimer.")
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
                    execute_query("INSERT INTO equipes (nom_groupe, chef_groupe) VALUES (?, ?)", (nom_g.strip(), chef_g.strip()), action_desc=f"Création groupe '{nom_g}'", user_info=tech)
                    st.success("✅ Groupe créé !")
                    st.rerun()
        
        df_eq_list = load_table('equipes')
        if not df_eq_list.empty:
            st.markdown("---")
            st.write("**Liste des groupes :**")
            for _, g in df_eq_list.iterrows():
                cg1, cg2 = st.columns([3, 1])
                cg1.write(f"👥 **{g['nom_groupe']}** (Chef : {g['chef_groupe']})")
                if cg2.button("🗑️", key=f"del_eq_{g['id']}"):
                    execute_query("DELETE FROM equipes WHERE id = ?", (g['id'],), action_desc=f"Suppression groupe '{g['nom_groupe']}'", user_info=tech)
                    st.success("Groupe supprimé !")
                    st.rerun()

    with col_g2:
        st.subheader("2️⃣ Membres / Employés")
        df_eq_disp = load_table('equipes')
        if not df_eq_disp.empty:
            with st.form("form_emp"):
                nom_emp = st.text_input("Nom et Prénom")
                role_emp = st.text_input("Rôle (ex: Ouvrier, Mécanicien)")
                grp_emp = st.selectbox("Groupe assigné", df_eq_disp['nom_groupe'].tolist())
                tarif = st.number_input("Tarif journalier (FCFA)", min_value=0.0, value=2500.0)
                if st.form_submit_button("Ajouter l'Employé", use_container_width=True):
                    if nom_emp.strip():
                        execute_query("INSERT INTO employes (nom, role, groupe_nom, tarif_journalier) VALUES (?, ?, ?, ?)", (nom_emp.strip(), role_emp.strip(), grp_emp, tarif), action_desc=f"Ajout employé '{nom_emp}'", user_info=tech)
                        st.success("✅ Employé ajouté !")
                        st.rerun()
        
        df_emp_list = load_table('employes')
        if not df_emp_list.empty:
            st.markdown("---")
            st.write("**Liste des employés :**")
            for _, emp in df_emp_list.iterrows():
                ce1, ce2 = st.columns([3, 1])
                ce1.write(f"👤 **{emp['nom']}** ({emp['role']})")
                if ce2.button("🗑️", key=f"del_emp_{emp['id']}"):
                    execute_query("DELETE FROM employes WHERE id = ?", (emp['id'],), action_desc=f"Suppression employé '{emp['nom']}'", user_info=tech)
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
                
                df_emp_filtre = df_emp[df_emp['groupe_nom'].isin(groupes_selectionnes)] if groupes_selectionnes else df_emp
                
                lignes = [{
                    "Présent": True, 
                    "Employé": f"{e['nom']} - {e['role']}", 
                    "Groupe": e['groupe_nom'], 
                    "Tâche": tache_globale, 
                    "Heures": 8.0, 
                    "Remarque": ""
                } for _, e in df_emp_filtre.iterrows()]
                
                edited = st.data_editor(pd.DataFrame(lignes), hide_index=True, use_container_width=True)
                if st.form_submit_button("💾 Enregistrer le Pointage Global", use_container_width=True, type="primary"):
                    for _, r in edited.iterrows():
                        if r["Présent"]:
                            execute_query(
                                "INSERT INTO pointage (date, employe_nom, groupe_nom, champ_nom, statut_presence, tache_effectuee, heures_travaillees, remarque) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                (str(date_p), r["Employé"], r["Groupe"], champ_selectionne, "Présent", r["Tâche"], float(r["Heures"]), str(r["Remarque"])),
                                action_desc=f"Pointage de {r['Employé']} sur {champ_selectionne}",
                                user_info=tech
                            )
                    st.success("✅ Pointage enregistré avec succès !")
                    st.rerun()

        st.markdown("---")
        st.subheader("📜 Historique des pointages de la parcelle (avec suppression)")
        df_pts = load_table('pointage')
        # Correction stricte : Filtrage rigoureux par champ_nom pour éviter d'afficher tous les pointages de la base
        df_pts_champ = df_pts[df_pts['champ_nom'].astype(str).str.strip().str.lower() == str(champ_selectionne).strip().lower()] if not df_pts.empty and 'champ_nom' in df_pts.columns else pd.DataFrame()
        
        if not df_pts_champ.empty:
            for _, pt in df_pts_champ.iterrows():
                cp1, cp2 = st.columns([4, 1])
                cp1.write(f"📅 {pt['date']} | Groupe: **{pt.get('groupe_nom', 'N/A')}** | Membre: **{pt['employe_nom']}** — Tâche : {pt['tache_effectuee']} ({pt['heures_travaillees']}h)")
                if cp2.button("🗑️ Supprimer", key=f"del_pt_{pt['id']}"):
                    execute_query("DELETE FROM pointage WHERE id = ?", (pt['id'],), action_desc="Suppression d'un pointage", user_info=tech)
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
                execute_query("INSERT INTO taches (champ_id, groupe_id, type_travail, date_tache, heures_travaillees, statut) VALUES (?, 1, ?, ?, ?, 'Planifié')", (champ_id_actif, t_trav, str(d_tache), hrs), action_desc=f"Planification '{t_trav}'", user_info=tech)
                st.success("✅ Planifié !")
                st.rerun()
        
        df_t = load_table('taches')
        df_t_champ = df_t[df_t['champ_id'] == champ_id_actif] if not df_t.empty else pd.DataFrame()
        st.markdown("---")
        st.subheader("Liste des tâches planifiées")
        if not df_t_champ.empty:
            for _, tc in df_t_champ.iterrows():
                ct1, ct2 = st.columns([4, 1])
                ct1.write(f"📌 **{tc['type_travail']}** (Prévu le : {tc['date_tache']} — {tc['heures_travaillees']}h)")
                if ct2.button("🗑️", key=f"del_tc_{tc['id']}"):
                    execute_query("DELETE FROM taches WHERE id = ?", (tc['id'],), action_desc=f"Suppression tâche '{tc['type_travail']}'", user_info=tech)
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
                execute_query("INSERT INTO recoltes (champ_id, culture, date_recolte, quantite_kg, prix_unitaire) VALUES (?, ?, ?, ?, ?)", (champ_id_actif, cult, str(date.today()), qte, pu), action_desc=f"Récolte '{cult}' ({qte} Kg)", user_info=tech)
                st.success("✅ Enregistré !")
                st.rerun()
        
        df_r = load_table('recoltes')
        df_r_champ = df_r[df_r['champ_id'] == champ_id_actif] if not df_r.empty else pd.DataFrame()
        st.markdown("---")
        st.subheader("Historique des récoltes")
        if not df_r_champ.empty:
            for _, rc in df_r_champ.iterrows():
                cr1, cr2 = st.columns([4, 1])
                cr1.write(f"🌾 **{rc['culture']}** : {rc['quantite_kg']} Kg à {rc['prix_unitaire']} FCFA/Kg ({rc['date_recolte']})")
                if cr2.button("🗑️", key=f"del_rc_{rc['id']}"):
                    execute_query("DELETE FROM recoltes WHERE id = ?", (rc['id'],), action_desc="Suppression d'une récolte", user_info=tech)
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
                execute_query("INSERT INTO depenses (champ_id, type, montant, date, facture_nom) VALUES (?, ?, ?, ?, 'Aucune')", (champ_id_actif, motif, mnt, str(date.today())), action_desc=f"Dépense '{motif}' ({mnt} FCFA)", user_info=tech)
                st.success("✅ Dépense enregistrée !")
                st.rerun()
        
        df_d = load_table('depenses')
        df_d_champ = df_d[df_d['champ_id'] == champ_id_actif] if not df_d.empty else pd.DataFrame()
        st.markdown("---")
        st.subheader("Liste des dépenses")
        if not df_d_champ.empty:
            for _, dp in df_d_champ.iterrows():
                cd1, cd2 = st.columns([4, 1])
                cd1.write(f"💸 **{dp['type']}** : {dp['montant']} FCFA ({dp['date']})")
                if cd2.button("🗑️", key=f"del_dp_{dp['id']}"):
                    execute_query("DELETE FROM depenses WHERE id = ?", (dp['id'],), action_desc=f"Suppression dépense '{dp['type']}'", user_info=tech)
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
            execute_query("INSERT INTO intrants (nom, categorie, stock_actuel, unite, seuil_alerte, facture_nom) VALUES (?, ?, ?, ?, 2.0, 'Aucune')", (nom_i, cat_i, stk, unite), action_desc=f"Ajout intrant '{nom_i}'", user_info=tech)
            st.success("✅ Ajouté !")
            st.rerun()
            
    df_i = load_table('intrants')
    st.markdown("---")
    st.subheader("Liste des stocks")
    if not df_i.empty:
        for _, in_t in df_i.iterrows():
            ci1, ci2 = st.columns([4, 1])
            ci1.write(f"📦 **{in_t['nom']}** ({in_t['categorie']}) — Stock : {in_t['stock_actuel']} {in_t['unite']}")
            if ci2.button("🗑️", key=f"del_in_{in_t['id']}"):
                execute_query("DELETE FROM intrants WHERE id = ?", (in_t['id'],), action_desc=f"Suppression intrant '{in_t['nom']}'", user_info=tech)
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
                execute_query("INSERT INTO pluviometrie (champ_id, date, pluie_mm) VALUES (?, ?, ?)", (champ_id_actif, str(date.today()), mm), action_desc=f"Pluviométrie {mm} mm", user_info=tech)
                st.success("✅ Enregistré !")
                st.rerun()
                
        df_plu = load_table('pluviometrie')
        df_plu_champ = df_plu[df_plu['champ_id'] == champ_id_actif] if not df_plu.empty else pd.DataFrame()
        st.markdown("---")
        st.subheader("Historique des relevés pluviométriques")
        if not df_plu_champ.empty:
            for _, plu in df_plu_champ.iterrows():
                cpl1, cpl2 = st.columns([4, 1])
                cpl1.write(f"🌧️ Date : {plu['date']} — **{plu['pluie_mm']} mm**")
                if cpl2.button("🗑️", key=f"del_plu_{plu['id']}"):
                    execute_query("DELETE FROM pluviometrie WHERE id = ?", (plu['id'],), action_desc="Suppression relevé pluviométrique", user_info=tech)
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
                execute_query("INSERT INTO incidents (champ_id, date, description, gravite, action) VALUES (?, ?, ?, ?, 'En attente')", (champ_id_actif, str(date.today()), desc, grav), action_desc=f"Incident ({grav})", user_info=tech)
                st.success("✅ Déclaré !")
                st.rerun()
                
        df_inc = load_table('incidents')
        df_inc_champ = df_inc[df_inc['champ_id'] == champ_id_actif] if not df_inc.empty else pd.DataFrame()
        st.markdown("---")
        st.subheader("Liste des incidents déclarés")
        if not df_inc_champ.empty:
            for _, inc in df_inc_champ.iterrows():
                cin1, cin2 = st.columns([4, 1])
                cin1.write(f"⚠️ [{inc['gravite']}] {inc['date']} : {inc['description']}")
                if cin2.button("🗑️", key=f"del_inc_{inc['id']}"):
                    execute_query("DELETE FROM incidents WHERE id = ?", (inc['id'],), action_desc="Suppression incident", user_info=tech)
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
            execute_query("INSERT INTO materiel (nom_equipement, categorie, statut_marche, date_derniere_revision, prochaine_revision) VALUES (?, ?, ?, ?, ?)", (nom_eq, cat_eq, stat_m, str(d_rev), str(p_rev)), action_desc=f"Ajout matériel '{nom_eq}'", user_info=tech)
            st.success("✅ Ajouté !")
            st.rerun()
            
    df_mat = load_table('materiel')
    st.markdown("---")
    st.subheader("Parc matériel")
    if not df_mat.empty:
        for _, mat in df_mat.iterrows():
            cmat1, cmat2 = st.columns([4, 1])
            cmat1.write(f"🚜 **{mat['nom_equipement']}** ({mat['categorie']}) — Statut : {mat['statut_marche']}")
            if cmat2.button("🗑️", key=f"del_mat_{mat['id']}"):
                execute_query("DELETE FROM materiel WHERE id = ?", (mat['id'],), action_desc=f"Suppression matériel '{mat['nom_equipement']}'", user_info=tech)
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
                    execute_query("INSERT INTO tracabilite (champ_id, lot_code, culture, date_recolte, norme_certification, acheteur) VALUES (?, ?, ?, ?, ?, ?)", (champ_id_actif, lot.strip(), cult_tr, str(date.today()), norme, acheteur), action_desc=f"Lot '{lot}'", user_info=tech)
                    st.success("✅ Lot enregistré !")
                    st.rerun()
                    
        df_trac = load_table('tracabilite')
        df_trac_champ = df_trac[df_trac['champ_id'] == champ_id_actif] if not df_trac.empty else pd.DataFrame()
        st.markdown("---")
        st.subheader("Lots enregistrés")
        if not df_trac_champ.empty:
            for _, tr in df_trac_champ.iterrows():
                ctr1, ctr2 = st.columns([4, 1])
                ctr1.write(f"🏷️ **{tr['lot_code']}** ({tr['culture']}) — Acheteur : {tr['acheteur']}")
                if ctr2.button("🗑️", key=f"del_tr_{tr['id']}"):
                    execute_query("DELETE FROM tracabilite WHERE id = ?", (tr['id'],), action_desc=f"Suppression lot '{tr['lot_code']}'", user_info=tech)
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
                execute_query("INSERT INTO irrigation (champ_id, date, volume_eau_m3, methode, duree_heures) VALUES (?, ?, ?, ?, ?)", (champ_id_actif, str(date.today()), vol_eau, methode, duree), action_desc=f"Irrigation {vol_eau}m3", user_info=tech)
                st.success("✅ Enregistré !")
                st.rerun()
                
        df_irrig = load_table('irrigation')
        df_irrig_champ = df_irrig[df_irrig['champ_id'] == champ_id_actif] if not df_irrig.empty else pd.DataFrame()
        st.markdown("---")
        st.subheader("Historique des irrigations")
        if not df_irrig_champ.empty:
            for _, ir in df_irrig_champ.iterrows():
                cir1, cir2 = st.columns([4, 1])
                cir1.write(f"💧 {ir['date']} — **{ir['volume_eau_m3']} m³** ({ir['methode']}, {ir['duree_heures']}h)")
                if cir2.button("🗑️", key=f"del_ir_{ir['id']}"):
                    execute_query("DELETE FROM irrigation WHERE id = ?", (ir['id'],), action_desc="Suppression irrigation", user_info=tech)
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
                execute_query("INSERT INTO alertes_meteo (champ_id, date, type_risque, niveau_alerte, recommandation_ts) VALUES (?, ?, ?, ?, ?)", (champ_id_actif, str(date.today()), risque, niveau, reco), action_desc=f"Alerte '{risque}'", user_info=tech)
                st.success("✅ Alerte enregistrée !")
                st.rerun()
                
        df_meteo = load_table('alertes_meteo')
        df_meteo_champ = df_meteo[df_meteo['champ_id'] == champ_id_actif] if not df_meteo.empty else pd.DataFrame()
        st.markdown("---")
        st.subheader("Alertes météo enregistrées")
        if not df_meteo_champ.empty:
            for _, alt in df_meteo_champ.iterrows():
                cal1, cal2 = st.columns([4, 1])
                cal1.write(f"🌤️ [{alt['niveau_alerte']}] **{alt['type_risque']}** ({alt['date']}) — {alt['recommandation_ts']}")
                if cal2.button("🗑️", key=f"del_alt_{alt['id']}"):
                    execute_query("DELETE FROM alertes_meteo WHERE id = ?", (alt['id'],), action_desc="Suppression alerte météo", user_info=tech)
                    st.success("Alerte supprimée !")
                    st.rerun()
        else:
            st.info("Aucune alerte enregistrée.")

elif menu == "📈 Rentabilité & ROI":
    st.title(f"📈 Rentabilité & ROI — {champ_selectionne} (Espace Gestionnaire)")
    if champ_id_actif:
        df_d = load_table('depenses')
        df_r = load_table('recoltes')
        df_d_champ = df_d[df_d['champ_id'] == champ_id_actif] if not df_d.empty else pd.DataFrame()
        df_r_champ = df_r[df_r['champ_id'] == champ_id_actif] if not df_r.empty else pd.DataFrame()
        
        total_dep = df_d_champ['montant'].sum() if not df_d_champ.empty else 0
        total_rec = (df_r_champ['quantite_kg'] * df_r_champ['prix_unitaire']).sum() if not df_r_champ.empty else 0
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
    emails_disponibles = df_users_wl['email'].tolist() if not df_users_wl.empty else []
    
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
        
        champ_concerne = st.selectbox("Parcelle liée (Optionnel) :", ["Aucune"] + (list(db_champs['nom'].values) if not db_champs.empty else []))
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
                    
                    execute_query(
                        "INSERT INTO messages_workspace (auteur, email, role, destinataire, destinataire_email, priorite, texte, date_heure, type_contenu, fichier_path, nom_fichier, champ_concerne) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (auteur_complet, email_connecte, role_tech, destinataire, destinataire_email, priorite, texte_message.strip(), date_heure_actuelle, type_contenu, fichier_path, nom_fichier, champ_concerne),
                        action_desc=f"Publication workspace ({type_contenu}) pour {destinataire} ({destinataire_email}) [Expéditeur: {email_connecte}]",
                        user_info=tech
                    )
                    st.success(f"✅ Publication validée et partagée avec succès depuis l'e-mail **{email_connecte}** vers **{destinataire}** ({destinataire_email if destinataire_email else 'Global'}) !")
                    st.rerun()
                else:
                    st.warning("⚠️ Veuillez saisir un message ou joindre un fichier.")

    st.divider()
    st.subheader("📜 Fil d'actualité, Médias, Rapports & Consignes de l'Exploitation (avec suppression)")
    df_messages = load_table('messages_workspace')
    if not df_messages.empty:
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
                    execute_query("DELETE FROM messages_workspace WHERE id = ?", (m_id,), action_desc="Suppression publication workspace", user_info=tech)
                    st.success("Publication supprimée !")
                    st.rerun()
    else:
        st.info("Aucun contenu dans l'espace de travail.")

elif menu == "📜 Historique":
    st.title("📜 Historique des Modifications (Espace Administration)")
    df_h = load_table('historique_modifications')
    # Correction stricte : Filtrage optionnel ou affichage complet propre et clair ordonné du plus récent au plus ancien
    st.dataframe(df_h.iloc[::-1].reset_index(drop=True) if not df_h.empty else df_h, use_container_width=True)

elif menu == "🔐 Paramètres & Liste Blanche":
    st.title("🔐 Paramètres & Liste Blanche (Espace Administration)")
    with st.form("form_add_user"):
        st.subheader("Ajouter un nouvel utilisateur / rôle")
        mail_new = st.text_input("E-mail professionnel")
        pwd_new = st.text_input("Mot de passe", type="password")
        prenom_new = st.text_input("Prénom")
        nom_new = st.text_input("Nom")
        role_new = st.selectbox("Rôle attribué", ["Administration", "Gestionnaire", "Technicien"])
        if st.form_submit_button("Enregistrer l'utilisateur", use_container_width=True):
            if mail_new.strip():
                execute_query("INSERT INTO whitelist_users (email, password, prenom, nom, role, modules_autorises) VALUES (?, ?, ?, ?, ?, 'TOUS')", (mail_new.strip().lower(), pwd_new, prenom_new, nom_new, role_new), action_desc=f"Ajout utilisateur {mail_new}", user_info=tech)
                st.success("✅ Utilisateur ajouté avec succès !")
                st.rerun()
                
    st.markdown("---")
    st.subheader("Utilisateurs autorisés (avec suppression)")
    df_wl = load_table('whitelist_users')
    if not df_wl.empty:
        for _, usr in df_wl.iterrows():
            cu1, cu2 = st.columns([4, 1])
            cu1.write(f"👤 **{usr['prenom']} {usr['nom']}** ({usr['email']}) — Rôle : **{usr['role']}**")
            if usr['email'].lower() != "issayoume2012@gmail.com":
                if cu2.button("🗑️ Supprimer", key=f"del_usr_{usr['id']}"):
                    execute_query("DELETE FROM whitelist_users WHERE id = ?", (usr['id'],), action_desc=f"Suppression utilisateur '{usr['email']}'", user_info=tech)
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
                
                execute_query(
                    "INSERT INTO messages_workspace (auteur, email, role, destinataire, destinataire_email, priorite, texte, date_heure, type_contenu, fichier_path, nom_fichier, champ_concerne) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (auteur_complet, email_connecte, role_tech, "Tous", "", "Important ⚠️", f"Rapport technique officiel généré pour la parcelle {champ_selectionne}.", date_heure_actuelle, "Rapport PDF", f_path, nom_fic_pdf, champ_selectionne),
                    action_desc=f"Archivage rapport PDF {champ_selectionne} dans workspace",
                    user_info=tech
                )
                st.success("✅ Rapport envoyé et archivé avec succès dans l'Espace Collaboration & Workspace !")
    else:
        st.warning("⚠️ Veuillez sélectionner une parcelle active valide pour générer le rapport.")
