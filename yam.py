import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import sqlite3

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

st.markdown("""
    <style>
        .stApp { background-color: #f4f7f6; }
        div.stButton > button { width: 100%; border-radius: 8px; font-weight: 600; padding: 0.5rem 1rem; }
        .main-header { background: white; padding: 15px 20px; border-radius: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
        .card-container { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 15px; }
        @media(max-width: 768px) {
            .stMetric { font-size: 14px !important; }
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. GESTION DE LA BASE DE DONNÉES & CACHE SQLITE
# ==========================================
def get_connection():
    return sqlite3.connect('agrigestion.db', check_same_thread=False)

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
    cursor.execute('''CREATE TABLE IF NOT EXISTS tracabilite (id INTEGER PRIMARY KEY AUTOINCREMENT, lot_code TEXT, champ_nom TEXT, culture TEXT, date_recolte TEXT, norme_certification TEXT, acheteur TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS irrigation (id INTEGER PRIMARY KEY AUTOINCREMENT, champ_nom TEXT, date TEXT, volume_eau_m3 REAL, methode TEXT, duree_heures REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS alertes_meteo (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, type_risque TEXT, niveau_alerte TEXT, recommandation_ts TEXT)''')
    
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
    
    cursor.execute("PRAGMA table_info(whitelist_users)")
    cols_wl = [col[1] for col in cursor.fetchall()]
    if "modules_autorises" not in cols_wl:
        cursor.execute("ALTER TABLE whitelist_users ADD COLUMN modules_autorises TEXT")

    cursor.execute("SELECT COUNT(*) FROM whitelist_users")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO whitelist_users (email, password, prenom, nom, role, modules_autorises) VALUES (?, ?, ?, ?, ?, ?)",
            ("issayoume2012@gmail.com", "issayoume2026", "Issa", "Youme", "Propriétaire", "TOUS")
        )
    else:
        cursor.execute("UPDATE whitelist_users SET modules_autorises = 'TOUS' WHERE email = 'issayoume2012@gmail.com'")

    conn.commit()
    conn.close()

init_db()

@st.cache_data(ttl=60)
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
            (date_act, f"{user_info.get('prenom', '')} {user_info.get('nom', '')}", user_info.get('gmail', ''), user_info.get('role', ''), action_desc, "Mise à jour réussie")
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
                    <p style="text-align: center; color: #6b7280; font-size: 14px; margin-bottom: 25px;">Espace d'authentification sécurisé</p>
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
    elements.append(Paragraph("Cette fiche certifie l'enregistrement de la parcelle dans le système de gestion agricole intégré AgriGestion Pro. Conserver ce document pour le suivi des intrants, des interventions phytosanitaires et des récoltes.", normal_style))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("<i>Document officiel généré automatiquement — Conforme aux normes d'exploitation agricole A4.</i>", ParagraphStyle('Foot', parent=normal_style, fontSize=8, textColor=colors.gray)))
    
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
    df_part = load_table('partage_champs')
    tables_to_export["1. Équipe & Rôles assignés"] = df_part[df_part['champ_nom'] == champ_nom][['technicien_email', 'droit']] if not df_part.empty else pd.DataFrame()

    if champ_id:
        df_pt = load_table('pointage')
        tables_to_export["2. Pointage & Présences"] = df_pt[df_pt['champ_nom'] == champ_nom][['date', 'employe_nom', 'tache_effectuee', 'heures_travaillees']] if not df_pt.empty else pd.DataFrame()
        df_rec = load_table('recoltes')
        tables_to_export["3. Récoltes"] = df_rec[df_rec['champ_id'] == champ_id][['culture', 'date_recolte', 'quantite_kg', 'prix_unitaire']] if not df_rec.empty else pd.DataFrame()
        df_dep = load_table('depenses')
        tables_to_export["4. Dépenses"] = df_dep[df_dep['champ_id'] == champ_id][['type', 'montant', 'date']] if not df_dep.empty else pd.DataFrame()

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
            elements.append(Paragraph("<i>Aucune donnée enregistrée.</i>", normal_style))
        elements.append(Spacer(1, 6))

    doc.build(elements)
    return buffer.getvalue()

# ==========================================
# 5. NAVIGATION & HEADER FLUIDE
# ==========================================
tech = st.session_state.get('registered_tech', {})
prenom_tech = tech.get('prenom', 'Utilisateur')
nom_tech = tech.get('nom', '')
role_tech = tech.get('role', 'Technicien')
email_connecte = tech.get('gmail', '').lower()
modules_autorises_user = tech.get('modules_autorises', 'TOUS')

st.markdown(f"""
    <div class="main-header">
        <div><b>🌾 AgriGestion Pro</b> | <span style="color: #10b981; font-weight: 600;">{prenom_tech} {nom_tech}</span> — Rôle : <b>{role_tech}</b></div>
    </div>
""", unsafe_allow_html=True)

tous_les_menus = [
    "📊 Tableau de Bord",
    "🌱 Cartographie & Parcelles",
    "👥 Groupes & Membres",
    "⏰ Pointage des Horaires",
    "📅 Planning & Travaux",
    "🌾 Récoltes & Rendements",
    "💰 Finances & Marges",
    "📦 Stocks d'Intrants",
    "🌧️ Pluviométrie",
    "⚠️ Incidents",
    "🚜 Maintenance Matériel",
    "🏷️ Traçabilité & Lots",
    "💧 Irrigation & Eau",
    "🌤️ Risques & Météo",
    "📈 Rentabilité & ROI",
    "💬 Espace Collaboration & Meet",
    "📜 Historique",
    "🔐 Paramètres & Liste Blanche",
    "📑 EXPORT RAPPORT PARCELLE"
]

if modules_autorises_user == "TOUS" or email_connecte == "issayoume2012@gmail.com":
    menu_options = tous_les_menus
else:
    menu_options = ["📊 Tableau de Bord", "💬 Espace Collaboration & Meet", "📜 Historique", "📑 EXPORT RAPPORT PARCELLE"]
    liste_mod_autorises = [m.strip() for m in modules_autorises_user.split(",") if m.strip()]
    for m in tous_les_menus:
        if any(mod == m for mod in liste_mod_autorises) and m not in menu_options:
            menu_options.insert(1, m)

col_nav1, col_nav2 = st.columns([3, 1])
with col_nav1:
    menu = st.selectbox("📌 Navigation Principale", menu_options, label_visibility="collapsed")
with col_nav2:
    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

db_champs = load_table('champs')
champ_id_actif = None
champ_selectionne = "Aucune parcelle"

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
            st.session_state.menu_force_carto = True
            st.rerun()

st.divider()

# ==========================================
# 6. MODULES APPLICATIFS ÉPURÉS ET FLUIDES
# ==========================================

if menu == "📊 Tableau de Bord":
    st.title("📊 Tableau de Bord Global")
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
        st.info("👋 Aucune parcelle enregistrée. Rendez-vous dans 'Cartographie & Parcelles' pour en créer une.")
    else:
        st.subheader("📍 Aperçu des Parcelles")
        st.dataframe(df_c[["nom", "superficie_ha", "culture_actuelle", "statut"]], use_container_width=True)

elif menu == "🌱 Cartographie & Parcelles":
    st.title("🌱 Cartographie & Gestion Fluide des Parcelles")
    
    if 'lat_active' not in st.session_state:
        st.session_state['lat_active'] = 14.6937
    if 'lon_active' not in st.session_state:
        st.session_state['lon_active'] = -17.4441

    # Disposition ultra fluide : Formulaire à gauche, Carte interactive intégrée à droite (ou l'inverse)
    col_form, col_map = st.columns([1.1, 1.4], gap="medium")

    with col_form:
        st.markdown("<div class='card-container'>", unsafe_allow_html=True)
        st.subheader("➕ Nouvelle Parcelle & A4")
        st.write("Cliquez sur la carte pour capturer les coordonnées GPS instantanément.")
        
        with st.form("form_champ_fluide"):
            nom_p = st.text_input("Nom de la parcelle *", placeholder="Ex: Champ Sud 02")
            surf_p = st.number_input("Superficie (Ha)", min_value=0.1, value=2.5, step=0.1)
            cult_p = st.text_input("Culture principale", placeholder="Ex: Tomate, Riz...")
            
            # Utilisation des coordonnées issues de la carte interactive
            lat_p = st.number_input("Latitude GPS", value=float(st.session_state['lat_active']), format="%.6f")
            lon_p = st.number_input("Longitude GPS", value=float(st.session_state['lon_active']), format="%.6f")
            
            stat_p = st.selectbox("Statut initial", ["En préparation", "Semé", "En croissance", "Prêt à récolter"])
            pin_p = st.text_input("Code PIN de sécurité (optionnel)", type="password", placeholder="Laisser vide si libre")
            
            st.markdown("<br>", unsafe_allow_html=True)
            submit_parcelle = st.form_submit_button("💾 Enregistrer & Générer le PDF A4", use_container_width=True, type="primary")
            
            if submit_parcelle:
                if nom_p.strip():
                    df_check_exist = load_table('champs')
                    if not df_check_exist.empty and nom_p.strip().lower() in df_check_exist['nom'].str.lower().values:
                        st.error(f"❌ Une parcelle nommée '{nom_p.strip()}' existe déjà.")
                    else:
                        execute_query(
                            "INSERT INTO champs (nom, superficie_ha, latitude, longitude, culture_actuelle, statut, icone_lieu, code_pin) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (nom_p.strip(), surf_p, lat_p, lon_p, cult_p, stat_p, "leaf", pin_p.strip() if pin_p else ""),
                            action_desc=f"Création de la parcelle '{nom_p.strip()}'",
                            user_info=tech
                        )
                        execute_query("INSERT INTO partage_champs (champ_nom, technicien_email, droit) VALUES (?, ?, ?)", (nom_p.strip(), email_connecte, "Propriétaire"))
                        st.success(f"✅ Parcelle **{nom_p.strip()}** enregistrée avec succès !")
                        
                        st.session_state['last_created_pdf'] = export_fiche_parcelle_a4(nom_p.strip(), surf_p, cult_p, lat_p, lon_p, stat_p)
                        st.session_state['last_created_name'] = nom_p.strip()
                else:
                    st.warning("⚠️ Veuillez indiquer un nom de parcelle valide.")
        
        # Téléchargement direct si généré
        if 'last_created_pdf' in st.session_state and 'last_created_name' in st.session_state:
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label=f"📥 Télécharger la Fiche A4 ({st.session_state['last_created_name']})",
                data=st.session_state['last_created_pdf'],
                file_name=f"fiche_a4_{st.session_state['last_created_name']}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_map:
        st.markdown("<div class='card-container'>", unsafe_allow_html=True)
        st.subheader("🗺️ Carte Interactive (Cliquez pour cibler)")
        df_c = load_table('champs')
        
        m = folium.Map(location=[float(st.session_state['lat_active']), float(st.session_state['lon_active'])], zoom_start=13)
        for _, r in df_c.iterrows():
            folium.Marker(
                location=[r['latitude'], r['longitude']],
                popup=f"<b>{r['nom']}</b><br>Culture: {r['culture_actuelle']}<br>Superficie: {r['superficie_ha']} Ha",
                icon=folium.Icon(color="green", icon="leaf")
            ).add_to(m)
            
        map_data = st_folium(m, width="100%", height=420, key="map_interactive_fluid", returned_objects=["last_clicked"])
        if map_data and map_data.get("last_clicked"):
            st.session_state['lat_active'] = round(map_data["last_clicked"]["lat"], 6)
            st.session_state['lon_active'] = round(map_data["last_clicked"]["lng"], 6)
            st.success(f"📍 Coordonnées capturées : {st.session_state['lat_active']}, {st.session_state['lon_active']}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    st.subheader("📋 Liste des Parcelles Enregistrées")
    df_champs_list = load_table('champs')
    if not df_champs_list.empty:
        for _, ch in df_champs_list.iterrows():
            col_li1, col_li2 = st.columns([4, 1])
            with col_li1:
                st.markdown(f"**🌾 {ch['nom']}** — `{ch['superficie_ha']} Ha` | Culture : *{ch['culture_actuelle']}* | Statut : `{ch['statut']}`")
            with col_li2:
                if st.button("🗑️ Supprimer", key=f"del_ch_{ch['id']}"):
                    execute_query("DELETE FROM champs WHERE id = ?", (ch['id'],), action_desc=f"Suppression parcelle '{ch['nom']}'", user_info=tech)
                    st.rerun()
            st.divider()
    else:
        st.info("Aucune parcelle enregistrée pour le moment.")

elif menu == "👥 Groupes & Membres":
    st.title("👥 Groupes & Membres")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("1️⃣ Groupes")
        with st.form("form_grp"):
            nom_g = st.text_input("Nom du groupe")
            chef_g = st.text_input("Chef de groupe")
            if st.form_submit_button("Ajouter le Groupe", use_container_width=True):
                if nom_g.strip():
                    execute_query("INSERT INTO equipes (nom_groupe, chef_groupe) VALUES (?, ?)", (nom_g.strip(), chef_g.strip()), action_desc=f"Création groupe '{nom_g}'", user_info=tech)
                    st.success("✅ Groupe créé !")
                    st.rerun()
        df_g = load_table('equipes')
        if not df_g.empty:
            st.dataframe(df_g, use_container_width=True)

    with col_g2:
        st.subheader("2️⃣ Employés")
        df_eq_disp = load_table('equipes')
        if not df_eq_disp.empty:
            with st.form("form_emp"):
                nom_emp = st.text_input("Nom et Prénom")
                role_emp = st.text_input("Rôle (ex: Ouvrier)")
                grp_emp = st.selectbox("Groupe", df_eq_disp['nom_groupe'].tolist())
                tarif = st.number_input("Tarif journalier (FCFA)", min_value=0.0, value=2500.0)
                if st.form_submit_button("Ajouter l'Employé", use_container_width=True):
                    if nom_emp.strip():
                        execute_query("INSERT INTO employes (nom, role, groupe_nom, tarif_journalier) VALUES (?, ?, ?, ?)", (nom_emp.strip(), role_emp.strip(), grp_emp, tarif), action_desc=f"Ajout employé '{nom_emp}'", user_info=tech)
                        st.success("✅ Employé ajouté !")
                        st.rerun()
        df_e = load_table('employes')
        if not df_e.empty:
            st.dataframe(df_e, use_container_width=True)

elif menu == "⏰ Pointage des Horaires":
    st.title(f"⏰ Pointage des Horaires — {champ_selectionne}")
    if champ_selectionne == "Aucune parcelle":
        st.warning("⚠️ Veuillez sélectionner une parcelle active.")
    else:
        df_emp = load_table('employes')
        if df_emp.empty:
            st.warning("⚠️ Aucun employé enregistré.")
        else:
            date_p = st.date_input("Date du pointage", value=date.today())
            lignes = [{"Présent": True, "Employé": f"{e['nom']} - {e['role']}", "Groupe": e['groupe_nom'], "Tâche": "Travaux", "Heures": 8.0, "Remarque": ""} for _, e in df_emp.iterrows()]
            edited = st.data_editor(pd.DataFrame(lignes), hide_index=True, use_container_width=True)
            if st.button("💾 Enregistrer le Pointage", use_container_width=True, type="primary"):
                for _, r in edited.iterrows():
                    if r["Présent"]:
                        execute_query(
                            "INSERT INTO pointage (date, employe_nom, groupe_nom, champ_nom, statut_presence, tache_effectuee, heures_travaillees, remarque) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (str(date_p), r["Employé"], r["Groupe"], champ_selectionne, "Présent", r["Tâche"], float(r["Heures"]), str(r["Remarque"])),
                            action_desc=f"Pointage de {r['Employé']} ({r['Heures']}h)",
                            user_info=tech
                        )
                st.success("✅ Pointage enregistré !")
                st.rerun()

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
        st.dataframe(df_t[df_t['champ_id'] == champ_id_actif] if not df_t.empty else pd.DataFrame(), use_container_width=True)

elif menu == "🌾 Récoltes & Rendements":
    st.title(f"🌾 Récoltes — {champ_selectionne}")
    if champ_id_actif:
        with st.form("form_rec"):
            cult = st.text_input("Culture")
            qte = st.number_input("Quantité (Kg)", min_value=0.0)
            pu = st.number_input("Prix unitaire (FCFA)", min_value=0.0, value=300.0)
            if st.form_submit_button("Enregistrer", use_container_width=True):
                execute_query("INSERT INTO recoltes (champ_id, culture, date_recolte, quantite_kg, prix_unitaire) VALUES (?, ?, ?, ?, ?)", (champ_id_actif, cult, str(date.today()), qte, pu), action_desc=f"Récolte '{cult}' ({qte} Kg)", user_info=tech)
                st.success("✅ Enregistré !")
                st.rerun()
        df_r = load_table('recoltes')
        st.dataframe(df_r[df_r['champ_id'] == champ_id_actif] if not df_r.empty else pd.DataFrame(), use_container_width=True)

elif menu == "💰 Finances & Marges":
    st.title(f"💰 Finances — {champ_selectionne}")
    if champ_id_actif:
        with st.form("form_fin"):
            motif = st.text_input("Motif de la dépense")
            mnt = st.number_input("Montant (FCFA)", min_value=0.0)
            if st.form_submit_button("Enregistrer", use_container_width=True):
                execute_query("INSERT INTO depenses (champ_id, type, montant, date, facture_nom) VALUES (?, ?, ?, ?, 'Aucune')", (champ_id_actif, motif, mnt, str(date.today())), action_desc=f"Dépense '{motif}' ({mnt} FCFA)", user_info=tech)
                st.success("✅ Dépense enregistrée !")
                st.rerun()
        df_d = load_table('depenses')
        st.dataframe(df_d[df_d['champ_id'] == champ_id_actif] if not df_d.empty else pd.DataFrame(), use_container_width=True)

elif menu == "📦 Stocks d'Intrants":
    st.title("📦 Stocks d'Intrants")
    with st.form("form_int"):
        nom_i = st.text_input("Nom de l'intrant")
        cat_i = st.selectbox("Catégorie", ["Engrais", "Semence", "Pesticide", "Carburant"])
        stk = st.number_input("Stock", min_value=0.0)
        unite = st.text_input("Unité (Sacs, Litres, Kg)")
        if st.form_submit_button("Ajouter", use_container_width=True):
            execute_query("INSERT INTO intrants (nom, categorie, stock_actuel, unite, seuil_alerte, facture_nom) VALUES (?, ?, ?, ?, 2.0, 'Aucune')", (nom_i, cat_i, stk, unite), action_desc=f"Ajout intrant '{nom_i}'", user_info=tech)
            st.success("✅ Ajouté !")
            st.rerun()
    st.dataframe(load_table('intrants'), use_container_width=True)

elif menu == "🌧️ Pluviométrie":
    st.title(f"🌧️ Pluviométrie — {champ_selectionne}")
    if champ_id_actif:
        with st.form("form_plu"):
            mm = st.number_input("Hauteur (mm)", min_value=0.0)
            if st.form_submit_button("Enregistrer", use_container_width=True):
                execute_query("INSERT INTO pluviometrie (champ_id, date, pluie_mm) VALUES (?, ?, ?)", (champ_id_actif, str(date.today()), mm), action_desc=f"Pluviométrie {mm} mm", user_info=tech)
                st.success("✅ Enregistré !")
                st.rerun()
        st.dataframe(load_table('pluviometrie'), use_container_width=True)

elif menu == "⚠️ Incidents":
    st.title(f"⚠️ Incidents — {champ_selectionne}")
    if champ_id_actif:
        with st.form("form_inc"):
            desc = st.text_area("Description")
            grav = st.selectbox("Gravité", ["Faible", "Modéré", "Critique"])
            if st.form_submit_button("Déclarer", use_container_width=True):
                execute_query("INSERT INTO incidents (champ_id, date, description, gravite, action) VALUES (?, ?, ?, ?, 'En attente')", (champ_id_actif, str(date.today()), desc, grav), action_desc=f"Incident ({grav})", user_info=tech)
                st.success("✅ Déclaré !")
                st.rerun()
        st.dataframe(load_table('incidents'), use_container_width=True)

elif menu == "🚜 Maintenance Matériel":
    st.title("🚜 Maintenance Matériel")
    st.dataframe(load_table('materiel'), use_container_width=True)

elif menu == "🏷️ Traçabilité & Lots":
    st.title("🏷️ Traçabilité")
    st.dataframe(load_table('tracabilite'), use_container_width=True)

elif menu == "💧 Irrigation & Eau":
    st.title(f"💧 Irrigation — {champ_selectionne}")
    st.dataframe(load_table('irrigation'), use_container_width=True)

elif menu == "🌤️ Risques & Météo":
    st.title("🌤️ Risques & Météo")
    st.dataframe(load_table('alertes_meteo'), use_container_width=True)

elif menu == "📈 Rentabilité & ROI":
    st.title("📈 Rentabilité & ROI")
    df_d = load_table('depenses')
    df_r = load_table('recoltes')
    total_dep = df_d['montant'].sum() if not df_d.empty else 0
    total_rec = (df_r['quantite_kg'] * df_r['prix_unitaire']).sum() if not df_r.empty else 0
    marge = total_rec - total_dep
    col1, col2, col3 = st.columns(3)
    col1.metric("Dépenses", f"{total_dep:,.0f} FCFA")
    col2.metric("Ventes", f"{total_rec:,.0f} FCFA")
    col3.metric("Marge Nette", f"{marge:,.0f} FCFA")

elif menu == "💬 Espace Collaboration & Meet":
    st.title("💬 Collaboration & Réunions")
    st.link_button("🚀 Ouvrir une réunion Google Meet", "https://meet.google.com/new", use_container_width=True)
    st.divider()
    df_m = load_table('messages_collab')
    if not df_m.empty:
        st.dataframe(df_m, use_container_width=True)
    else:
        st.info("Aucun message.")

elif menu == "📜 Historique":
    st.title("📜 Historique des Modifications")
    df_h = load_table('historique_modifications')
    st.dataframe(df_h.iloc[::-1] if not df_h.empty else df_h, use_container_width=True)

elif menu == "🔐 Paramètres & Liste Blanche":
    st.title("🔐 Paramètres")
    st.dataframe(load_table('whitelist_users'), use_container_width=True)

elif menu == "📑 EXPORT RAPPORT PARCELLE":
    st.title("📑 Export Rapport A4")
    date_exp = st.date_input("Date officielle", value=date.today())
    if champ_selectionne and champ_selectionne != "Aucune parcelle":
        pdf_bytes = export_parcelle_pdf(champ_selectionne, date_exp)
        st.download_button(
            label=f"📥 Télécharger le Rapport A4 de '{champ_selectionne}'",
            data=pdf_bytes,
            file_name=f"rapport_{champ_selectionne}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )
    else:
        st.warning("Sélectionnez une parcelle valide.")
