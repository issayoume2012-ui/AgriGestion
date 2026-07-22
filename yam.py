import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, date
import io
import secrets
import smtplib
from email.mime.text import MIMEText

# Cartographie dynamique
import folium
from streamlit_folium import st_folium

# Exports PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# CONFIGURATION SMTP / MAIL ADMIN
# ==========================================
ADMIN_EMAIL = "issayoume2012@gmail.com"      # Votre e-mail admin
SMTP_SENDER = "issayoume2012@gmail.com"      # Votre e-mail d'envoi
SMTP_PASSWORD = "qwhvzfvheaacdtsp"           # Mot de passe d'application Gmail
APP_URL = "http://localhost:8501"            # Remplacez par votre URL une fois en ligne

# ==========================================
# 0. BASE DE DONNÉES & AUTO-MIGRATION
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
    
    # Table des utilisateurs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_tech (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT, prenom TEXT, gmail TEXT UNIQUE, phone TEXT, matricule TEXT, password TEXT, sync_gdocs INTEGER
    )""")

    # Table Whitelist (E-mails pré-autorisés)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_whitelist_emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        description TEXT,
        date_ajout TEXT
    )""")

    # Table des demandes d'autorisation d'accès (Tokens)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_autorisations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        token TEXT UNIQUE,
        statut TEXT, -- 'EN_ATTENTE', 'APPROUVE', 'REFUSE'
        date_demande TEXT,
        date_decision TEXT
    )""")

    # Table des logs d'accès (Audit Trail / Traçabilité)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_logs_acces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        action TEXT,
        date_evenement TEXT,
        statut TEXT,
        details TEXT
    )""")

    # NOUVEAU: Table Fil de Discussion Commun (Techniciens)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_fil_discussion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auteur_nom TEXT,
        auteur_email TEXT,
        message TEXT,
        type_message TEXT, -- 'INFO', 'ALERTE', 'QUESTION'
        date_envoi TEXT
    )""")

    # NOUVEAU: Table Base de Connaissances & Fiches Techniques Partagées
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_notes_partagees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        auteur_email TEXT,
        auteur_nom TEXT,
        titre TEXT,
        categorie TEXT,
        contenu TEXT,
        date_creation TEXT
    )""")

    # Tables métiers existantes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_champs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        nom TEXT, superficie_ha REAL, latitude REAL, longitude REAL, culture_actuelle TEXT, statut TEXT, icone_lieu TEXT
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_historique_champs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, champ_id INTEGER,
        culture TEXT, date_debut TEXT, date_fin TEXT, rendement_kg REAL, remarques TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_equipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        nom_groupe TEXT, chef_groupe TEXT, membres TEXT
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_employes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        nom TEXT, role TEXT, groupe_id INTEGER, type_contrat TEXT, tarif_journalier REAL, salaire_mensuel REAL, photo_chemin TEXT, matricule_emp TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_pointage (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        date TEXT, employe_nom TEXT, groupe_nom TEXT, champ_nom TEXT, statut_presence TEXT,
        heure_arrivee TEXT, heure_depart TEXT, heures_effectives REAL, remarque TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_materiel (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        nom_materiel TEXT, categorie TEXT, etat TEXT, date_acquisition TEXT, remarques TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_taches (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        champ_id INTEGER, groupe_id INTEGER, employe_id INTEGER, materiel_id INTEGER,
        type_travail TEXT, description TEXT, date_tache TEXT, heures_travaillees REAL, priorite TEXT, statut TEXT
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
    CREATE TABLE IF NOT EXISTS me_elevage (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        type_animaux TEXT, race TEXT, quantite INTEGER, date_arrivee TEXT, statut_sanitaire TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_aquaculture (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        nom_bassin TEXT, espece_poisson TEXT, nombre_alvins INTEGER, aliment_kg REAL, ph_eau REAL
    )""")

    # Ajout automatique de l'admin issayoume2012@gmail.com à la liste blanche
    cursor.execute("INSERT OR IGNORE INTO me_whitelist_emails (email, description, date_ajout) VALUES (?, ?, ?)",
                   (ADMIN_EMAIL, "Administrateur Principal", str(datetime.now())))

    conn.commit()
    conn.close()

init_db()

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
# FONCTIONS DE VALIDATION PAR E-MAIL & AUDIT LOGS
# ==========================================
def log_acces(email, action, statut, details=""):
    execute_db("""
        INSERT INTO me_logs_acces (user_email, action, date_evenement, statut, details)
        VALUES (?, ?, ?, ?, ?)
    """, (email, action, str(datetime.now()), statut, details))

def envoyer_mail_demande_autorisation(user_email, token):
    link_approve = f"{APP_URL}/?action=approve&token={token}"
    link_reject = f"{APP_URL}/?action=reject&token={token}"

    corps_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #10B981;">🔐 Demande d'accès - AgriGestion Pro</h2>
        <p>L'utilisateur <b>{user_email}</b> sollicite une autorisation pour se connecter au système.</p>
        <p><b>Heure de la demande :</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
        <hr style="border: none; border-top: 1px solid #ddd;">
        <p>Cliquez sur l'un des boutons ci-dessous pour valider ou refuser l'accès :</p>
        <p style="margin-top: 20px;">
            <a href="{link_approve}" style="background-color: #10B981; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">🟢 ACCORDER L'ACCÈS</a>
            &nbsp;&nbsp;&nbsp;
            <a href="{link_reject}" style="background-color: #EF4444; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">🔴 REFUSER L'ACCÈS</a>
        </p>
      </body>
    </html>
    """
    
    msg = MIMEText(corps_html, 'html')
    msg['Subject'] = f"🔔 Autorisation d'accès requise pour : {user_email}"
    msg['From'] = SMTP_SENDER
    msg['To'] = ADMIN_EMAIL

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_SENDER, SMTP_PASSWORD)
            server.sendmail(SMTP_SENDER, ADMIN_EMAIL, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Erreur d'envoi d'e-mail : {e}")
        return False

# ==========================================
# 1. CONFIGURATION STYLES STREAMLIT
# ==========================================
st.set_page_config(
    page_title="AgriGestion Pro",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 2rem; padding-left: 1rem; padding-right: 1rem; }
        .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
        @media (max-width: 768px) {
            .stTabs [data-baseweb="tab-list"] { gap: 2px; }
            .stTabs [data-baseweb="tab"] { font-size: 11px; padding: 4px 6px; }
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. TRAITEMENT DES CLICS DANS L'E-MAIL (st.query_params)
# ==========================================
params = st.query_params
if "action" in params and "token" in params:
    act = params["action"]
    tok = params["token"]
    
    req = query_db("SELECT * FROM me_autorisations WHERE token = ?", (tok,), one=True)
    if req:
        if act == "approve":
            execute_db("UPDATE me_autorisations SET statut = 'APPROUVE', date_decision = ? WHERE token = ?", (str(datetime.now()), tok))
            log_acces(req['user_email'], "APPROVAL_EMAIL", "SUCCÈS", f"Autorisé par clic e-mail. Token: {tok}")
            st.success(f"✅ L'accès pour l'utilisateur **{req['user_email']}** a été ACCORDÉ avec succès !")
        elif act == "reject":
            execute_db("UPDATE me_autorisations SET statut = 'REFUSE', date_decision = ? WHERE token = ?", (str(datetime.now()), tok))
            log_acces(req['user_email'], "APPROVAL_EMAIL", "REFUSÉ", f"Refusé par clic e-mail. Token: {tok}")
            st.error(f"❌ L'accès pour l'utilisateur **{req['user_email']}** a été REFUSÉ.")
    else:
        st.warning("⚠️ Jeton de demande invalide ou déjà utilisé.")
    st.stop()

# ==========================================
# 3. AUTHENTIFICATION & SÉCURITÉ
# ==========================================
if "user" not in st.session_state:
    st.session_state.user = None
if "pending_token" not in st.session_state:
    st.session_state.pending_token = None

def auth_system():
    if st.session_state.user is None:
        st.title("🌾 AgriGestion Pro")
        
        # Attente d'approbation par l'administrateur
        if st.session_state.pending_token:
            st.info("⏳ **Demande d'autorisation envoyée à issayoume2012@gmail.com.**")
            st.write("Un e-mail de confirmation a été transmis à l'administrateur. Veuillez attendre la validation ou rafraîchir le statut.")
            
            req = query_db("SELECT * FROM me_autorisations WHERE token = ?", (st.session_state.pending_token,), one=True)
            
            if req:
                if req['statut'] == 'APPROUVE':
                    user = query_db("SELECT * FROM me_tech WHERE gmail = ?", (req['user_email'],), one=True)
                    st.session_state.user = dict(user)
                    st.session_state.pending_token = None
                    log_acces(req['user_email'], "LOGIN", "SUCCÈS", "Accès débloqué suite à la validation e-mail.")
                    st.success("✅ Accès accordé ! Redirection...")
                    st.rerun()
                elif req['statut'] == 'REFUSE':
                    st.error("❌ Votre demande d'accès a été refusée par l'administrateur.")
                    log_acces(req['user_email'], "LOGIN", "REFUSÉ", "Connexion refusée par l'admin.")
                    if st.button("Réessayer"):
                        st.session_state.pending_token = None
                        st.rerun()
                else:
                    st.warning("🔄 Statut : En attente de décision de l'administrateur...")
                    if st.button("🔄 Vérifier si l'accès a été accordé"):
                        st.rerun()
            return False

        # Connexion & Inscription
        tab_login, tab_register = st.tabs(["🔑 Connexion", "📝 Inscription"])

        with tab_login:
            gmail_in = st.text_input("Email", key="l_email").strip().lower()
            pwd_in = st.text_input("Mot de passe", type="password", key="l_pwd")
            
            if st.button("Se Connecter", type="primary"):
                # 1. Vérification dans la Whitelist (Liste Blanche)
                in_whitelist = query_db("SELECT * FROM me_whitelist_emails WHERE email = ?", (gmail_in,), one=True)
                if not in_whitelist:
                    st.error("❌ Accès Refusé : Cet e-mail n'est pas autorisé (absent de la liste blanche).")
                    log_acces(gmail_in, "LOGIN_ATTEMPT", "BLOIQUÉ_WHITELIST", "Non pré-autorisé sur la liste blanche.")
                else:
                    # 2. Vérification des identifiants
                    user = query_db("SELECT * FROM me_tech WHERE gmail = ? AND password = ?", (gmail_in, pwd_in), one=True)
                    if user:
                        # Si c'est l'administrateur principal (issayoume2012@gmail.com), connexion directe
                        if gmail_in == ADMIN_EMAIL.lower():
                            st.session_state.user = dict(user)
                            log_acces(gmail_in, "LOGIN_ADMIN", "SUCCÈS", "Connexion directe administrateur.")
                            st.rerun()
                        else:
                            # 3. Envoi du mail d'autorisation pour les autres utilisateurs
                            token = secrets.token_hex(16)
                            execute_db("""
                                INSERT INTO me_autorisations (user_email, token, statut, date_demande)
                                VALUES (?, ?, 'EN_ATTENTE', ?)
                            """, (gmail_in, token, str(datetime.now())))
                            
                            if envoyer_mail_demande_autorisation(gmail_in, token):
                                st.session_state.pending_token = token
                                log_acces(gmail_in, "DEMANDE_AUTORISATION", "EN_ATTENTE", f"Demande transmise à l'admin. Token: {token}")
                                st.rerun()
                    else:
                        st.error("❌ Email ou mot de passe incorrect.")
                        log_acces(gmail_in, "LOGIN_ATTEMPT", "ÉCHEC", "Mot de passe incorrect.")

        with tab_register:
            with st.form("f_reg"):
                nom = st.text_input("Nom *")
                prenom = st.text_input("Prénom *")
                gmail = st.text_input("Email *").strip().lower()
                password = st.text_input("Mot de passe *", type="password")
                if st.form_submit_button("Créer le compte"):
                    if nom and prenom and gmail and password:
                        in_whitelist = query_db("SELECT * FROM me_whitelist_emails WHERE email = ?", (gmail,), one=True)
                        if not in_whitelist:
                            st.error("❌ Création impossible : L'adresse e-mail doit être préalablement ajoutée à la liste blanche par l'administrateur.")
                        else:
                            try:
                                execute_db("INSERT INTO me_tech (nom, prenom, gmail, password, sync_gdocs) VALUES (?, ?, ?, ?, 1)", (nom, prenom, gmail, password))
                                st.success("✅ Compte créé avec succès ! Vous pouvez maintenant vous connecter.")
                            except sqlite3.IntegrityError:
                                st.error("❌ Cet e-mail a déjà un compte.")
        return False
    return True

if not auth_system():
    st.stop()

USER_ID = st.session_state.user['id']
USER_DATA = st.session_state.user

# ==========================================
# 4. HEADER & NAVIGATION
# ==========================================
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown(f"### 🌾 Exploitation : **{USER_DATA['prenom']} {USER_DATA['nom']}**")
with col_h2:
    if st.button("🚪 Déconnexion"):
        log_acces(USER_DATA['gmail'], "LOGOUT", "SUCCÈS", "Déconnexion manuelle.")
        st.session_state.user = None
        st.session_state.pending_token = None
        st.rerun()

champs_df = query_df("SELECT * FROM me_champs WHERE user_id = ?", (USER_ID,))
if not champs_df.empty:
    liste_champs = {row['nom']: (row['id'], row['latitude'], row['longitude']) for _, row in champs_df.iterrows()}
    if "selected_parcelle_name" not in st.session_state or st.session_state.selected_parcelle_name not in liste_champs:
        st.session_state.selected_parcelle_name = list(liste_champs.keys())[0]

    parcelle_active_nom = st.selectbox("📍 **Parcelle Active :**", list(liste_champs.keys()), index=list(liste_champs.keys()).index(st.session_state.selected_parcelle_name))
    st.session_state.selected_parcelle_name = parcelle_active_nom
    champ_id_actif, champ_lat_actif, champ_lon_actif = liste_champs[parcelle_active_nom]
else:
    champ_id_actif, champ_lat_actif, champ_lon_actif = None, 16.0300, -16.4800
    parcelle_active_nom = "Aucune parcelle"

# Liste des onglets principaux (Ajout de l'Espace Commun Techniciens)
tabs_titles = [
    "📊 TBD", "🤝 Espace Commun Techniciens", "🌱 Parcelles & Historique", "👥 Personnel & Équipes", "⏰ Pointages",
    "📅 Travaux & Matériel", "🐓 Élevage", "🐟 Pisciculture", "🌾 Récoltes", "💰 Finances", "📄 Rapports Automatisés"
]

# Affichage de l'onglet Sécurité uniquement pour issayoume2012@gmail.com
if USER_DATA['gmail'].lower() == ADMIN_EMAIL.lower():
    tabs_titles.append("🛡️ Sécurité & Whitelist")

main_tabs = st.tabs(tabs_titles)

# ==========================================
# GENERATION RAPPORT PDF
# ==========================================
def generate_full_pdf_report(user_data, period_title, filter_month=None, filter_year=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    
    styles = getSampleStyleSheet()
    subtitle_style = ParagraphStyle('CustomSub', parent=styles['Normal'], fontSize=11, leading=14, textColor=colors.HexColor('#4B5563'), spaceAfter=10)

    elements.append(Paragraph("<b>RAPPORT GLOBAL D'EXPLOITATION AUTOMATISÉ</b>", styles['Title']))
    elements.append(Paragraph(f"<b>Période / Titre : {period_title}</b>", subtitle_style))
    elements.append(Paragraph(f"Exploitant : {user_data['prenom']} {user_data['nom']} | Date : {date.today()}", styles['Normal']))
    elements.append(Spacer(1, 10))

    def add_section(title, df):
        elements.append(Paragraph(f"<b>{title}</b>", styles.get('Heading2', styles['Normal'])))
        if not df.empty:
            df_str = df.astype(str)
            data = [list(df_str.columns)] + df_str.values.tolist()
            t = Table(data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#10B981')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTSIZE', (0,0), (-1,-1), 7),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("<i>Aucune donnée enregistrée pour cette période.</i>", styles['Normal']))
        elements.append(Spacer(1, 10))

    month_str = f"{filter_year:04d}-{filter_month:02d}" if (filter_month and filter_year) else None

    add_section("1. Parcelles & Terrains", query_df("SELECT nom, superficie_ha, culture_actuelle, statut FROM me_champs WHERE user_id = ?", (USER_ID,)))
    add_section("2. Personnel & Salaires", query_df("SELECT nom, role, type_contrat, tarif_journalier, salaire_mensuel FROM me_employes WHERE user_id = ?", (USER_ID,)))
    
    if month_str:
        add_section("3. Pointages du Mois", query_df("SELECT date, employe_nom, statut_presence, heures_effectives FROM me_pointage WHERE user_id = ? AND date LIKE ? ORDER BY date DESC", (USER_ID, f"{month_str}%")))
        add_section("4. Tâches du Mois", query_df("SELECT type_travail, description, date_tache, priorite, statut FROM me_taches WHERE user_id = ? AND date_tache LIKE ?", (USER_ID, f"{month_str}%")))
        add_section("5. Récoltes du Mois", query_df("SELECT culture, date_recolte, quantite_kg, prix_unitaire FROM me_recoltes WHERE user_id = ? AND date_recolte LIKE ?", (USER_ID, f"{month_str}%")))
        add_section("6. Dépenses Financières du Mois", query_df("SELECT type, montant, date FROM me_depenses WHERE user_id = ? AND date LIKE ?", (USER_ID, f"{month_str}%")))
    else:
        add_section("3. Derniers Pointages", query_df("SELECT date, employe_nom, statut_presence, heures_effectives FROM me_pointage WHERE user_id = ? ORDER BY date DESC LIMIT 15", (USER_ID,)))
        add_section("4. Tâches & Affectations", query_df("SELECT type_travail, description, date_tache, priorite, statut FROM me_taches WHERE user_id = ?", (USER_ID,)))
        add_section("5. Récoltes", query_df("SELECT culture, date_recolte, quantite_kg, prix_unitaire FROM me_recoltes WHERE user_id = ?", (USER_ID,)))
        add_section("6. Dépenses Financières", query_df("SELECT type, montant, date FROM me_depenses WHERE user_id = ?", (USER_ID,)))

    doc.build(elements)
    return buffer.getvalue()

# ==========================================
# MODULES APPLICATIFS
# ==========================================

# --- TAB 1 : DASHBOARD ---
with main_tabs[0]:
    st.subheader("📊 Aperçu Général de l'Exploitation")
    k1, k2, k3, k4 = st.columns(4)
    surf_tot = query_db("SELECT SUM(superficie_ha) as total FROM me_champs WHERE user_id = ?", (USER_ID,), one=True)['total'] or 0
    emp_tot = query_db("SELECT COUNT(*) as total FROM me_employes WHERE user_id = ?", (USER_ID,), one=True)['total'] or 0
    anim_tot = query_db("SELECT SUM(quantite) as total FROM me_elevage WHERE user_id = ?", (USER_ID,), one=True)['total'] or 0
    rec_tot = query_db("SELECT SUM(quantite_kg) as total FROM me_recoltes WHERE user_id = ?", (USER_ID,), one=True)['total'] or 0
    
    k1.metric("Superficie Totale", f"{surf_tot:.1f} Ha")
    k2.metric("Personnel Actif", f"{emp_tot}")
    k3.metric("Bétail / Animaux", f"{anim_tot}")
    k4.metric("Récoltes Cumulées", f"{rec_tot/1000:.2f} T")
    st.dataframe(champs_df[["nom", "superficie_ha", "culture_actuelle", "statut"]], use_container_width=True)

# --- TAB 2 : ESPACE COMMUN TECHNICIENS (NOUVEAU) ---
with main_tabs[1]:
    st.subheader("🤝 Espace Commun de Collaboration entre Techniciens")
    st.info("💡 Cet espace est partagé en temps réel avec tous les techniciens de la plateforme.")
    
    comm_t1, comm_t2, comm_t3 = st.tabs([
        "💬 Fil d'Actualité & Messagerie", 
        "📚 Base de Connaissances & Fiches", 
        "👥 Annuaire des Techniciens"
    ])

    # Sub-tab 1: Chat/Fil d'actualité partagé
    with comm_t1:
        st.write("#### 📢 Messages, Annonces & Alertes Partagées")
        
        with st.form("f_post_comm", clear_on_submit=True):
            type_m = st.selectbox("Type d'annonce", ["INFO (Information)", "ALERTE (Sanitaire/Météo)", "QUESTION (Besoin d'aide)"])
            msg_comm = st.text_area("Votre message pour l'équipe des techniciens *", placeholder="Ex: Attention invasion d'insectes observée sur le secteur Nord...")
            if st.form_submit_button("Publier sur l'Espace Commun"):
                if msg_comm:
                    nom_auteur = f"{USER_DATA['prenom']} {USER_DATA['nom']}"
                    execute_db("""
                        INSERT INTO me_fil_discussion (auteur_nom, auteur_email, message, type_message, date_envoi)
                        VALUES (?, ?, ?, ?, ?)
                    """, (nom_auteur, USER_DATA['gmail'], msg_comm, type_m, str(datetime.now().strftime('%d/%m/%Y %H:%M'))))
                    st.success("Message publié sur le réseau commun !")
                    st.rerun()

        st.divider()
        st.write("##### 📜 Historique des Échanges")
        fil_df = query_df("SELECT * FROM me_fil_discussion ORDER BY id DESC LIMIT 50")
        if not fil_df.empty:
            for _, row in fil_df.iterrows():
                badge_color = "🔴" if "ALERTE" in str(row['type_message']) else ("🟡" if "QUESTION" in str(row['type_message']) else "🟢")
                with st.expander(f"{badge_color} **{row['auteur_nom']}** - *{row['date_envoi']}* [{row['type_message']}]"):
                    st.write(row['message'])
                    st.caption(f"Auteur : {row['auteur_email']}")
        else:
            st.info("Aucun message publié pour le moment. Soyez le premier à partager une note !")

    # Sub-tab 2: Fiches techniques partagées
    with comm_t2:
        st.write("#### 📖 Centre de Documentation & Fiches Techniques Partagées")
        
        with st.expander("➕ Créer une nouvelle Fiche Technique Partagée"):
            with st.form("f_add_note_comm", clear_on_submit=True):
                t_note = st.text_input("Titre de la Fiche *", placeholder="Ex: Protocole de Fertigation du Maïs")
                cat_note = st.selectbox("Catégorie", ["Irrigation & Sol", "Protection des Cultures", "Élevage & Santé", "Machinisme", "Autre"])
                c_note = st.text_area("Contenu / Procédure technique *", height=200)
                if st.form_submit_button("Enregistrer la Fiche Technique"):
                    if t_note and c_note:
                        nom_auteur = f"{USER_DATA['prenom']} {USER_DATA['nom']}"
                        execute_db("""
                            INSERT INTO me_notes_partagees (auteur_email, auteur_nom, titre, categorie, contenu, date_creation)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (USER_DATA['gmail'], nom_auteur, t_note, cat_note, c_note, str(datetime.now().strftime('%d/%m/%Y'))))
                        st.success("Fiche technique partagée enregistrée !")
                        st.rerun()

        notes_df = query_df("SELECT * FROM me_notes_partagees ORDER BY id DESC")
        if not notes_df.empty:
            for _, r in notes_df.iterrows():
                st.markdown(f"### 📄 {r['titre']} `[{r['categorie']}]`")
                st.caption(f"Rédigé par **{r['auteur_nom']}** ({r['auteur_email']}) le {r['date_creation']}")
                st.markdown(r['contenu'])
                st.divider()
        else:
            st.info("Aucune fiche technique disponible. Partagez votre savoir-faire avec vos collègues !")

    # Sub-tab 3: Annuaire des Techniciens
    with comm_t3:
        st.write("#### 👥 Répertoire des Techniciens de la Plateforme")
        tech_df = query_df("SELECT prenom, nom, gmail, phone, matricule FROM me_tech")
        st.dataframe(tech_df, use_container_width=True)

# --- TAB 3 : PARCELLES ET HISTORIQUE ---
with main_tabs[2]:
    st.subheader("🌱 Gestion des Parcelles & Historique des Cultures")
    p_tab1, p_tab2, p_tab3 = st.tabs(["📍 Carte & Nouvelle Parcelle", "📜 Historique d'une Parcelle", "🔄 Charger / Basculer Parcelle"])

    with p_tab1:
        col_m, col_f = st.columns([2, 1])
        with col_m:
            m = folium.Map(location=[champ_lat_actif, champ_lon_actif], zoom_start=14)
            for _, r in champs_df.iterrows():
                folium.Marker([r['latitude'], r['longitude']], popup=f"{r['nom']} ({r['culture_actuelle']})").add_to(m)
            st_folium(m, width="100%", height=350, key="folium_map")
        with col_f:
            with st.form("form_p", clear_on_submit=True):
                nom_p = st.text_input("Nom Parcelle *")
                surf_p = st.number_input("Superficie (Ha)", min_value=0.1, value=1.0)
                lat_p = st.number_input("Latitude", value=float(champ_lat_actif), format="%.6f")
                lon_p = st.number_input("Longitude", value=float(champ_lon_actif), format="%.6f")
                cult_p = st.text_input("Culture Actuelle")
                stat_p = st.selectbox("Statut", ["Préparation", "Semé", "En Croissance", "En Récolte", "En Friche"])
                if st.form_submit_button("Créer la Parcelle"):
                    if nom_p:
                        execute_db("INSERT INTO me_champs (user_id, nom, superficie_ha, latitude, longitude, culture_actuelle, statut) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   (USER_ID, nom_p, surf_p, lat_p, lon_p, cult_p, stat_p))
                        st.success("Parcelle créée !")
                        st.rerun()

    with p_tab2:
        st.write(f"#### Historique des cultures pour : **{parcelle_active_nom}**")
        with st.expander("➕ Ajouter un enregistrement historique"):
            with st.form("f_hist_add"):
                c_hist = st.text_input("Culture cultivée passée", value="Maïs")
                d_dep = st.date_input("Date Début Plantation", value=date.today())
                d_fin = st.date_input("Date Fin / Récolte", value=date.today())
                rend_h = st.number_input("Rendement obtenu (Kg)", value=0.0)
                rem_h = st.text_area("Remarques / Bilans des intrants")
                if st.form_submit_button("Enregistrer dans l'Historique"):
                    if champ_id_actif:
                        execute_db("""
                            INSERT INTO me_historique_champs (user_id, champ_id, culture, date_debut, date_fin, rendement_kg, remarques)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (USER_ID, champ_id_actif, c_hist, str(d_dep), str(d_fin), rend_h, rem_h))
                        st.success("Historique sauvegardé !")
                        st.rerun()

        hist_df = query_df("SELECT culture, date_debut, date_fin, rendement_kg, remarques FROM me_historique_champs WHERE champ_id = ? AND user_id = ?", (champ_id_actif, USER_ID))
        st.dataframe(hist_df, use_container_width=True)

    with p_tab3:
        st.write("#### 🔄 Charger et Définir la Parcelle Active")
        if not champs_df.empty:
            p_target = st.selectbox("Sélectionner la parcelle à charger :", champs_df['nom'].tolist(), index=list(champs_df['nom']).index(parcelle_active_nom))
            if st.button("🚀 Charger cette Parcelle"):
                st.session_state.selected_parcelle_name = p_target
                st.success(f"Parcelle '{p_target}' chargée avec succès !")
                st.rerun()

# --- TAB 4 : PERSONNEL & ÉQUIPES ---
with main_tabs[3]:
    st.subheader("👥 Gestion du Personnel, Contrats & Équipes")
    sub_t1, sub_t2, sub_t3 = st.tabs(["📋 Liste du Personnel", "➕ Nouvel Employé", "👨‍👩‍👧‍👦 Équipes & Chefs"])

    with sub_t1:
        employes = query_df("SELECT e.*, g.nom_groupe FROM me_employes e LEFT JOIN me_equipes g ON e.groupe_id = g.id WHERE e.user_id = ?", (USER_ID,))
        if not employes.empty:
            st.dataframe(employes[["id", "nom", "role", "type_contrat", "tarif_journalier", "salaire_mensuel", "matricule_emp", "nom_groupe"]], use_container_width=True)
        else:
            st.info("Aucun employé enregistré.")

    with sub_t2:
        equipes = query_df("SELECT * FROM me_equipes WHERE user_id = ?", (USER_ID,))
        dict_eq = {e['nom_groupe']: e['id'] for _, e in equipes.iterrows()} if not equipes.empty else {}
        with st.form("f_add_emp", clear_on_submit=True):
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                n_e = st.text_input("Nom & Prénom *")
                r_e = st.text_input("Rôle / Fonction", value="Ouvrier Agricole")
                m_e = st.text_input("Matricule", value=f"EMP-{datetime.now().strftime('%M%S')}")
                g_e = st.selectbox("Affecter à un groupe", ["Aucun"] + list(dict_eq.keys()))
            with col_e2:
                type_c = st.selectbox("Type de Contrat", ["Journalier", "Mensuel"])
                tarif_j = st.number_input("Tarif par Jour (FCFA)", value=3000 if type_c == "Journalier" else 0)
                sal_m = st.number_input("Salaire Mensuel Fixe (FCFA)", value=75000 if type_c == "Mensuel" else 0)

            if st.form_submit_button("Enregistrer Employé"):
                if n_e:
                    gid = dict_eq[g_e] if g_e != "Aucun" else None
                    execute_db("""
                        INSERT INTO me_employes (user_id, nom, role, type_contrat, tarif_journalier, salaire_mensuel, photo_chemin, matricule_emp, groupe_id) 
                        VALUES (?, ?, ?, ?, ?, ?, '', ?, ?)
                    """, (USER_ID, n_e, r_e, type_c, tarif_j, sal_m, m_e, gid))
                    st.success("Employé créé !")
                    st.rerun()

    with sub_t3:
        col_g1, col_g2 = st.columns([1, 1])
        emp_all = query_df("SELECT * FROM me_employes WHERE user_id = ?", (USER_ID,))
        with col_g1:
            st.write("#### ➕ Créer / Modifier une Équipe")
            with st.form("f_team"):
                nom_g = st.text_input("Nom de l'Équipe *", value="Équipe A")
                chef_g = st.selectbox("Chef de Groupe *", emp_all['nom'].tolist() if not emp_all.empty else ["Aucun"])
                membres_g = st.multiselect("Membres du groupe", emp_all['nom'].tolist() if not emp_all.empty else [])
                if st.form_submit_button("Sauvegarder l'Équipe"):
                    if nom_g:
                        m_str = ", ".join(membres_g)
                        g_id = execute_db("INSERT INTO me_equipes (user_id, nom_groupe, chef_groupe, membres) VALUES (?, ?, ?, ?)", 
                                          (USER_ID, nom_g, chef_g, m_str))
                        if membres_g:
                            for m in membres_g:
                                execute_db("UPDATE me_employes SET groupe_id = ? WHERE nom = ? AND user_id = ?", (g_id, m, USER_ID))
                        st.success("Équipe créée !")
                        st.rerun()

        with col_g2:
            st.write("#### 📜 Équipes Actuelles")
            eq_df = query_df("SELECT * FROM me_equipes WHERE user_id = ?", (USER_ID,))
            st.dataframe(eq_df[["nom_groupe", "chef_groupe", "membres"]], use_container_width=True)

# --- TAB 5 : POINTAGES ---
with main_tabs[4]:
    st.subheader("⏰ Pointage Journalier")
    emp_df = query_df("SELECT * FROM me_employes WHERE user_id = ?", (USER_ID,))
    if not emp_df.empty:
        d_p = st.date_input("Date du pointage", value=date.today())
        grid_data = pd.DataFrame({"Employé": emp_df['nom'], "Contrat": emp_df['type_contrat'], "Présent": True, "Remarque": ""})
        e_grid = st.data_editor(grid_data, use_container_width=True)
        if st.button("Valider les Pointages du Jour", type="primary"):
            for _, r in e_grid.iterrows():
                stt = "Présent" if r["Présent"] else "Absent"
                hrs = 8.0 if r["Présent"] else 0.0
                execute_db("""
                    INSERT INTO me_pointage (user_id, date, employe_nom, champ_nom, statut_presence, heures_effectives, remarque) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (USER_ID, str(d_p), r["Employé"], parcelle_active_nom, stt, hrs, r["Remarque"]))
            st.success("Pointages enregistrés !")
            st.rerun()
            
    st.divider()
    st.dataframe(query_df("SELECT * FROM me_pointage WHERE user_id = ? ORDER BY date DESC", (USER_ID,)), use_container_width=True)

# --- TAB 6 : TRAVAUX & MATÉRIEL ---
with main_tabs[5]:
    st.subheader("📅 Attribution des Tâches & Matériel")
    t_sub1, t_sub2 = st.tabs(["📝 Affecter une Tâche", "🚜 Parc Matériel"])

    equipes_list = query_df("SELECT * FROM me_equipes WHERE user_id = ?", (USER_ID,))
    employes_list = query_df("SELECT * FROM me_employes WHERE user_id = ?", (USER_ID,))
    materiel_list = query_df("SELECT * FROM me_materiel WHERE user_id = ?", (USER_ID,))

    with t_sub1:
        col_t1, col_t2 = st.columns([1, 1])
        with col_t1:
            with st.form("f_assign_task", clear_on_submit=True):
                act_type = st.selectbox("Type de Travail", ["Labour", "Semis", "Désherbage", "Irrigation", "Traitement Phytosanitaire", "Récolte"])
                desc_tache = st.text_area("Description / Consignes")
                mode_assign = st.radio("Cible :", ["Groupe / Équipe", "Ouvrier Individuel"])
                
                target_team, target_emp = None, None
                if mode_assign == "Groupe / Équipe":
                    if not equipes_list.empty:
                        selected_team_nom = st.selectbox("Équipe", equipes_list['nom_groupe'].tolist())
                        target_team = int(equipes_list[equipes_list['nom_groupe'] == selected_team_nom]['id'].values[0])
                else:
                    if not employes_list.empty:
                        selected_emp_nom = st.selectbox("Employé", employes_list['nom'].tolist())
                        target_emp = int(employes_list[employes_list['nom'] == selected_emp_nom]['id'].values[0])

                dict_mat = {m['nom_materiel']: m['id'] for _, m in materiel_list.iterrows()} if not materiel_list.empty else {}
                mat_sel = st.selectbox("Matériel à utiliser", ["Aucun"] + list(dict_mat.keys()))
                target_mat = dict_mat[mat_sel] if mat_sel != "Aucun" else None

                priorite = st.selectbox("Priorité", ["Normale", "Urgente", "Basse"])
                date_tk = st.date_input("Date", value=date.today())
                hrs_tk = st.number_input("Heures estimées", value=4.0)

                if st.form_submit_button("Assigner la Tâche"):
                    if champ_id_actif:
                        execute_db("""
                            INSERT INTO me_taches (user_id, champ_id, groupe_id, employe_id, materiel_id, type_travail, description, date_tache, heures_travaillees, priorite, statut)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'À faire')
                        """, (USER_ID, champ_id_actif, target_team, target_emp, target_mat, act_type, desc_tache, str(date_tk), hrs_tk, priorite))
                        st.success("Tâche assignée !")
                        st.rerun()

        with col_t2:
            tasks_df = query_df("""
                SELECT t.id, t.type_travail, t.description, t.date_tache, t.priorite, t.statut, 
                       g.nom_groupe as equipe, e.nom as employe, m.nom_materiel as materiel
                FROM me_taches t
                LEFT JOIN me_equipes g ON t.groupe_id = g.id
                LEFT JOIN me_employes e ON t.employe_id = e.id
                LEFT JOIN me_materiel m ON t.materiel_id = m.id
                WHERE t.user_id = ? ORDER BY t.date_tache DESC
            """, (USER_ID,))
            st.dataframe(tasks_df, use_container_width=True)

    with t_sub2:
        col_m1, col_m2 = st.columns([1, 1])
        with col_m1:
            with st.form("f_add_mat", clear_on_submit=True):
                nom_m = st.text_input("Nom Matériel *", value="Tracteur John Deere")
                cat_m = st.selectbox("Catégorie", ["Engin Lourd", "Irrigation", "Outil Manuel", "Pulvérisateur", "Autre"])
                etat_m = st.selectbox("État", ["Opérationnel", "En Maintenance", "Hors Service"])
                rem_m = st.text_input("Remarques")
                if st.form_submit_button("Ajouter Matériel"):
                    if nom_m:
                        execute_db("INSERT INTO me_materiel (user_id, nom_materiel, categorie, etat, date_acquisition, remarques) VALUES (?, ?, ?, ?, ?, ?)",
                                   (USER_ID, nom_m, cat_m, etat_m, str(date.today()), rem_m))
                        st.success("Matériel enregistré !")
                        st.rerun()
        with col_m2:
            st.dataframe(materiel_list[["nom_materiel", "categorie", "etat", "remarques"]], use_container_width=True)

# --- TAB 7 : ÉLEVAGE ---
with main_tabs[6]:
    st.subheader("🐓 Suivi de l'Élevage")
    st.dataframe(query_df("SELECT * FROM me_elevage WHERE user_id = ?", (USER_ID,)), use_container_width=True)
    with st.form("f_el"):
        t_a = st.text_input("Type d'animal", value="Volaille / Poulets")
        q_a = st.number_input("Quantité", min_value=1, value=20)
        s_a = st.selectbox("État Sanitaire", ["Sain", "Vacciné", "En Traitement"])
        if st.form_submit_button("Enregistrer Lot"):
            execute_db("INSERT INTO me_elevage (user_id, type_animaux, race, quantite, date_arrivee, statut_sanitaire) VALUES (?, ?, '', ?, ?, ?)",
                       (USER_ID, t_a, q_a, str(date.today()), s_a))
            st.rerun()

# --- TAB 8 : PISCICULTURE ---
with main_tabs[7]:
    st.subheader("🐟 Suivi Piscicole")
    st.dataframe(query_df("SELECT * FROM me_aquaculture WHERE user_id = ?", (USER_ID,)), use_container_width=True)
    with st.form("f_aq"):
        n_b = st.text_input("Bassin", value="Bassin Principale")
        e_p = st.text_input("Espèce", value="Tilapia")
        a_p = st.number_input("Nombre d'alvins", value=500)
        if st.form_submit_button("Enregistrer Bassin"):
            execute_db("INSERT INTO me_aquaculture (user_id, nom_bassin, espece_poisson, nombre_alvins, aliment_kg, ph_eau) VALUES (?, ?, ?, ?, 0, 7.0)",
                       (USER_ID, n_b, e_p, a_p))
            st.rerun()

# --- TAB 9 : RÉCOLTES ---
with main_tabs[8]:
    st.subheader("🌾 Récoltes & Pesées")
    st.dataframe(query_df("SELECT * FROM me_recoltes WHERE user_id = ?", (USER_ID,)), use_container_width=True)
    with st.form("f_rec"):
        c_r = st.text_input("Culture", value="Maïs")
        q_r = st.number_input("Quantité Récoltée (Kg)", value=250.0)
        p_r = st.number_input("Prix de vente estimé / Kg (FCFA)", value=300)
        if st.form_submit_button("Enregistrer Récolte"):
            if champ_id_actif:
                execute_db("INSERT INTO me_recoltes (user_id, champ_id, culture, date_recolte, quantite_kg, prix_unitaire) VALUES (?, ?, ?, ?, ?, ?)",
                           (USER_ID, champ_id_actif, c_r, str(date.today()), q_r, p_r))
                st.rerun()

# --- TAB 10 : FINANCES ---
with main_tabs[9]:
    st.subheader("💰 Suivi Financier & Dépenses")
    col_d1, col_d2 = st.columns([1, 1])
    with col_d1:
        with st.form("f_dep"):
            mot = st.text_input("Motif Dépense")
            mnt = st.number_input("Montant (FCFA)", value=10000)
            if st.form_submit_button("Ajouter Dépense"):
                execute_db("INSERT INTO me_depenses (user_id, champ_id, type, montant, date) VALUES (?, ?, ?, ?, ?)",
                           (USER_ID, champ_id_actif, mot, mnt, str(date.today())))
                st.rerun()
    with col_d2:
        st.dataframe(query_df("SELECT * FROM me_depenses WHERE user_id = ?", (USER_ID,)), use_container_width=True)

# --- TAB 11 : RAPPORTS AUTOMATISÉS ---
with main_tabs[10]:
    st.subheader("📄 Génération Automatique des Rapports")
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        mode_periode = st.radio("Type de Rapport :", ["Global (Toutes données)", "Mensuel Spécifique"])
    
    sel_month, sel_year = None, None
    nom_mois = ""
    if mode_periode == "Mensuel Spécifique":
        with col_filter2:
            c_m, c_y = st.columns(2)
            mois_dict = {"Janvier": 1, "Février": 2, "Mars": 3, "Avril": 4, "Mai": 5, "Juin": 6, "Juillet": 7, "Août": 8, "Septembre": 9, "Octobre": 10, "Novembre": 11, "Décembre": 12}
            with c_m:
                nom_mois = st.selectbox("Mois", list(mois_dict.keys()), index=datetime.now().month - 1)
                sel_month = mois_dict[nom_mois]
            with c_y:
                sel_year = st.number_input("Année", min_value=2020, max_value=2100, value=datetime.now().year)

    month_str = f"{sel_year:04d}-{sel_month:02d}" if (sel_month and sel_year) else None

    st.divider()
    col_rep1, col_rep2 = st.columns(2)

    with col_rep1:
        st.write("### 📊 Exportation Excel")
        if st.button("📊 Générer le Pack Excel"):
            buf_all = io.BytesIO()
            with pd.ExcelWriter(buf_all, engine='openpyxl') as writer:
                query_df("SELECT * FROM me_champs WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Parcelles", index=False)
                query_df("SELECT * FROM me_employes WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Personnel", index=False)
                
                if month_str:
                    query_df("SELECT * FROM me_pointage WHERE user_id = ? AND date LIKE ?", (USER_ID, f"{month_str}%")).to_excel(writer, sheet_name="Pointages", index=False)
                    query_df("SELECT * FROM me_taches WHERE user_id = ? AND date_tache LIKE ?", (USER_ID, f"{month_str}%")).to_excel(writer, sheet_name="Taches", index=False)
                    query_df("SELECT * FROM me_recoltes WHERE user_id = ? AND date_recolte LIKE ?", (USER_ID, f"{month_str}%")).to_excel(writer, sheet_name="Recoltes", index=False)
                    query_df("SELECT * FROM me_depenses WHERE user_id = ? AND date LIKE ?", (USER_ID, f"{month_str}%")).to_excel(writer, sheet_name="Depenses", index=False)
                else:
                    query_df("SELECT * FROM me_pointage WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Pointages", index=False)
                    query_df("SELECT * FROM me_taches WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Taches", index=False)
                    query_df("SELECT * FROM me_recoltes WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Recoltes", index=False)
                    query_df("SELECT * FROM me_depenses WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Depenses", index=False)
            
            st.download_button("📥 Télécharger Excel", data=buf_all.getvalue(), file_name=f"Rapport_AgriGestion_{month_str or 'Global'}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with col_rep2:
        st.write("### 📑 Exportation PDF")
        titre_default = f"Bilan Mensuel ({nom_mois} {sel_year})" if mode_periode == "Mensuel Spécifique" else f"Bilan Global du {date.today()}"
        titre_pdf = st.text_input("Titre du PDF", value=titre_default)
        
        if st.button("📑 Générer le Rapport PDF"):
            pdf_bytes = generate_full_pdf_report(USER_DATA, titre_pdf, filter_month=sel_month, filter_year=sel_year)
            st.download_button("📥 Télécharger PDF", data=pdf_bytes, file_name=f"Rapport_AgriGestion_{month_str or 'Global'}.pdf", mime="application/pdf")

# --- TAB 12 : PANNEAU DE SÉCURITÉ & AUDIT LOGS (Administrateur issayoume2012@gmail.com) ---
if USER_DATA['gmail'].lower() == ADMIN_EMAIL.lower():
    with main_tabs[11]:
        st.subheader("🛡️ Panneau de Sécurité, Liste Blanche & Traçabilité")
        sec_t1, sec_t2, sec_t3 = st.tabs(["📧 Liste Blanche (Whitelist)", "⏳ Demandes d'autorisation", "📜 Journal des d'accès (Audit Trail)"])

        with sec_t1:
            st.write("#### E-mails pré-autorisés à s'inscrire ou se connecter")
            col_w1, col_w2 = st.columns([1, 1])
            with col_w1:
                with st.form("f_add_whitelist", clear_on_submit=True):
                    new_e = st.text_input("Ajouter un e-mail à la Liste Blanche *").strip().lower()
                    desc_e = st.text_input("Description / Rôle", value="Gérant de ferme")
                    if st.form_submit_button("Autoriser cet e-mail"):
                        if new_e:
                            try:
                                execute_db("INSERT INTO me_whitelist_emails (email, description, date_ajout) VALUES (?, ?, ?)", (new_e, desc_e, str(datetime.now())))
                                st.success(f"E-mail {new_e} ajouté avec succès !")
                                st.rerun()
                            except sqlite3.IntegrityError:
                                st.error("Cet e-mail est déjà pré-autorisé.")
            with col_w2:
                wl_df = query_df("SELECT email, description, date_ajout FROM me_whitelist_emails ORDER BY id DESC")
                st.dataframe(wl_df, use_container_width=True)

        with sec_t2:
            st.write("#### Historique des demandes de validation reçues par e-mail")
            aut_df = query_df("SELECT user_email, token, statut, date_demande, date_decision FROM me_autorisations ORDER BY id DESC")
            st.dataframe(aut_df, use_container_width=True)

        with sec_t3:
            st.write("#### Journal d'audit complet (Connexions, Tentatives, Blocages)")
            logs_df = query_df("SELECT * FROM me_logs_acces ORDER BY id DESC LIMIT 100")
            st.dataframe(logs_df, use_container_width=True)
