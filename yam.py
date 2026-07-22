import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, date
import io

# Cartographie dynamique
import folium
from streamlit_folium import st_folium

# Exports PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

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
    
    # Tables principales
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_tech (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT, prenom TEXT, gmail TEXT UNIQUE, phone TEXT, matricule TEXT, password TEXT, sync_gdocs INTEGER
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS me_champs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        nom TEXT, superficie_ha REAL, latitude REAL, longitude REAL, culture_actuelle TEXT, statut TEXT, icone_lieu TEXT
    )""")
    
    # Historique des parcelles
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

    # Gestion du Matériel
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

    # Migrations automatiques
    migrations = {
        "me_employes": [
            ("photo_chemin", "TEXT"), ("matricule_emp", "TEXT"), 
            ("tarif_journalier", "REAL"), ("salaire_mensuel", "REAL"),
            ("type_contrat", "TEXT"), ("groupe_id", "INTEGER")
        ],
        "me_champs": [("icone_lieu", "TEXT")],
        "me_taches": [
            ("groupe_id", "INTEGER"), ("employe_id", "INTEGER"), 
            ("materiel_id", "INTEGER"), ("description", "TEXT"), ("priorite", "TEXT")
        ]
    }

    tables_metier = [
        "me_champs", "me_historique_champs", "me_equipes", "me_employes", "me_pointage", 
        "me_materiel", "me_taches", "me_recoltes", "me_depenses", "me_intrants", 
        "me_elevage", "me_aquaculture"
    ]
    
    for table in tables_metier:
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [c[1] for c in cursor.fetchall()]
        if "user_id" not in cols:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER")
            except sqlite3.OperationalError:
                pass

    for table, columns in migrations.items():
        cursor.execute(f"PRAGMA table_info({table})")
        existing_cols = [c[1] for c in cursor.fetchall()]
        for col_name, col_type in columns:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass

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
# 1. CONFIGURATION ET STYLES
# ==========================================
st.set_page_config(
    page_title="AgriGestion Pro Ultimate",
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
# 2. AUTHENTIFICATION
# ==========================================
if "user" not in st.session_state:
    st.session_state.user = None

def auth_system():
    if st.session_state.user is None:
        st.title("🌾 AgriGestion Pro")
        tab_login, tab_register = st.tabs(["🔑 Connexion", "📝 Inscription"])

        with tab_login:
            gmail_in = st.text_input("Email", key="l_email")
            pwd_in = st.text_input("Mot de passe", type="password", key="l_pwd")
            if st.button("Se Connecter", type="primary"):
                user = query_db("SELECT * FROM me_tech WHERE gmail = ? AND password = ?", (gmail_in, pwd_in), one=True)
                if user:
                    st.session_state.user = dict(user)
                    st.rerun()
                else:
                    st.error("❌ Email ou mot de passe incorrect.")

        with tab_register:
            with st.form("f_reg"):
                nom = st.text_input("Nom *")
                prenom = st.text_input("Prénom *")
                gmail = st.text_input("Email *")
                password = st.text_input("Mot de passe *", type="password")
                if st.form_submit_button("Créer le compte"):
                    if nom and prenom and gmail and password:
                        try:
                            execute_db("INSERT INTO me_tech (nom, prenom, gmail, password, sync_gdocs) VALUES (?, ?, ?, ?, 1)", (nom, prenom, gmail, password))
                            st.success("✅ Compte créé ! Connectez-vous.")
                        except sqlite3.IntegrityError:
                            st.error("❌ Email déjà enregistré.")
        return False
    return True

if not auth_system():
    st.stop()

USER_ID = st.session_state.user['id']
USER_DATA = st.session_state.user

# ==========================================
# 3. HEADER ET NAVIGATION
# ==========================================
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown(f"### 🌾 Exploitation : **{USER_DATA['prenom']} {USER_DATA['nom']}**")
with col_h2:
    if st.button("🚪 Déconnexion"):
        st.session_state.user = None
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

main_tabs = st.tabs([
    "📊 TBD",
    "🌱 Parcelles & Historique",
    "👥 Personnel & Équipes",
    "⏰ Pointages",
    "📅 Travaux & Matériel",
    "🐓 Élevage",
    "🐟 Pisciculture",
    "🌾 Récoltes",
    "💰 Finances",
    "📄 Rapports Automatisés"
])

# ==========================================
# FONCTION D'EXPORTATION AUTOMATISÉE ET COMPLÈTE EN PDF
# ==========================================
def generate_full_pdf_report(user_data, period_title):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(f"<b>RAPPORT GLOBAL D'EXPLOITATION AUTOMATISÉ</b>", styles['Title']))
    elements.append(Paragraph(f"<b>Période / Titre : {period_title}</b>", styles['Subtitle']))
    elements.append(Paragraph(f"Exploitant : {user_data['prenom']} {user_data['nom']} | Date de génération : {date.today()}", styles['Normal']))
    elements.append(Spacer(1, 10))

    def add_section(title, df):
        elements.append(Paragraph(f"<b>{title}</b>", styles['Heading2']))
        if not df.empty:
            # Nettoyage pour affichage PDF
            df_str = df.astype(str)
            data = [list(df_str.columns)] + df_str.values.tolist()
            t = Table(data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#10b981')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTSIZE', (0,0), (-1,-1), 7),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("<i>Aucune donnée enregistrée.</i>", styles['Normal']))
        elements.append(Spacer(1, 10))

    # Importation globale de toutes les tables
    add_section("1. Parcelles & Terrains", query_df("SELECT nom, superficie_ha, culture_actuelle, statut FROM me_champs WHERE user_id = ?", (USER_ID,)))
    add_section("2. Personnel & Salaires", query_df("SELECT nom, role, type_contrat, tarif_journalier, salaire_mensuel FROM me_employes WHERE user_id = ?", (USER_ID,)))
    add_section("3. Derniers Pointages", query_df("SELECT date, employe_nom, statut_presence, heures_effectives FROM me_pointage WHERE user_id = ? ORDER BY date DESC LIMIT 15", (USER_ID,)))
    add_section("4. Tâches & Affectations", query_df("SELECT type_travail, description, date_tache, priorite, statut FROM me_taches WHERE user_id = ?", (USER_ID,)))
    add_section("5. Parc Matériel & Équipements", query_df("SELECT nom_materiel, categorie, etat FROM me_materiel WHERE user_id = ?", (USER_ID,)))
    add_section("6. Récoltes", query_df("SELECT culture, date_recolte, quantite_kg, prix_unitaire FROM me_recoltes WHERE user_id = ?", (USER_ID,)))
    add_section("7. Dépenses Financières", query_df("SELECT type, montant, date FROM me_depenses WHERE user_id = ?", (USER_ID,)))

    doc.build(elements)
    return buffer.getvalue()


# ==========================================
# 4. MODULES DE L'APPLICATION
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

# --- TAB 2 : PARCELLES ET HISTORIQUE ---
with main_tabs[1]:
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
                        st.success("Parcelle ajoutée !")
                        st.rerun()

    with p_tab2:
        st.write(f"#### Historique des cultures pour : **{parcelle_active_nom}**")
        
        # Formulaire d'ajout d'historique
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
        st.info("Sélectionnez une parcelle ci-dessous pour changer la zone d'intervention principale dans l'application.")
        
        if not champs_df.empty:
            p_target = st.selectbox("Sélectionner la parcelle à charger :", champs_df['nom'].tolist(), index=list(champs_df['nom']).index(parcelle_active_nom))
            if st.button("🚀 Charger cette Parcelle"):
                st.session_state.selected_parcelle_name = p_target
                st.success(f"Parcelle '{p_target}' chargée avec succès !")
                st.rerun()

# --- TAB 3 : PERSONNEL & ÉQUIPES ---
with main_tabs[2]:
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
                        st.success("Équipe configurée !")
                        st.rerun()

        with col_g2:
            st.write("#### 📜 Équipes & Chefs Actuels")
            eq_df = query_df("SELECT * FROM me_equipes WHERE user_id = ?", (USER_ID,))
            st.dataframe(eq_df[["nom_groupe", "chef_groupe", "membres"]], use_container_width=True)

# --- TAB 4 : POINTAGES ---
with main_tabs[3]:
    st.subheader("⏰ Pointage Journalier des Travailleurs")
    emp_df = query_df("SELECT * FROM me_employes WHERE user_id = ?", (USER_ID,))
    if not emp_df.empty:
        d_p = st.date_input("Date du pointage", value=date.today())
        grid_data = pd.DataFrame({
            "Employé": emp_df['nom'], 
            "Contrat": emp_df['type_contrat'],
            "Présent": True, 
            "Remarque": ""
        })
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
    st.write("### 📋 Historique des Pointages")
    st.dataframe(query_df("SELECT * FROM me_pointage WHERE user_id = ? ORDER BY date DESC", (USER_ID,)), use_container_width=True)

# --- TAB 5 : ATTRIBUTION DES TRAVAUX & GESTION DU MATÉRIEL ---
with main_tabs[4]:
    st.subheader("📅 Attribution des Travaux & Gestion du Matériel")
    
    t_sub1, t_sub2 = st.tabs(["📝 Affecter / Désigner une Tâche", "🚜 Gestion du Matériel & Équipements"])

    equipes_list = query_df("SELECT * FROM me_equipes WHERE user_id = ?", (USER_ID,))
    employes_list = query_df("SELECT * FROM me_employes WHERE user_id = ?", (USER_ID,))
    materiel_list = query_df("SELECT * FROM me_materiel WHERE user_id = ?", (USER_ID,))

    with t_sub1:
        col_t1, col_t2 = st.columns([1, 1])

        with col_t1:
            st.write("#### ➕ Créer et Attribuer une Tâche")
            with st.form("f_assign_task", clear_on_submit=True):
                act_type = st.selectbox("Type de Travail", ["Labour", "Semis", "Désherbage", "Irrigation", "Traitement Phytosanitaire", "Récolte", "Entretien Matériel"])
                desc_tache = st.text_area("Description & Consignes", value="")
                
                mode_assign = st.radio("Cible d'affectation :", ["Groupe / Équipe", "Ouvrier Individuel"])
                
                target_team = None
                target_emp = None
                
                if mode_assign == "Groupe / Équipe":
                    if not equipes_list.empty:
                        selected_team_nom = st.selectbox("Choisir l'Équipe target", equipes_list['nom_groupe'].tolist())
                        target_team = int(equipes_list[equipes_list['nom_groupe'] == selected_team_nom]['id'].values[0])
                    else:
                        st.warning("⚠️ Aucune équipe disponible.")
                else:
                    if not employes_list.empty:
                        selected_emp_nom = st.selectbox("Choisir l'Employé target", employes_list['nom'].tolist())
                        target_emp = int(employes_list[employes_list['nom'] == selected_emp_nom]['id'].values[0])
                    else:
                        st.warning("⚠️ Aucun employé disponible.")

                # Matériel associé
                dict_mat = {m['nom_materiel']: m['id'] for _, m in materiel_list.iterrows()} if not materiel_list.empty else {}
                mat_sel = st.selectbox("Matériel / Équipement à utiliser", ["Aucun / Manuel"] + list(dict_mat.keys()))
                target_mat = dict_mat[mat_sel] if mat_sel != "Aucun / Manuel" else None

                priorite = st.selectbox("Niveau de Priorité", ["Normale", "Urgente", "Basse"])
                date_tk = st.date_input("Date d'exécution", value=date.today())
                hrs_tk = st.number_input("Durée estimée (Heures)", value=4.0)

                if st.form_submit_button("Assigner la Tâche"):
                    if champ_id_actif:
                        execute_db("""
                            INSERT INTO me_taches (user_id, champ_id, groupe_id, employe_id, materiel_id, type_travail, description, date_tache, heures_travaillees, priorite, statut)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'À faire')
                        """, (USER_ID, champ_id_actif, target_team, target_emp, target_mat, act_type, desc_tache, str(date_tk), hrs_tk, priorite))
                        st.success("✅ Tâche attribuée avec succès !")
                        st.rerun()

        with col_t2:
            st.write("#### 📋 Suivi & Évolution des Tâches")
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
        st.write("#### 🚜 Gestion du Parc Matériel & Outillage")
        
        col_m1, col_m2 = st.columns([1, 1])
        with col_m1:
            with st.form("f_add_mat", clear_on_submit=True):
                nom_m = st.text_input("Nom de l'équipement / Matériel *", value="Tracteur John Deere")
                cat_m = st.selectbox("Catégorie", ["Engin Lourd", "Irrigation / Pompe", "Outil Manuel", "Pulvérisateur", "Autre"])
                etat_m = st.selectbox("État Général", ["Opérationnel", "En Maintenance", "Hors Service"])
                rem_m = st.text_input("Remarques / Maintenance")
                if st.form_submit_button("Ajouter au Parc Matériel"):
                    if nom_m:
                        execute_db("""
                            INSERT INTO me_materiel (user_id, nom_materiel, categorie, etat, date_acquisition, remarques)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (USER_ID, nom_m, cat_m, etat_m, str(date.today()), rem_m))
                        st.success("Matériel enregistré !")
                        st.rerun()
        
        with col_m2:
            st.write("#### 📜 Inventaire du Matériel")
            st.dataframe(materiel_list[["nom_materiel", "categorie", "etat", "remarques"]], use_container_width=True)

# --- TAB 6 : ÉLEVAGE ---
with main_tabs[5]:
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

# --- TAB 7 : PISCICULTURE ---
with main_tabs[6]:
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

# --- TAB 8 : RÉCOLTES ---
with main_tabs[7]:
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

# --- TAB 9 : FINANCES ---
with main_tabs[8]:
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

# --- TAB 10 : RAPPORTS ET EXPORTS AUTOMATISÉS ---
with main_tabs[9]:
    st.subheader("📄 Génération Automatique des Rapports Globaux")
    st.write("Téléchargez l'intégralité des données renseignées dans votre exploitation sous format structuré (PDF ou Excel).")

    st.divider()

    col_rep1, col_rep2 = st.columns(2)

    with col_rep1:
        st.write("### 📊 Exportation Excel Globale")
        st.write("Génère un classeur Excel contenant une feuille pour chaque module de l'application.")
        
        if st.button("📊 Générer le Pack Excel Automatisé"):
            buf_all = io.BytesIO()
            with pd.ExcelWriter(buf_all, engine='openpyxl') as writer:
                query_df("SELECT * FROM me_champs WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Parcelles", index=False)
                query_df("SELECT * FROM me_historique_champs WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Historique Parcelles", index=False)
                query_df("SELECT * FROM me_employes WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Personnel", index=False)
                query_df("SELECT * FROM me_pointage WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Pointages", index=False)
                query_df("SELECT * FROM me_taches WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Taches", index=False)
                query_df("SELECT * FROM me_materiel WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Materiel", index=False)
                query_df("SELECT * FROM me_elevage WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Elevage", index=False)
                query_df("SELECT * FROM me_aquaculture WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Pisciculture", index=False)
                query_df("SELECT * FROM me_recoltes WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Recoltes", index=False)
                query_df("SELECT * FROM me_depenses WHERE user_id = ?", (USER_ID,)).to_excel(writer, sheet_name="Depenses", index=False)
            
            st.download_button("📥 Télécharger le fichier Excel Complet", data=buf_all.getvalue(), file_name=f"Rapport_Complet_AgriGestion_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with col_rep2:
        st.write("### 📑 Exportation PDF Synthétique")
        st.write("Génère un rapport structuré au format PDF contenant l'ensemble des bilans enregistrés.")
        
        titre_pdf = st.text_input("Titre du Rapport PDF", value=f"Bilan Global du {date.today()}")
        
        if st.button("📑 Générer le Rapport PDF Automatisé"):
            pdf_bytes = generate_full_pdf_report(USER_DATA, titre_pdf)
            st.download_button("📥 Télécharger le Rapport PDF", data=pdf_bytes, file_name=f"Rapport_AgriGestion_{date.today()}.pdf", mime="application/pdf")
