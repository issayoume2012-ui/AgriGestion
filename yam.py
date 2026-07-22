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
# 1. CONFIGURATION DE LA PAGE & RESPONSIVENESS
# ==========================================
st.set_page_config(
    page_title="AgriGestion Pro",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        .stApp { background-color: #f8f9fa; }
        .tech-badge { background-color: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold; }
        div.stButton > button { width: 100%; border-radius: 8px; font-weight: bold; }
        @media(max-width: 768px) {
            .stMetric { font-size: 14px !important; }
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. GESTION DE LA BASE DE DONNÉES SQLITE
# ==========================================
def get_connection():
    return sqlite3.connect('agrigestion.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS champs (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT, superficie_ha REAL, latitude REAL, longitude REAL, culture_actuelle TEXT, statut TEXT, icone_lieu TEXT)''')
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
    
    # Table pour la Liste Blanche des utilisateurs autorisés
    cursor.execute('''CREATE TABLE IF NOT EXISTS whitelist_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        email TEXT UNIQUE, 
                        password TEXT, 
                        prenom TEXT, 
                        nom TEXT, 
                        role TEXT
                    )''')
    
    # Insertion par défaut de l'administrateur si la table est vide
    cursor.execute("SELECT COUNT(*) FROM whitelist_users")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO whitelist_users (email, password, prenom, nom, role) VALUES (?, ?, ?, ?, ?)",
            ("issayoume2012@gmail.com", "issayoume2026", "Issa", "Youme", "Administrateur Principal")
        )

    # Mises à jour de colonnes de sécurité si besoin
    cursor.execute("PRAGMA table_info(employes)")
    cols_emp = [col[1] for col in cursor.fetchall()]
    if "groupe_nom" not in cols_emp: cursor.execute("ALTER TABLE employes ADD COLUMN groupe_nom TEXT")
    if "tarif_journalier" not in cols_emp: cursor.execute("ALTER TABLE employes ADD COLUMN tarif_journalier REAL")

    conn.commit()
    conn.close()

init_db()

def load_table(table_name):
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    conn.close()
    return df

def execute_query(query, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()

# ==========================================
# 3. AUTHENTIFICATION DYNAMIQUE (LISTE BLANCHE SQL)
# ==========================================
def auth_system():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 Accès Sécurisé - Espace Restreint")
        st.info("Veuillez vous identifier avec un e-mail autorisé pour accéder à l'application.")

        with st.form("form_login_admin"):
            email_input = st.text_input("Adresse e-mail professionnelle *", placeholder="issayoume2012@gmail.com")
            password_input = st.text_input("Mot de passe d'accès *", type="password")
            submit_login = st.form_submit_button("Se Connecter", use_container_width=True)

            if submit_login:
                email_propre = email_input.strip().lower()
                
                # Vérification dans la base de données SQLite (whitelist_users)
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT prenom, nom, role, password FROM whitelist_users WHERE LOWER(email) = ?", (email_propre,))
                user_record = cursor.fetchone()
                conn.close()

                if user_record and password_input == user_record[3]:
                    st.session_state.authenticated = True
                    st.session_state.registered_tech = {
                        "nom": user_record[1],
                        "prenom": user_record[0],
                        "gmail": email_propre,
                        "phone": "+221 XX XXX XX XX",
                        "matricule": "TS-PRO-01",
                        "role": user_record[2]
                    }
                    st.success(f"✅ Bienvenue, {user_record[0]} !")
                    st.rerun()
                else:
                    st.error("❌ Identifiants incorrects ou e-mail non autorisé dans la liste blanche.")
        return False
    return True

if not auth_system():
    st.stop()

# ==========================================
# 4. EXPORTATIONS (CSV & PDF)
# ==========================================
def export_global_to_csv():
    output = io.StringIO()
    output.write("--- RAPPORT GLOBAL AGRIGESTION ---\n\n")
    tables = ['champs', 'equipes', 'employes', 'pointage', 'taches', 'recoltes', 'depenses', 'intrants', 'materiel']
    for t in tables:
        output.write(f"=== TABLE : {t.upper()} ===\n")
        df = load_table(t)
        df.to_csv(output, index=False)
        output.write("\n\n")
    return output.getvalue().encode('utf-8')

def export_global_pdf(date_rapport):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    tech = st.session_state.registered_tech
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=16, alignment=1, textColor=colors.HexColor('#1e3d59'))
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#10b981'), spaceBefore=8, spaceAfter=4)
    normal_style = styles['Normal']
    
    elements.append(Paragraph("RAPPORT GÉNÉRAL D'EXPLOITATION AGRICOLE", title_style))
    elements.append(Spacer(1, 8))
    
    date_str = date_rapport.strftime('%d/%m/%Y')
    header_info = f"<b>JOURNÉE DU : {date_str}</b> | <b>Technicien :</b> {tech['prenom']} {tech['nom']} ({tech['role']})<br/>"
    elements.append(Paragraph(header_info, normal_style))
    elements.append(Spacer(1, 10))

    tables_dict = {
        "1. Pointages": load_table('pointage'),
        "2. Parcelles": load_table('champs'),
        "3. Récoltes": load_table('recoltes'),
        "4. Dépenses": load_table('depenses'),
        "5. Intrants": load_table('intrants'),
        "6. Matériel": load_table('materiel')
    }

    for section_title, df_sec in tables_dict.items():
        elements.append(Paragraph(section_title, subtitle_style))
        if not df_sec.empty:
            data = [df_sec.columns.tolist()] + df_sec.astype(str).values.tolist()
            t = Table(data, hAlign='LEFT')
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(t)
        else:
            elements.append(Paragraph("<i>Aucune donnée enregistrée.</i>", normal_style))
        elements.append(Spacer(1, 6))

    doc.build(elements)
    return buffer.getvalue()

# ==========================================
# 5. NAVIGATION TOP BAR
# ==========================================
tech = st.session_state.registered_tech
st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; background-color: #ffffff; padding: 10px 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 15px;">
        <div><b>🌾 AgriGestion Pro</b> | <span style="color: #10b981;">{tech['prenom']} {tech['nom']}</span> ({tech['role']})</div>
    </div>
""", unsafe_allow_html=True)

menu_options = [
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
    "🔐 Paramètres & Liste Blanche",
    "📑 EXPORT COMPLET"
]

menu = st.selectbox("📌 Menu Principal de Navigation", menu_options)

db_champs = load_table('champs')
if not db_champs.empty:
    liste_champs = {row['nom']: row['id'] for _, row in db_champs.iterrows()}
    col_sel1, col_sel2 = st.columns([3, 1])
    with col_sel1:
        champ_selectionne = st.selectbox("📍 Parcelle Active pour les opérations :", list(liste_champs.keys()))
        champ_id_actif = liste_champs[champ_selectionne]
    with col_sel2:
        if st.button("🚪 Déconnexion"):
            st.session_state.authenticated = False
            st.rerun()
else:
    champ_id_actif = None
    champ_selectionne = "Aucune parcelle"
    if st.button("🚪 Déconnexion"):
        st.session_state.authenticated = False
        st.rerun()

st.divider()

# ==========================================
# 6. MODULES APPLICATIFS
# ==========================================

if menu == "📊 Tableau de Bord":
    st.title("📊 Tableau de Bord d'Exploitation")
    m1, m2, m3, m4 = st.columns(4)
    df_c = load_table('champs')
    df_e = load_table('employes')
    df_eq = load_table('equipes')
    df_r = load_table('recoltes')
    
    tot_surf = df_c['superficie_ha'].sum() if not df_c.empty else 0
    tot_ouv = len(df_e)
    tot_eq = len(df_eq)
    tot_rec = df_r['quantite_kg'].sum() if not df_r.empty else 0
    
    m1.metric("Superficie", f"{tot_surf:.2f} Ha")
    m2.metric("Groupes", f"{tot_eq}")
    m3.metric("Effectif", f"{tot_ouv}")
    m4.metric("Récoltes", f"{tot_rec/1000:.2f} T")
    st.divider()
    if df_c.empty:
        st.info("👋 Commencez par ajouter vos parcelles dans **'🌱 Cartographie & Parcelles'**.")
    else:
        st.subheader("📍 Parcelles Actives")
        st.dataframe(df_c[["nom", "superficie_ha", "culture_actuelle", "statut"]], use_container_width=True)

elif menu == "🌱 Cartographie & Parcelles":
    st.title("🌱 Cartographie Dynamique & Parcelles")
    if 'lat_active' not in st.session_state:
        st.session_state['lat_active'] = 14.6937
        st.session_state['lon_active'] = -17.4441

    col_map, col_form = st.columns([2, 1])
    with col_map:
        st.subheader("🗺️ Carte Interactive")
        df_c = load_table('champs')
        m = folium.Map(location=[float(st.session_state['lat_active']), float(st.session_state['lon_active'])], zoom_start=13)
        for _, r in df_c.iterrows():
            folium.Marker(
                location=[r['latitude'], r['longitude']],
                popup=f"<b>{r['nom']}</b><br>Culture: {r['culture_actuelle']}",
                icon=folium.Icon(color="green", icon="leaf")
            ).add_to(m)
        map_data = st_folium(m, width="100%", height=400, key="folium_map_stable", returned_objects=["last_clicked"])
        if map_data and map_data.get("last_clicked"):
            st.session_state['lat_active'] = round(map_data["last_clicked"]["lat"], 6)
            st.session_state['lon_active'] = round(map_data["last_clicked"]["lng"], 6)

    with col_form:
        st.subheader("➕ Ajouter une Parcelle")
        with st.form("form_champ_new"):
            nom_p = st.text_input("Nom de la parcelle *")
            surf_p = st.number_input("Superficie (Ha)", min_value=0.1, value=1.0)
            lat_p = st.number_input("Latitude", value=float(st.session_state['lat_active']), format="%.6f")
            lon_p = st.number_input("Longitude", value=float(st.session_state['lon_active']), format="%.6f")
            cult_p = st.text_input("Culture principale")
            stat_p = st.selectbox("Statut", ["En préparation", "Semé", "En croissance", "Prêt à récolter"])
            if st.form_submit_button("💾 Enregistrer", use_container_width=True):
                if nom_p:
                    execute_query(
                        "INSERT INTO champs (nom, superficie_ha, latitude, longitude, culture_actuelle, statut, icone_lieu) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (nom_p, surf_p, lat_p, lon_p, cult_p, stat_p, "leaf")
                    )
                    st.success("✅ Parcelle enregistrée avec succès !")
                    st.rerun()

elif menu == "👥 Groupes & Membres":
    st.title("👥 Gestion des Groupes & des Membres")
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.subheader("1️⃣ Gestion des Groupes")
        with st.form("form_creer_groupe"):
            nom_g_input = st.text_input("Nom du Groupe / Équipe")
            chef_g_input = st.text_input("Chef de Groupe")
            if st.form_submit_button("📁 Créer le Groupe", use_container_width=True):
                if nom_g_input.strip():
                    execute_query("INSERT INTO equipes (nom_groupe, chef_groupe) VALUES (?, ?)", (nom_g_input.strip(), chef_g_input.strip()))
                    st.success("✅ Groupe créé !")
                    st.rerun()
                    
        st.subheader("📋 Liste des Groupes")
        df_groupes = load_table('equipes')
        if not df_groupes.empty:
            for _, grp in df_groupes.iterrows():
                col_gr1, col_gr2 = st.columns([3, 1])
                with col_gr1: st.markdown(f"**{grp['nom_groupe']}** (Chef : *{grp['chef_groupe']}*)")
                with col_gr2:
                    if st.button("🗑️ Supprimer", key=f"del_grp_{grp['id']}"):
                        execute_query("DELETE FROM equipes WHERE id = ?", (grp['id'],))
                        st.rerun()

    with col_g2:
        st.subheader("2️⃣ Gestion des Employés")
        df_groupes_dispos = load_table('equipes')
        if df_groupes_dispos.empty:
            st.warning("⚠️ Créez d'abord un groupe.")
        else:
            with st.form("form_ajouter_employe"):
                nom_emp = st.text_input("Nom et Prénom *")
                role_emp = st.text_input("Rôle (ex: Ouvrier)")
                groupe_affecte = st.selectbox("Groupe *", df_groupes_dispos['nom_groupe'].tolist())
                tarif_emp = st.number_input("Tarif journalier (FCFA)", min_value=0, value=2500)
                if st.form_submit_button("👷 Ajouter le Membre", use_container_width=True):
                    if nom_emp.strip():
                        execute_query("INSERT INTO employes (nom, role, groupe_nom, tarif_journalier) VALUES (?, ?, ?, ?)", (nom_emp.strip(), role_emp.strip(), groupe_affecte, tarif_emp))
                        st.success("✅ Membre ajouté !")
                        st.rerun()
                        
        st.subheader("👥 Répertoire des Employés")
        df_employes_tous = load_table('employes')
        if not df_employes_tous.empty:
            for _, emp in df_employes_tous.iterrows():
                col_em1, col_em2 = st.columns([3, 1])
                with col_em1: st.markdown(f"**{emp['nom']}** — *{emp['role']}* (`{emp['groupe_nom']}`)")
                with col_em2:
                    if st.button("🗑️ Retirer", key=f"del_emp_{emp['id']}"):
                        execute_query("DELETE FROM employes WHERE id = ?", (emp['id'],))
                        st.rerun()

elif menu == "⏰ Pointage des Horaires":
    st.title("⏰ Registre de Pointage Global")
    df_emps = load_table('employes')
    if df_emps.empty:
        st.warning("⚠️ Aucun employé trouvé.")
    else:
        c_d1, c_d2 = st.columns(2)
        with c_d1: date_p = st.date_input("Date du pointage", value=date.today(), key="global_date_pointage")
        with c_d2: parc_p = st.selectbox("Parcelle concernée", db_champs['nom'].tolist() if not db_champs.empty else ["Général"], key="global_parc_pointage")
        
        st.divider()
        df_edition = df_emps[['nom', 'role', 'groupe_nom']].copy()
        df_edition.insert(0, "Présent", True)
        df_edition.insert(4, "Tâche", "Travaux généraux")
        df_edition.insert(5, "Heures", 8.0)
        df_edition.insert(6, "Remarque", "")

        edited_df = st.data_editor(
            df_edition,
            column_config={
                "Présent": st.column_config.CheckboxColumn("Présent ?", default=True),
                "nom": st.column_config.TextColumn("Employé", disabled=True),
                "role": st.column_config.TextColumn("Rôle", disabled=True),
                "groupe_nom": st.column_config.TextColumn("Groupe", disabled=True),
                "Tâche": st.column_config.TextColumn("Tâche effectuée"),
                "Heures": st.column_config.NumberColumn("Heures", min_value=0.0, max_value=24.0, step=0.5),
                "Remarque": st.column_config.TextColumn("Remarque")
            },
            hide_index=True, use_container_width=True, key="editor_pointage_global"
        )

        if st.button("💾 Enregistrer le Pointage Global", use_container_width=True, type="primary"):
            for _, row in edited_df.iterrows():
                execute_query(
                    "INSERT INTO pointage (date, employe_nom, groupe_nom, champ_nom, statut_presence, tache_effectuee, heures_travaillees, remarque) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(date_p), row["nom"], row["groupe_nom"], parc_p, "Présent" if row["Présent"] else "Absent", row["Tâche"] if row["Présent"] else "-", float(row["Heures"]) if row["Présent"] else 0.0, str(row["Remarque"]))
                )
            st.success("✅ Pointage enregistré avec succès !")
            st.rerun()

        st.subheader("📋 Historique Récent")
        st.dataframe(load_table('pointage'), use_container_width=True)

elif menu == "📅 Planning & Travaux":
    st.title(f"📅 Planning & Travaux - {champ_selectionne}")
    if champ_id_actif:
        col_pl1, col_pl2 = st.columns([2, 1])
        with col_pl1:
            st.subheader("📋 Tâches Planifiées pour cette Parcelle")
            df_t = load_table('taches')
            df_t_champ = df_t[df_t['champ_id'] == champ_id_actif] if not df_t.empty else pd.DataFrame()
            if not df_t_champ.empty:
                for _, tache in df_t_champ.iterrows():
                    c_t1, c_t2 = st.columns([4, 1])
                    with c_t1:
                        st.markdown(f"🔹 **{tache['type_travail']}** | Date : {tache['date_tache']} | Durée : {tache['heures_travaillees']}h | Statut : `{tache['statut']}`")
                    with c_t2:
                        if st.button("🗑️ Suppr", key=f"del_tache_{tache['id']}"):
                            execute_query("DELETE FROM taches WHERE id = ?", (tache['id'],))
                            st.rerun()
            else:
                st.info("Aucune tâche planifiée pour cette parcelle.")
        
        with col_pl2:
            st.subheader("➕ Planifier une Tâche")
            with st.form("form_planning_refonte"):
                type_trav = st.selectbox("Type de travaux", ["Labour", "Semis", "Désherbage", "Fertilisation", "Traitement phythosanitaire", "Récolte"])
                date_tache = st.date_input("Date prévue", value=date.today())
                hrs_t = st.number_input("Heures prévues", min_value=1.0, value=8.0)
                statut_t = st.selectbox("Statut initial", ["Planifié", "En cours", "Terminé"])
                if st.form_submit_button("💾 Enregistrer la Tâche", use_container_width=True):
                    execute_query("INSERT INTO taches (champ_id, groupe_id, type_travail, date_tache, heures_travaillees, statut) VALUES (?, ?, ?, ?, ?, ?)", (champ_id_actif, 1, type_trav, str(date_tache), hrs_t, statut_t))
                    st.success("✅ Tâche planifiée avec succès !")
                    st.rerun()

elif menu == "🌾 Récoltes & Rendements":
    st.title(f"🌾 Récoltes - {champ_selectionne}")
    if champ_id_actif:
        df_r = load_table('recoltes')
        st.dataframe(df_r[df_r['champ_id'] == champ_id_actif], use_container_width=True)
        with st.form("form_rec"):
            cult = st.text_input("Culture")
            qte = st.number_input("Quantité (Kg)", min_value=0.0)
            pu = st.number_input("Prix unitaire (FCFA)", min_value=0.0, value=300.0)
            if st.form_submit_button("Enregistrer Récolte"):
                execute_query("INSERT INTO recoltes (champ_id, culture, date_recolte, quantite_kg, prix_unitaire) VALUES (?, ?, ?, ?, ?)", (champ_id_actif, cult, str(date.today()), qte, pu))
                st.success("✅ Récolte enregistrée !")
                st.rerun()

elif menu == "💰 Finances & Marges":
    st.title(f"💰 Finances & Dépenses - {champ_selectionne}")
    if champ_id_actif:
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            st.subheader("📋 Historique des Dépenses de la Parcelle")
            df_d = load_table('depenses')
            df_d_champ = df_d[df_d['champ_id'] == champ_id_actif] if not df_d.empty else pd.DataFrame()
            if not df_d_champ.empty:
                st.dataframe(df_d_champ[["type", "montant", "date", "facture_nom"]], use_container_width=True)
            else:
                st.info("Aucune dépense enregistrée sur cette parcelle.")
        
        with col_f2:
            st.subheader("➕ Nouvelle Dépense & Facture")
            with st.form("form_finances_refonte"):
                motif = st.text_input("Motif / Type de dépense (ex: Achat Carburant)")
                mnt = st.number_input("Montant (FCFA)", min_value=0.0, value=0.0)
                date_dep = st.date_input("Date de la dépense", value=date.today())
                
                photo_facture = st.file_uploader("📸 Photo ou Scan de la Facture", type=["png", "jpg", "jpeg", "pdf"])
                
                if st.form_submit_button("💾 Enregistrer la Dépense", use_container_width=True):
                    nom_fic = photo_facture.name if photo_facture else "Aucune facture"
                    execute_query("INSERT INTO depenses (champ_id, type, montant, date, facture_nom) VALUES (?, ?, ?, ?, ?)", (champ_id_actif, motif, mnt, str(date_dep), nom_fic))
                    st.success("✅ Dépense enregistrée avec succès !")
                    st.rerun()

elif menu == "📦 Stocks d'Intrants":
    st.title("📦 Stocks d'Intrants & Factures")
    col_i1, col_i2 = st.columns([2, 1])
    with col_i1:
        st.subheader("📋 État Actuel des Stocks")
        st.dataframe(load_table('intrants'), use_container_width=True)
    with col_i2:
        st.subheader("➕ Ajouter un Intrant")
        with st.form("form_intrant_refonte"):
            nom_i = st.text_input("Nom de l'intrant (ex: Engrais NPK)")
            cat_i = st.selectbox("Catégorie", ["Engrais", "Semence", "Pesticide", "Carburant"])
            stk_i = st.number_input("Stock initial / actuel", min_value=0.0, value=10.0)
            unit_i = st.text_input("Unité (ex: Sacs, Litres, Kg)")
            seuil_i = st.number_input("Seuil d'alerte", min_value=0.0, value=2.0)
            
            photo_fact_intrant = st.file_uploader("📸 Photo de la Facture Intrant", type=["png", "jpg", "jpeg"])
            
            if st.form_submit_button("💾 Enregistrer l'Intrant", use_container_width=True):
                nom_fic_i = photo_fact_intrant.name if photo_fact_intrant else "Aucune facture"
                execute_query("INSERT INTO intrants (nom, categorie, stock_actuel, unite, seuil_alerte, facture_nom) VALUES (?, ?, ?, ?, ?, ?)", (nom_i, cat_i, stk_i, unit_i, seuil_i, nom_fic_i))
                st.success("✅ Intrant enregistré avec succès !")
                st.rerun()

elif menu == "🌧️ Pluviométrie":
    st.title(f"🌧️ Pluviométrie - {champ_selectionne}")
    if champ_id_actif:
        df_p = load_table('pluviometrie')
        st.dataframe(df_p[df_p['champ_id'] == champ_id_actif], use_container_width=True)
        with st.form("form_pluie"):
            mm = st.number_input("Hauteur de pluie (mm)", min_value=0.0, format="%.1f")
            date_pluie = st.date_input("Date de relevé", value=date.today())
            if st.form_submit_button("Enregistrer", use_container_width=True):
                execute_query("INSERT INTO pluviometrie (champ_id, date, pluie_mm) VALUES (?, ?, ?)", (champ_id_actif, str(date_pluie), mm))
                st.success("✅ Enregistré !")
                st.rerun()

elif menu == "⚠️ Incidents":
    st.title(f"⚠️ Incidents - {champ_selectionne}")
    if champ_id_actif:
        df_inc = load_table('incidents')
        st.dataframe(df_inc[df_inc['champ_id'] == champ_id_actif], use_container_width=True)
        with st.form("form_inc"):
            desc = st.text_area("Description")
            grav = st.selectbox("Gravité", ["Faible", "Modéré", "Critique"])
            action_corrective = st.text_input("Action corrective")
            if st.form_submit_button("Déclarer l'incident", use_container_width=True):
                execute_query("INSERT INTO incidents (champ_id, date, description, gravite, action) VALUES (?, ?, ?, ?, ?)", (champ_id_actif, str(date.today()), desc, grav, action_corrective))
                st.success("✅ Déclaré !")
                st.rerun()

elif menu == "🚜 Maintenance Matériel":
    st.title("🚜 Maintenance du Parc Matériel")
    st.dataframe(load_table('materiel'), use_container_width=True)
    with st.form("form_mat"):
        nom_mat = st.text_input("Nom de l'équipement")
        cat_mat = st.selectbox("Catégorie", ["Motorisé", "Outil", "Irrigation"])
        statut_mat = st.selectbox("Statut", ["Opérationnel", "En panne", "En révision"])
        if st.form_submit_button("Ajouter", use_container_width=True):
            execute_query("INSERT INTO materiel (nom_equipement, categorie, statut_marche, date_derniere_revision, prochaine_revision) VALUES (?, ?, ?, ?, ?)", (nom_mat, cat_mat, statut_mat, str(date.today()), str(date.today())))
            st.success("✅ Ajouté !")
            st.rerun()

elif menu == "🏷️ Traçabilité & Lots":
    st.title("🏷️ Traçabilité des Lots de Récolte")
    st.dataframe(load_table('tracabilite'), use_container_width=True)
    with st.form("form_trac"):
        code_l = st.text_input("Code unique du Lot")
        cult_l = st.text_input("Culture concernée")
        norme = st.selectbox("Norme / Certification", ["Bio", "GlobalGAP", "Standard"])
        acheteur = st.text_input("Acheteur / Destination")
        if st.form_submit_button("Créer le Lot", use_container_width=True):
            execute_query("INSERT INTO tracabilite (lot_code, champ_nom, culture, date_recolte, norme_certification, acheteur) VALUES (?, ?, ?, ?, ?, ?)", (code_l, champ_selectionne, cult_l, str(date.today()), norme, acheteur))
            st.success("✅ Créé !")
            st.rerun()

elif menu == "💧 Irrigation & Eau":
    st.title(f"💧 Gestion de l'Eau & Irrigation - {champ_selectionne}")
    if champ_id_actif:
        df_irr = load_table('irrigation')
        st.dataframe(df_irr[df_irr['champ_nom'] == champ_selectionne], use_container_width=True)
        with st.form("form_irr"):
            vol = st.number_input("Volume d'eau (m³)", min_value=0.0)
            methode = st.selectbox("Méthode", ["Aspersion", "Goutte à goutte", "Gravitaire"])
            duree = st.number_input("Durée (heures)", min_value=0.5, value=2.0)
            if st.form_submit_button("Enregistrer", use_container_width=True):
                execute_query("INSERT INTO irrigation (champ_nom, date, volume_eau_m3, methode, duree_heures) VALUES (?, ?, ?, ?, ?)", (champ_selectionne, str(date.today()), vol, methode, duree))
                st.success("✅ Enregistré !")
                st.rerun()

elif menu == "🌤️ Risques & Météo":
    st.title("🌤️ Risques & Alertes Météo")
    st.dataframe(load_table('alertes_meteo'), use_container_width=True)
    with st.form("form_meteo"):
        risque = st.selectbox("Type de risque", ["Sécheresse", "Inondation", "Tempête", "Attaque parasitaire"])
        niveau = st.selectbox("Niveau", ["Faible", "Modéré", "Élevé", "Critique"])
        reco = st.text_input("Recommandation technique")
        if st.form_submit_button("Publier", use_container_width=True):
            execute_query("INSERT INTO alertes_meteo (date, type_risque, niveau_alerte, recommandation_ts) VALUES (?, ?, ?, ?)", (str(date.today()), risque, niveau, reco))
            st.success("✅ Publié !")
            st.rerun()

elif menu == "📈 Rentabilité & ROI":
    st.title("📈 Rentabilité & ROI Global")
    df_d = load_table('depenses')
    df_r = load_table('recoltes')
    total_dep = df_d['montant'].sum() if not df_d.empty else 0
    total_rec = (df_r['quantite_kg'] * df_r['prix_unitaire']).sum() if not df_r.empty else 0
    marge = total_rec - total_dep
    
    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("Total Dépenses", f"{total_dep:,.0f} FCFA")
    col_r2.metric("Total Ventes", f"{total_rec:,.0f} FCFA")
    col_r3.metric("Marge Nette", f"{marge:,.0f} FCFA", delta="Bénéfice" if marge >= 0 else "Déficit")

elif menu == "🔐 Paramètres & Liste Blanche":
    st.title("🔐 Gestion de la Liste Blanche (Contrôle d'Accès)")
    st.info("Ici, vous pouvez ajouter ou supprimer les adresses e-mail autorisées à se connecter à cette application.")

    col_wl1, col_wl2 = st.columns([1, 1])

    with col_wl1:
        st.subheader("➕ Ajouter un utilisateur autorisé")
        with st.form("form_add_whitelist"):
            new_email = st.text_input("Adresse e-mail *", placeholder="exemple@gmail.com")
            new_password = st.text_input("Mot de passe attribué *", type="password")
            new_prenom = st.text_input("Prénom")
            new_nom = st.text_input("Nom")
            new_role = st.selectbox("Rôle", ["Administrateur", "Technicien", "Gestionnaire de Stock", "Consultant"])
            
            if st.form_submit_button("💾 Autoriser cet E-mail", use_container_width=True):
                if new_email.strip() and new_password.strip():
                    try:
                        execute_query(
                            "INSERT INTO whitelist_users (email, password, prenom, nom, role) VALUES (?, ?, ?, ?, ?)",
                            (new_email.strip().lower(), new_password.strip(), new_prenom.strip(), new_nom.strip(), new_role)
                        )
                        st.success(f"✅ L'e-mail **{new_email}** a été ajouté à la liste blanche avec succès !")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("⚠️ Cet e-mail est déjà présent dans la liste blanche.")
                else:
                    st.warning("⚠️ Veuillez remplir au moins l'e-mail et le mot de passe.")

    with col_wl2:
        st.subheader("📋 Liste des E-mails Autorisés")
        df_wl = load_table('whitelist_users')
        if not df_wl.empty:
            for _, row in df_wl.iterrows():
                c_item1, c_item2 = st.columns([3, 1])
                with c_item1:
                    st.markdown(f"📧 **{row['email']}**<br>👤 *{row['prenom']} {row['nom']}* (`{row['role']}`)", unsafe_allow_html=True)
                with c_item2:
                    # Empêcher la suppression du compte principal admin par sécurité
                    if row['email'].lower() != "issayoume2012@gmail.com":
                        if st.button("🗑️ Révoquer", key=f"del_wl_{row['id']}"):
                            execute_query("DELETE FROM whitelist_users WHERE id = ?", (row['id'],))
                            st.success("Accès révoqué.")
                            st.rerun()
                    else:
                        st.caption("🔒 Protégé")
                st.divider()

elif menu == "📑 EXPORT COMPLET":
    st.title("📑 Centre d'Exportation & Validation")
    date_exp = st.date_input("Date du rapport officiel", value=date.today())
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Télécharger Données Globales (CSV)", data=export_global_to_csv(), file_name="export_agricole.csv", mime="text/csv", use_container_width=True)
    with col2:
        st.download_button("📥 Télécharger Rapport PDF Signé", data=export_global_pdf(date_exp), file_name="rapport_agricole.pdf", mime="application/pdf", use_container_width=True)
