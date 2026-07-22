import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, date
import io
import qrcode

# Cartographie dynamique interactive
import folium
from streamlit_folium import st_folium

# Exports PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# 0. INITIALISATION DOSSIER & BASE DE DONNÉES (SQLITE MULTI-UTILISATEURS)
# ==========================================
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

DB_FILE = "agri_database.db"

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Table Techniciens / Utilisateurs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_tech (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT, prenom TEXT, gmail TEXT UNIQUE, phone TEXT, matricule TEXT, password TEXT, sync_gdocs INTEGER
    )""")
    
    # Tables liées à l'utilisateur via user_id
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_champs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        nom TEXT, superficie_ha REAL, latitude REAL, longitude REAL, culture_actuelle TEXT, statut TEXT, icone_lieu TEXT
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_equipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        nom_groupe TEXT, chef_groupe TEXT, membres TEXT
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_employes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        nom TEXT, role TEXT, groupe_id INTEGER, tarif_journalier REAL, photo_chemin TEXT, matricule_emp TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_pointage (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        date TEXT, employe_nom TEXT, groupe_nom TEXT, champ_nom TEXT, statut_presence TEXT,
        heure_arrivee TEXT, heure_depart TEXT, heures_effectives REAL, remarque TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_taches (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        champ_id INTEGER, groupe_id INTEGER, type_travail TEXT, date_tache TEXT, heures_travaillees REAL, statut TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_recoltes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        champ_id INTEGER, culture TEXT, date_recolte TEXT, quantite_kg REAL, prix_unitaire REAL
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_depenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        champ_id INTEGER, type TEXT, montant REAL, date TEXT, facture_chemin TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_intrants (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        nom TEXT, categorie TEXT, stock_actuel REAL, unite TEXT, seuil_alerte REAL, facture_chemin TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_pluviometrie (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        champ_id INTEGER, date TEXT, pluie_mm REAL
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        champ_id INTEGER, date TEXT, description TEXT, gravite TEXT, action TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_materiel (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        nom_equipement TEXT, categorie TEXT, statut_marche TEXT, date_derniere_revision TEXT, prochaine_revision TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_tracabilite (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        lot_code TEXT, champ_nom TEXT, culture TEXT, date_recolte TEXT, norme_certification TEXT, acheteur TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_irrigation (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        champ_nom TEXT, date TEXT, volume_eau_m3 REAL, methode TEXT, duree_heures REAL
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_alertes_meteo (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        date TEXT, type_risque TEXT, niveau_alerte TEXT, recommandation_ts TEXT
    )""")

    # --- TABLES POUR FERMES INTÉGRÉES ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_elevage (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        type_animaux TEXT, race TEXT, quantite INTEGER, date_arrivee TEXT, statut_sanitaire TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_aquaculture (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        nom_bassin TEXT, espece_poisson TEXT, nombre_alvins INTEGER, aliment_kg REAL, ph_eau REAL
    )""")

    conn.commit()
    conn.close()

init_db()

# Fonctions utilitaires SQL
def query_db(query, params=(), one=False):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rv = cursor.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def query_df(query, params=()):
    conn = get_db()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def execute_db(query, params=()):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

# ==========================================
# 1. CONFIGURATION DE LA PAGE
# ==========================================
st.set_page_config(
    page_title="AgriGestion Pro - Système Intégré",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. AUTHENTIFICATION DYNAMIQUE SECURISEE (MULTI-COMPTES)
# ==========================================
if "user" not in st.session_state:
    st.session_state.user = None

def auth_system():
    if st.session_state.user is None:
        tab_login, tab_register = st.tabs(["🔒 Connexion", "📝 Créer un Compte Ferme/Technicien"])

        with tab_login:
            st.subheader("Connexion à votre Espace")
            gmail_in = st.text_input("Adresse Email (Gmail)", key="login_email")
            pwd_in = st.text_input("Mot de passe", type="password", key="login_pwd")
            
            if st.button("Se Connecter", use_container_width=True):
                user = query_db("SELECT * FROM me_tech WHERE gmail = ? AND password = ?", (gmail_in, pwd_in), one=True)
                if user:
                    st.session_state.user = dict(user)
                    st.success(f"Bienvenue, {user['prenom']} !")
                    st.rerun()
                else:
                    st.error("❌ Email ou mot de passe incorrect.")

        with tab_register:
            st.subheader("Inscription Nouvel Utilisateur")
            with st.form("form_reg"):
                col1, col2 = st.columns(2)
                with col1:
                    nom = st.text_input("Nom *")
                    prenom = st.text_input("Prénom *")
                    gmail = st.text_input("Email / Gmail *")
                    phone = st.text_input("Téléphone")
                with col2:
                    matricule = st.text_input("Code/Matricule Exploitation", value="FERME-01")
                    password = st.text_input("Mot de passe *", type="password")
                    sync_gdocs = st.checkbox("Activer la synchronisation Google Drive", value=True)

                if st.form_submit_button("S'inscrire"):
                    if not nom or not prenom or not gmail or not password:
                        st.error("❌ Remplissez tous les champs obligatoires.")
                    else:
                        try:
                            execute_db("""
                                INSERT INTO me_tech (nom, prenom, gmail, phone, matricule, password, sync_gdocs)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (nom, prenom, gmail, phone, matricule, password, 1 if sync_gdocs else 0))
                            st.success("✅ Compte créé avec succès ! Connectez-vous.")
                        except sqlite3.IntegrityError:
                            st.error("❌ Cet email est déjà utilisé par un autre compte.")
        return False
    return True

if not auth_system():
    st.stop()

USER_ID = st.session_state.user['id']
tech_row = st.session_state.user

# ==========================================
# 3. GENERATION CARTE PRO & QR CODE EMPLOYÉ
# ==========================================
def generate_qr_code(data_string):
    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    qr.add_data(data_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def generate_employee_badge(emp_row):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(250, 380), rightMargin=10, leftMargin=10, topMargin=10, bottomMargin=10)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('BadgeTitle', parent=styles['Heading1'], fontSize=12, alignment=1, textColor=colors.HexColor('#10b981'))
    text_style = ParagraphStyle('BadgeText', parent=styles['Normal'], fontSize=9, alignment=1)

    elements.append(Paragraph(f"<b>{tech_row['nom'].upper()} EXPLOITATION</b>", title_style))
    elements.append(Spacer(1, 5))

    # Photo employé
    if emp_row['photo_chemin'] and os.path.exists(emp_row['photo_chemin']):
        elements.append(RLImage(emp_row['photo_chemin'], width=70, height=70))
    else:
        elements.append(Paragraph("[Pas de Photo]", text_style))

    elements.append(Spacer(1, 5))
    elements.append(Paragraph(f"<b>{emp_row['nom']}</b>", ParagraphStyle('Name', fontSize=11, alignment=1)))
    elements.append(Paragraph(f"Rôle: {emp_row['role']}", text_style))
    elements.append(Paragraph(f"ID: {emp_row['matricule_emp']}", text_style))
    elements.append(Spacer(1, 5))

    # QR Code
    qr_data = f"EMP_ID:{emp_row['id']}|NOM:{emp_row['nom']}|ROLE:{emp_row['role']}"
    qr_bytes = generate_qr_code(qr_data)
    qr_img = io.BytesIO(qr_bytes)
    elements.append(RLImage(qr_img, width=80, height=80))

    doc.build(elements)
    return buffer.getvalue()

# ==========================================
# 4. BARRE LATÉRALE
# ==========================================
with st.sidebar:
    st.markdown("### 👨‍🌾 Session Active")
    st.markdown(f"**{tech_row['prenom']} {tech_row['nom']}**")
    st.caption(f"📧 {tech_row['gmail']}")
    
    st.divider()
    
    menu = st.radio("Navigation", [
        "📊 Tableau de Bord",
        "🌱 Cartographie & Parcelles",
        "👥 Groupes & Membres (avec Carte QR)",
        "⏰ Pointage des Horaires",
        "🐓 Élevage & Bétail (Ferme Intégrée)",
        "🐟 Aquaculture / Pisciculture",
        "📅 Planning & Travaux",
        "🌾 Récoltes & Rendements",
        "💰 Finances & Marges",
        "📦 Stocks d'Intrants",
        "🚜 Maintenance Matériel"
    ])
    
    st.divider()
    
    champs_df = query_df("SELECT * FROM me_champs WHERE user_id = ?", (USER_ID,))
    if not champs_df.empty:
        liste_champs = {row['nom']: (row['id'], row['latitude'], row['longitude']) for _, row in champs_df.iterrows()}
        
        if "selected_parcelle_name" not in st.session_state or st.session_state.selected_parcelle_name not in liste_champs:
            st.session_state.selected_parcelle_name = list(liste_champs.keys())[0]

        champ_selectionne = st.selectbox(
            "📍 Parcelle Active :", 
            list(liste_champs.keys()),
            index=list(liste_champs.keys()).index(st.session_state.selected_parcelle_name)
        )
        st.session_state.selected_parcelle_name = champ_selectionne
        champ_id_actif, champ_lat_actif, champ_lon_actif = liste_champs[champ_selectionne]
    else:
        champ_id_actif, champ_lat_actif, champ_lon_actif = None, 16.0300, -16.4800
        champ_selectionne = "Aucune parcelle"

    if st.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.user = None
        st.rerun()

# ==========================================
# 5. MODULES APPLICATION
# ==========================================

# --- A. TABLEAU DE BORD ---
if menu == "📊 Tableau de Bord":
    st.title("📊 Tableau de Bord de l'Exploitation")
    
    m1, m2, m3, m4 = st.columns(4)
    tot_surf = query_db("SELECT SUM(superficie_ha) as total FROM me_champs WHERE user_id = ?", (USER_ID,), one=True)['total'] or 0
    tot_ouv = query_db("SELECT COUNT(*) as total FROM me_employes WHERE user_id = ?", (USER_ID,), one=True)['total'] or 0
    tot_animaux = query_db("SELECT SUM(quantite) as total FROM me_elevage WHERE user_id = ?", (USER_ID,), one=True)['total'] or 0
    tot_rec = query_db("SELECT SUM(quantite_kg) as total FROM me_recoltes WHERE user_id = ?", (USER_ID,), one=True)['total'] or 0
    
    m1.metric("Superficie Totale", f"{tot_surf:.2f} Ha")
    m2.metric("Effectif Personnel", f"{tot_ouv}")
    m3.metric("Têtes de Bétail / Volaille", f"{tot_animaux}")
    m4.metric("Récoltes Cumulées", f"{tot_rec/1000:.2f} T")
    
    st.divider()
    st.subheader("📍 Vos Parcelles")
    st.dataframe(champs_df[["nom", "superficie_ha", "culture_actuelle", "statut"]], use_container_width=True)

# --- B. CARTOGRAPHIE & HISTORIQUE ---
elif menu == "🌱 Cartographie & Parcelles":
    st.title("🌱 Cartographie & Historique des Parcelles")
    tab_map, tab_hist = st.tabs(["🗺️ Carte & Ajout", "📜 Historique"])

    ICON_MAP = {
        "Feuille / Plant": ("leaf", "green"),
        "Eau / Irrigation": ("tint", "blue"),
        "Maison / Dépôt": ("home", "orange"),
        "Alerte / Repère": ("exclamation-sign", "red")
    }

    with tab_map:
        col_map, col_form = st.columns([2, 1])
        with col_map:
            m = folium.Map(location=[champ_lat_actif, champ_lon_actif], zoom_start=14)
            for _, r in champs_df.iterrows():
                icon_key = r['icone_lieu'] if r['icone_lieu'] in ICON_MAP else "Feuille / Plant"
                icon_name, icon_color = ICON_MAP[icon_key]
                folium.Marker(
                    location=[r['latitude'], r['longitude']],
                    popup=r['nom'],
                    icon=folium.Icon(color=icon_color, icon=icon_name)
                ).add_to(m)
            map_data = st_folium(m, width="100%", height=450, key="map_p")
            click_lat = round(map_data["last_clicked"]["lat"], 6) if map_data and map_data.get("last_clicked") else champ_lat_actif
            click_lon = round(map_data["last_clicked"]["lng"], 6) if map_data and map_data.get("last_clicked") else champ_lon_actif

        with col_form:
            with st.form("form_p", clear_on_submit=True):
                nom_p = st.text_input("Nom Parcelle *")
                surf_p = st.number_input("Superficie (Ha)", min_value=0.1, value=1.0)
                lat_p = st.number_input("Lat", value=float(click_lat), format="%.6f")
                lon_p = st.number_input("Lon", value=float(click_lon), format="%.6f")
                cult_p = st.text_input("Culture Principal")
                stat_p = st.selectbox("Statut", ["Préparation", "En croissance", "Récolte"])
                logo_p = st.selectbox("Icône", list(ICON_MAP.keys()))

                if st.form_submit_button("Enregistrer"):
                    execute_db("""
                        INSERT INTO me_champs (user_id, nom, superficie_ha, latitude, longitude, culture_actuelle, statut, icone_lieu)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (USER_ID, nom_p, surf_p, lat_p, lon_p, cult_p, stat_p, logo_p))
                    st.success("Parcelle ajoutée !")
                    st.rerun()

    with tab_hist:
        st.dataframe(champs_df, use_container_width=True)

# --- C. GROUPES, MEMBRES & CARTE QR ---
elif menu == "👥 Groupes & Membres (avec Carte QR)":
    st.title("👥 Gestion du Personnel & Cartes QR Code")
    
    tab_list, tab_add = st.tabs(["📋 Répertoire du Personnel", "➕ Enregistrer un Employé"])

    with tab_list:
        employes = query_df("SELECT * FROM me_employes WHERE user_id = ?", (USER_ID,))
        if employes.empty:
            st.info("Aucun employé enregistré.")
        else:
            for _, emp in employes.iterrows():
                with st.expander(f"👤 {emp['nom']} - {emp['role']} ({emp['matricule_emp']})"):
                    c_img, c_info, c_btn = st.columns([1, 2, 2])
                    with c_img:
                        if emp['photo_chemin'] and os.path.exists(emp['photo_chemin']):
                            st.image(emp['photo_chemin'], width=100)
                        else:
                            st.caption("Aucune photo")
                    with c_info:
                        st.write(f"**Tarif Journalier :** {emp['tarif_journalier']} FCFA")
                        st.write(f"**Code Matricule :** {emp['matricule_emp']}")
                    with c_btn:
                        badge_pdf = generate_employee_badge(emp)
                        st.download_button(
                            "🪪 Imprimer la Carte d'Identité QR",
                            data=badge_pdf,
                            file_name=f"Carte_{emp['nom']}.pdf",
                            mime="application/pdf",
                            key=f"qr_{emp['id']}"
                        )

    with tab_add:
        with st.form("form_emp", clear_on_submit=True):
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                nom_e = st.text_input("Nom & Prénom *")
                role_e = st.text_input("Fonction / Rôle", value="Ouvrier Agricole")
                tarif_e = st.number_input("Tarif Journalier (FCFA)", value=3000)
            with col_e2:
                photo_e = st.file_uploader("📸 Photo de l'employé", type=['jpg', 'jpeg', 'png'])
                mat_e = st.text_input("Matricule Employé", value=f"EMP-{datetime.now().strftime('%M%S')}")

            if st.form_submit_button("Enregistrer l'employé"):
                if nom_e:
                    photo_path = ""
                    if photo_e:
                        photo_path = os.path.join(UPLOAD_DIR, f"emp_{USER_ID}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{photo_e.name}")
                        with open(photo_path, "wb") as f:
                            f.write(photo_e.getbuffer())

                    execute_db("""
                        INSERT INTO me_employes (user_id, nom, role, tarif_journalier, photo_chemin, matricule_emp)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (USER_ID, nom_e, role_e, tarif_e, photo_path, mat_e))
                    st.success("✅ Employé enregistré avec succès !")
                    st.rerun()

# --- D. ÉLEVAGE & BÉTAIL (FERME INTEGRÉE) ---
elif menu == "🐓 Élevage & Bétail (Ferme Intégrée)":
    st.title("🐓 Suivi du Bétail & Aviculture")
    
    st.dataframe(query_df("SELECT * FROM me_elevage WHERE user_id = ?", (USER_ID,)), use_container_width=True)
    
    st.subheader("➕ Entrée / Suivi d'animaux")
    with st.form("form_elevage", clear_on_submit=True):
        col_el1, col_el2 = st.columns(2)
        with col_el1:
            type_anim = st.selectbox("Type d'élevage", ["Bovins (Vaches/Bœufs)", "Oovins (Moutons)", "Caprins (Chèvres)", "Volaille (Poulets)", "Porcins"])
            race = st.text_input("Race / Variété")
            qte = st.number_input("Nombre de têtes", min_value=1, value=10)
        with col_el2:
            date_arr = st.date_input("Date d'intégration", value=date.today())
            statut_san = st.selectbox("Statut Sanitaire", ["Sain / Vacciné", "En Quarantaine", "Traitement en cours"])

        if st.form_submit_button("Ajouter à la ferme"):
            execute_db("""
                INSERT INTO me_elevage (user_id, type_animaux, race, quantite, date_arrivee, statut_sanitaire)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (USER_ID, type_anim, race, qte, str(date_arr), statut_san))
            st.success("Données d'élevage enregistrées !")
            st.rerun()

# --- E. AQUACULTURE / PISCICULTURE ---
elif menu == "🐟 Aquaculture / Pisciculture":
    st.title("🐟 Suivi Aquacole / Bassins")
    
    st.dataframe(query_df("SELECT * FROM me_aquaculture WHERE user_id = ?", (USER_ID,)), use_container_width=True)
    
    with st.form("form_aqua", clear_on_submit=True):
        col_aq1, col_aq2 = st.columns(2)
        with col_aq1:
            bassin = st.text_input("Nom du Bassin", value="Bassin 1")
            espece = st.text_input("Espèce de poisson", value="Tilapia / Clarias")
            alvins = st.number_input("Nombre d'alvéoles/alvins", min_value=0, value=500)
        with col_aq2:
            aliment = st.number_input("Nourriture distribuée (Kg)", min_value=0.0, value=5.0)
            ph = st.number_input("pH de l'eau", min_value=0.0, max_value=14.0, value=7.2)

        if st.form_submit_button("Mettre à jour le bassin"):
            execute_db("""
                INSERT INTO me_aquaculture (user_id, nom_bassin, espece_poisson, nombre_alvins, aliment_kg, ph_eau)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (USER_ID, bassin, espece, alvins, aliment, ph))
            st.success("Bassin mis à jour !")
            st.rerun()

# --- F. FINANCES ---
elif menu == "💰 Finances & Marges":
    st.title("💰 Bilan Financier")
    deps = query_df("SELECT * FROM me_depenses WHERE user_id = ?", (USER_ID,))
    st.dataframe(deps, use_container_width=True)
    
    with st.form("form_dep", clear_on_submit=True):
        motif = st.text_input("Motif Dépense *")
        mnt = st.number_input("Montant (FCFA)", min_value=0)
        if st.form_submit_button("Enregistrer Dépense"):
            execute_db("INSERT INTO me_depenses (user_id, champ_id, type, montant, date) VALUES (?, ?, ?, ?, ?)",
                       (USER_ID, champ_id_actif, motif, mnt, str(date.today())))
            st.rerun()
