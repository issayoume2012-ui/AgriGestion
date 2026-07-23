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
                        role TEXT
                    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS partage_champs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        champ_nom TEXT,
                        technicien_email TEXT,
                        droit TEXT
                    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS messages_collab (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        expéditeur TEXT,
                        expediteur_email TEXT,
                        role TEXT,
                        date_heure TEXT,
                        destinataire TEXT,
                        categorie_travail TEXT,
                        titre TEXT,
                        message TEXT,
                        statut_tache TEXT,
                        piece_jointe_nom TEXT,
                        piece_jointe_data BLOB
                    )''')
    
    cursor.execute("SELECT COUNT(*) FROM whitelist_users")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO whitelist_users (email, password, prenom, nom, role) VALUES (?, ?, ?, ?, ?)",
            ("issayoume2012@gmail.com", "issayoume2026", "Issa", "Youme", "Propriétaire")
        )

    cursor.execute("PRAGMA table_info(champs)")
    cols_champs = [col[1] for col in cursor.fetchall()]
    if "code_pin" not in cols_champs: 
        cursor.execute("ALTER TABLE champs ADD COLUMN code_pin TEXT")

    cursor.execute("PRAGMA table_info(messages_collab)")
    cols_msg = [col[1] for col in cursor.fetchall()]
    if "expediteur_email" not in cols_msg: cursor.execute("ALTER TABLE messages_collab ADD COLUMN expediteur_email TEXT")
    if "destinataire" not in cols_msg: cursor.execute("ALTER TABLE messages_collab ADD COLUMN destinataire TEXT")
    if "categorie_travail" not in cols_msg: cursor.execute("ALTER TABLE messages_collab ADD COLUMN categorie_travail TEXT")
    if "titre" not in cols_msg: cursor.execute("ALTER TABLE messages_collab ADD COLUMN titre TEXT")
    if "statut_tache" not in cols_msg: cursor.execute("ALTER TABLE messages_collab ADD COLUMN statut_tache TEXT")
    if "piece_jointe_nom" not in cols_msg: cursor.execute("ALTER TABLE messages_collab ADD COLUMN piece_jointe_nom TEXT")
    if "piece_jointe_data" not in cols_msg: cursor.execute("ALTER TABLE messages_collab ADD COLUMN piece_jointe_data BLOB")

    conn.commit()
    conn.close()

init_db()

# Utilisation du cache Streamlit pour booster drastiquement la rapidité d'exécution
@st.cache_data(ttl=60)
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
    # Invalidation automatique du cache pour rafraîchir les données instantanément après une écriture
    load_table.clear()

# ==========================================
# 3. AUTHENTIFICATION DYNAMIQUE
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
# 4. EXPORTATIONS PDF & SIGNÉ POUR PARCELLE
# ==========================================
def export_parcelle_pdf(champ_nom, date_rapport):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    tech = st.session_state.get('registered_tech', {})
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=15, alignment=1, textColor=colors.HexColor('#1e3d59'))
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#10b981'), spaceBefore=8, spaceAfter=4)
    normal_style = styles['Normal']
    
    elements.append(Paragraph(f"RAPPORT OFFICIEL - PARCELLE : {champ_nom.upper()}", title_style))
    elements.append(Spacer(1, 6))
    
    date_str = date_rapport.strftime('%d/%m/%Y')
    header_info = f"<b>DATE DU RAPPORT : {date_str}</b> | <b>Établi par :</b> {tech.get('prenom', '')} {tech.get('nom', '')} ({tech.get('role', '')})<br/>"
    elements.append(Paragraph(header_info, normal_style))
    elements.append(Spacer(1, 8))

    df_c = load_table('champs')
    champ_info = df_c[df_c['nom'] == champ_nom]
    champ_id = int(champ_info['id'].values[0]) if not champ_info.empty else None

    tables_to_export = {}
    if champ_id:
        df_rec = load_table('recoltes')
        tables_to_export["1. Récoltes"] = df_rec[df_rec['champ_id'] == champ_id] if not df_rec.empty else pd.DataFrame()
        
        df_dep = load_table('depenses')
        tables_to_export["2. Dépenses"] = df_dep[df_dep['champ_id'] == champ_id] if not df_dep.empty else pd.DataFrame()
        
        df_t = load_table('taches')
        tables_to_export["3. Tâches Planifiées"] = df_t[df_t['champ_id'] == champ_id] if not df_t.empty else pd.DataFrame()
        
        df_p = load_table('pluviometrie')
        tables_to_export["4. Pluviométrie"] = df_p[df_p['champ_id'] == champ_id] if not df_p.empty else pd.DataFrame()
        
        df_i = load_table('incidents')
        tables_to_export["5. Incidents"] = df_i[df_i['champ_id'] == champ_id] if not df_i.empty else pd.DataFrame()

    for section_title, df_sec in tables_to_export.items():
        elements.append(Paragraph(section_title, subtitle_style))
        if not df_sec.empty:
            cols_to_show = [c for c in df_sec.columns if c not in ['id', 'champ_id', 'groupe_id']]
            df_display = df_sec[cols_to_show]
            data = [df_display.columns.tolist()] + df_display.astype(str).values.tolist()
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
            elements.append(Paragraph("<i>Aucune donnée enregistrée pour cette parcelle.</i>", normal_style))
        elements.append(Spacer(1, 5))

    elements.append(Spacer(1, 15))
    signature_text = "<b>Signature et Validation du Propriétaire / Responsable :</b><br/><br/><br/>________________________________________"
    elements.append(Paragraph(signature_text, normal_style))

    doc.build(elements)
    return buffer.getvalue()

# ==========================================
# 5. NAVIGATION TOP BAR
# ==========================================
tech = st.session_state.get('registered_tech', {})
prenom_tech = tech.get('prenom', 'Utilisateur')
nom_tech = tech.get('nom', '')
role_tech = tech.get('role', 'Membre')
email_connecte = tech.get('gmail', '').lower()

st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; background-color: #ffffff; padding: 10px 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 15px;">
        <div><b>🌾 AgriGestion Pro</b> | <span style="color: #10b981;">{prenom_tech} {nom_tech}</span> ({role_tech})</div>
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
    "💬 Espace Collaboration & Réunions Meet",
    "🔐 Paramètres & Liste Blanche",
    "📑 EXPORT RAPPORT PARCELLE"
]

menu = st.selectbox("📌 Menu Principal de Navigation", menu_options)

db_champs = load_table('champs')
champ_id_actif = None
champ_selectionne = "Aucune parcelle"

if not db_champs.empty:
    if email_connecte != "issayoume2012@gmail.com" and role_tech.lower() != "propriétaire":
        df_partages = load_table('partage_champs')
        champs_autorises = df_partages[df_partages['technicien_email'].str.lower() == email_connecte]['champ_nom'].tolist()
        db_champs = db_champs[db_champs['nom'].isin(champs_autorises)]

if not db_champs.empty:
    liste_champs = {row['nom']: row['id'] for _, row in db_champs.iterrows()}
    col_sel1, col_sel2 = st.columns([3, 1])
    with col_sel1:
        champ_selectionne = st.selectbox("📍 Parcelle Active pour les opérations :", list(liste_champs.keys()))
        champ_id_actif = liste_champs[champ_selectionne]
        
        row_champ_actuel = db_champs[db_champs['id'] == champ_id_actif].iloc[0]
        pin_enreg = row_champ_actuel.get('code_pin')
        has_pin = pin_enreg is not None and str(pin_enreg).strip() != "" and str(pin_enreg).strip() != "None"
        
        if has_pin:
            if f"pin_ok_{champ_id_actif}" not in st.session_state:
                st.session_state[f"pin_ok_{champ_id_actif}"] = False
                
            if not st.session_state[f"pin_ok_{champ_id_actif}"]:
                st.warning(f"🔒 Cette parcelle (**{champ_selectionne}**) est protégée par un code de confidentialité.")
                saisie_pin = st.text_input("Entrez le code PIN de la parcelle :", type="password", key=f"input_pin_{champ_id_actif}")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🔓 Déverrouiller", key=f"btn_unlock_{champ_id_actif}", use_container_width=True):
                        if saisie_pin == str(pin_enreg):
                            st.session_state[f"pin_ok_{champ_id_actif}"] = True
                            st.success("✅ Accès autorisé !")
                            st.rerun()
                        else:
                            st.error("❌ Code PIN incorrect.")
                with col_btn2:
                    if st.button("🔄 Oublié / Réinitialiser", key=f"btn_reset_pin_{champ_id_actif}", use_container_width=True):
                        st.session_state[f"reset_mode_{champ_id_actif}"] = True
                
                if st.session_state.get(f"reset_mode_{champ_id_actif}", False):
                    nouveau_pin_saisi = st.text_input("Nouveau code PIN :", type="password", key=f"new_pin_val_{champ_id_actif}")
                    if st.button("💾 Enregistrer et Accéder", key=f"save_new_pin_{champ_id_actif}", type="primary"):
                        pin_final = nouveau_pin_saisi.strip() if nouveau_pin_saisi else None
                        execute_query("UPDATE champs SET code_pin = ? WHERE id = ?", (pin_final, champ_id_actif))
                        st.session_state[f"pin_ok_{champ_id_actif}"] = True
                        st.session_state[f"reset_mode_{champ_id_actif}"] = False
                        st.success("✅ Code PIN mis à jour avec succès !")
                        st.rerun()
                st.stop()

    with col_sel2:
        if st.button("🚪 Déconnexion"):
            st.session_state.authenticated = False
            st.rerun()
else:
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
        st.subheader("➕ Ajouter une Parcelle & Sécurité")
        with st.form("form_champ_new"):
            nom_p = st.text_input("Nom de la parcelle *")
            surf_p = st.number_input("Superficie (Ha)", min_value=0.1, value=1.0)
            lat_p = st.number_input("Latitude", value=float(st.session_state['lat_active']), format="%.6f")
            lon_p = st.number_input("Longitude", value=float(st.session_state['lon_active']), format="%.6f")
            cult_p = st.text_input("Culture principale")
            stat_p = st.selectbox("Statut", ["En préparation", "Semé", "En croissance", "Prêt à récolter"])
            pin_p = st.text_input("Code PIN de confidentialité (optionnel)", type="password", placeholder="Laisser vide si public")
            
            if st.form_submit_button("💾 Enregistrer la Parcelle", use_container_width=True):
                if nom_p:
                    execute_query(
                        "INSERT INTO champs (nom, superficie_ha, latitude, longitude, culture_actuelle, statut, icone_lieu, code_pin) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (nom_p, surf_p, lat_p, lon_p, cult_p, stat_p, "leaf", pin_p.strip() if pin_p else "")
                    )
                    execute_query("INSERT INTO partage_champs (champ_nom, technicien_email, droit) VALUES (?, ?, ?)", (nom_p, "issayoume2012@gmail.com", "Propriétaire"))
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
    st.title(f"⏰ Pointage strictly synchronisé — {champ_selectionne}")
    
    if champ_selectionne == "Aucune parcelle":
        st.warning("⚠️ Veuillez sélectionner une parcelle active pour gérer le pointage.")
    else:
        # Récupération stricte des membres autorisés/partagés sur CETTE parcelle uniquement
        df_partages = load_table('partage_champs')
        emails_autorises = df_partages[df_partages['champ_nom'] == champ_selectionne]['technicien_email'].str.lower().tolist()
        
        df_employes_global = load_table('employes')
        df_wl_global = load_table('whitelist_users')
        
        # Consolider la liste des personnes rattachées à la parcelle (techniciens partagés OU employés de l'exploitation)
        # Pour une robustesse totale, on croise les emails partagés avec la whitelist, ou on liste les employés enregistrés.
        membres_parcelle = []
        
        # 1. Ajouter les utilisateurs de la whitelist assignés à la parcelle
        if not df_wl_global.empty and emails_autorises:
            match_wl = df_wl_global[df_wl_global['email'].str.lower().isin(emails_autorises)]
            for _, w in match_wl.iterrows():
                membres_parcelle.append({
                    "nom": f"{w['prenom']} {w['nom']} ({w['role']})",
                    "groupe": "Équipe Encadrement / Technique"
                })
                
        # 2. Si aucun technicien spécifique n'est dans la table de partage hormis le propriétaire, on regarde les employés généraux ou on invite au partage
        if not membres_parcelle:
            st.info(f"💡 Aucun technicien externe n'est rattaché par partage à la parcelle **{champ_selectionne}**. Les membres par défaut de l'exploitation s'affichent.")
            if not df_employes_global.empty:
                for _, emp in df_employes_global.iterrows():
                    membres_parcelle.append({
                        "nom": f"{emp['nom']} - {emp['role']}",
                        "groupe": emp['groupe_nom']
                    })

        if not membres_parcelle:
            st.warning("⚠️ Aucun membre ou employé n'est disponible pour le pointage. Veuillez ajouter des employés ou partager des accès.")
        else:
            st.success(f"✅ Pointage actif et isolé pour la parcelle : **{champ_selectionne}** ({len(membres_parcelle)} membre(s) concerné(s)).")
            
            c_d1, c_d2 = st.columns(2)
            with c_d1: date_p = st.date_input("Date du pointage", value=date.today(), key=f"date_pt_{champ_id_actif}")
            with c_d2: parc_p = st.text_input("Parcelle ciblée", value=champ_selectionne, disabled=True)
            
            st.divider()
            
            # Construction du tableau interactif propre à la parcelle
            lignes_pointage = []
            for m in membres_parcelle:
                lignes_pointage.append({
                    "Présent": True,
                    "Membre / Technicien": m["nom"],
                    "Groupe": m["groupe"],
                    "Tâche effectuée": "Travaux généraux de parcelle",
                    "Heures": 8.0,
                    "Remarque": ""
                })
                
            df_edition_pointage = pd.DataFrame(lignes_pointage)

            edited_pointage = st.data_editor(
                df_edition_pointage,
                column_config={
                    "Présent": st.column_config.CheckboxColumn("Présent ?", default=True),
                    "Membre / Technicien": st.column_config.TextColumn("Membre", disabled=True),
                    "Groupe": st.column_config.TextColumn("Groupe", disabled=True),
                    "Tâche effectuée": st.column_config.TextColumn("Tâche effectuée"),
                    "Heures": st.column_config.NumberColumn("Heures", min_value=0.0, max_value=24.0, step=0.5),
                    "Remarque": st.column_config.TextColumn("Remarque / Observation")
                },
                hide_index=True, use_container_width=True, key=f"table_editor_pt_{champ_id_actif}"
            )

            if st.button("💾 Enregistrer le Pointage de cette Parcelle", use_container_width=True, type="primary"):
                for _, row in edited_pointage.iterrows():
                    execute_query(
                        "INSERT INTO pointage (date, employe_nom, groupe_nom, champ_nom, statut_presence, tache_effectuee, heures_travaillees, remarque) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(date_p), 
                            row["Membre / Technicien"], 
                            row["Groupe"], 
                            champ_selectionne, 
                            "Présent" if row["Présent"] else "Absent", 
                            row["Tâche effectuée"] if row["Présent"] else "-", 
                            float(row["Heures"]) if row["Présent"] else 0.0, 
                            str(row["Remarque"])
                        )
                    )
                st.success(f"✅ Pointage enregistré avec succès pour la parcelle **{champ_selectionne}** !")
                st.rerun()

        st.divider()
        st.subheader(f"📋 Historique des Pointages pour : {champ_selectionne}")
        df_pt_global = load_table('pointage')
        if not df_pt_global.empty:
            df_pt_parcelle = df_pt_global[df_pt_global['champ_nom'] == champ_selectionne]
            if not df_pt_parcelle.empty:
                st.dataframe(df_pt_parcelle.drop(columns=['id'], errors='ignore'), use_container_width=True)
            else:
                st.info("Aucun historique de pointage enregistré pour cette parcelle spécifique.")
        else:
            st.info("Aucun pointage dans la base de données.")

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
        df_r_champ = df_r[df_r['champ_id'] == champ_id_actif] if not df_r.empty else pd.DataFrame()
        st.dataframe(df_r_champ, use_container_width=True)
        
        with st.form("form_rec"):
            cult = st.text_input("Culture")
            qte = st.number_input("Quantité (Kg)", min_value=0.0)
            pu = st.number_input("Prix unitaire (FCFA)", min_value=0.0, value=300.0)
            if st.form_submit_button("Enregistrer Récolte", use_container_width=True):
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
                mnt = st.number_input("Montant (FCFA)", min_value=0.0, value=0.0, step=100.0)
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

elif menu == "💬 Espace Collaboration & Réunions Meet":
    st.title("💬 Espace Collaboration Professionnelle & Réunions Google Meet")
    st.info("Espace de travail en ligne et partagé entre Propriétaire, Techniciens et gestionnaires de parcelles.")

    with st.expander("🤝 Gestion Collégiale des Parcelles (Partage entre Propriétaire et Techniciens)", expanded=False):
        st.markdown("Attribuez l'accès de gestion d'une parcelle à des techniciens spécifiques de la liste blanche pour qu'ils puissent y travailler en équipe.")
        df_wl_all = load_table('whitelist_users')
        df_ch_all = load_table('champs')
        
        if not df_ch_all.empty and not df_wl_all.empty:
            with st.form("form_partage_champ"):
                c_p1 = st.selectbox("Parcelle à partager", df_ch_all['nom'].tolist())
                c_p2 = st.selectbox("Technicien destinataire", df_wl_all['email'].tolist())
                c_p3 = st.selectbox("Droit d'accès", ["Gestion complète", "Lecture & Pointage"])
                if st.form_submit_button("🔗 Partager l'accès à la parcelle"):
                    execute_query("INSERT INTO partage_champs (champ_nom, technicien_email, droit) VALUES (?, ?, ?)", (c_p1, c_p2, c_p3))
                    st.success(f"✅ La parcelle **{c_p1}** a été partagée avec **{c_p2}** !")
                    st.rerun()
            
            st.subheader("📋 Parcelles Actuellement Partagées")
            df_parts = load_table('partage_champs')
            if not df_parts.empty:
                for _, prt in df_parts.iterrows():
                    col_pr1, col_pr2 = st.columns([4, 1])
                    with col_pr1:
                        st.markdown(f"📍 Parcelle : **{prt['champ_nom']}** ➡️ Technicien : `{prt['technicien_email']}` (*{prt['droit']}*)")
                    with col_pr2:
                        if st.button("🗑️ Retirer", key=f"del_part_{prt['id']}"):
                            execute_query("DELETE FROM partage_champs WHERE id = ?", (prt['id'],))
                            st.rerun()

    st.divider()

    col_meet1, col_meet2 = st.columns(2)
    with col_meet1:
        st.link_button("🚀 Ouvrir une réunion Google Meet instantanée", "https://meet.google.com/new", use_container_width=True)
    with col_meet2:
        saisie_lien_meet = st.text_input("Ou coller un lien Google Meet programmé :", placeholder="ex: https://meet.google.com/abc-defg-hij")
        if saisie_lien_meet.strip():
            st.link_button("🔗 Rejoindre la réunion planifiée", saisie_lien_meet.strip(), use_container_width=True)

    st.divider()

    col_m1, col_m2 = st.columns([1, 2])
    with col_m1:
        st.subheader("📝 Publier une Consigne / Rapport")
        df_users_wl = load_table('whitelist_users')
        options_destinataires = ["📢 Tous les collaborateurs (Diffusion générale)"]
        if not df_users_wl.empty:
            for _, u_w in df_users_wl.iterrows():
                options_destinataires.append(f"{u_w['prenom']} {u_w['nom']} ({u_w['email']})")

        with st.form("form_send_message_pro"):
            destinataire_choix = st.selectbox("Destinataire principal *", options_destinataires)
            cat_travail = st.selectbox("Objet / Type de travail", ["Rapport de Terrain", "Consigne d'Irrigation", "Alerte Urgence / Incident", "Point Financier / Dépense", "Autre communication"])
            titre_msg = st.text_input("Titre / Sujet *", placeholder="Ex: État de la parcelle")
            texte_msg = st.text_area("Contenu détaillé du message ou rapport :")
            statut_t = st.selectbox("Statut de la demande", ["À lire", "En cours de traitement", "Urgent", "Résolu / Validé"])
            fichier_joint = st.file_uploader("📸 Joindre une photo ou un document", type=["png", "jpg", "jpeg", "pdf", "xlsx", "docx"])
            joindre_rapport_auto = st.checkbox(f"📑 Joindre automatiquement le rapport PDF officiel de la parcelle active ({champ_selectionne})")

            if st.form_submit_button("📤 Diffuser / Envoyer", use_container_width=True):
                if titre_msg.strip() and texte_msg.strip():
                    auteur_nom = f"{prenom_tech} {nom_tech}"
                    horodatage = datetime.now().strftime("%d/%m/%Y à %H:%M")
                    nom_PJ = None
                    data_PJ = None
                    
                    if fichier_joint is not None:
                        nom_PJ = fichier_joint.name
                        data_PJ = fichier_joint.getvalue()
                    elif joindre_rapport_auto and champ_selectionne != "Aucune parcelle":
                        nom_PJ = f"rapport_{champ_selectionne}_{date.today().strftime('%Y%m%d')}.pdf"
                        data_PJ = export_parcelle_pdf(champ_selectionne, date.today())
                    
                    execute_query(
                        "INSERT INTO messages_collab (expéditeur, expediteur_email, role, date_heure, destinataire, categorie_travail, titre, message, statut_tache, piece_jointe_nom, piece_jointe_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (auteur_nom, email_connecte, role_tech, horodatage, destinataire_choix, cat_travail, titre_msg.strip(), texte_msg.strip(), statut_t, nom_PJ, data_PJ)
                    )
                    st.success("✅ Publication enregistrée et partagée avec succès !")
                    st.rerun()
                else:
                    st.warning("⚠️ Veuillez remplir le titre et le contenu du message.")

    with col_m2:
        st.subheader("📋 Fil d'Actualité & Notes de Travail")
        filtre_vue = st.radio("Filtrer l'affichage :", ["Tous les messages", "Mes messages / Reçus pour moi"], horizontal=True)
        df_msgs = load_table('messages_collab')
        
        if not df_msgs.empty:
            if filtre_vue == "Mes messages / Reçus pour moi":
                df_msgs = df_msgs[df_msgs['destinataire'].str.contains("Tous") | df_msgs['destinataire'].str.contains(email_connecte, case=False)]

            if df_msgs.empty:
                st.info("Aucun message ne correspond à ce filtre.")
            else:
                for _, m_row in df_msgs.iloc[::-1].iterrows():
                    badge_color = "#10b981"
                    if m_row.get('statut_tache') == "Urgent": badge_color = "#ef4444"
                    elif m_row.get('statut_tache') == "En cours de traitement": badge_color = "#f59e0b"

                    st.markdown(f"""
                        <div style="background-color: #ffffff; padding: 14px; border-radius: 8px; border-left: 5px solid {badge_color}; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
                            <div style="display: flex; justify-content: space-between;">
                                <b>📌 [{m_row.get('categorie_travail', 'Note')}] {m_row.get('titre', 'Sans titre')}</b>
                                <span style="font-size: 11px; background-color: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-weight: bold;">{m_row.get('statut_tache', 'Info')}</span>
                            </div>
                            <p style="margin: 6px 0; font-size: 13px; color: #4b5563;">{m_row['message']}</p>
                    """, unsafe_allow_html=True)

                    if m_row.get('piece_jointe_nom') and m_row.get('piece_jointe_data'):
                        st.download_button(
                            label=f"📎 Télécharger la pièce jointe : {m_row['piece_jointe_nom']}",
                            data=m_row['piece_jointe_data'],
                            file_name=m_row['piece_jointe_nom'],
                            key=f"dl_msg_file_{m_row['id']}"
                        )

                    st.markdown(f"""
                            <div style="font-size: 11px; color: #6b7280; display: flex; justify-content: space-between; border-top: 1px solid #f3f4f6; padding-top: 6px; margin-top: 8px;">
                                <span>👤 <b>{m_row['expéditeur']}</b> ({m_row['role']} — <code>{m_row.get('expediteur_email', 'N/A')}</code>)</span>
                                <span>🎯 Destinataire : <b>{m_row.get('destinataire', 'Tous')}</b> | 🕒 {m_row['date_heure']}</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("Aucun échange enregistré pour le moment.")

elif menu == "🔐 Paramètres & Liste Blanche":
    st.title("🔐 Gestion de la Liste Blanche (Contrôle d'Accès)")
    est_proprietaire = (email_connecte == "issayoume2012@gmail.com")

    if not est_proprietaire:
        st.warning("⚠️ Accès restreint : Seul le propriétaire de l'application est autorisé à modifier les accès.")
        df_wl = load_table('whitelist_users')
        if not df_wl.empty:
            for _, row in df_wl.iterrows():
                st.markdown(f"📧 **{row['email']}** | 👤 *{row['prenom']} {row['nom']}* (`{row['role']}`)")
    else:
        col_wl1, col_wl2 = st.columns([1, 1])
        with col_wl1:
            st.subheader("➕ Ajouter un utilisateur autorisé")
            with st.form("form_add_whitelist"):
                new_email = st.text_input("Adresse e-mail *", placeholder="exemple@gmail.com")
                new_password = st.text_input("Mot de passe d'accès *", type="password")
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
                            st.success(f"✅ L'e-mail **{new_email}** a été ajouté à la liste blanche !")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("⚠️ Cet e-mail est déjà présent dans la liste blanche.")
                    else:
                        st.warning("⚠️ Remplissez au moins l'e-mail et le mot de passe.")

        with col_wl2:
            st.subheader("📋 Liste des E-mails Autorisés")
            df_wl = load_table('whitelist_users')
            if not df_wl.empty:
                for _, row in df_wl.iterrows():
                    c_item1, c_item2 = st.columns([3, 1])
                    with c_item1:
                        st.markdown(f"📧 **{row['email']}**<br>👤 *{row['prenom']} {row['nom']}* (`{row['role']}`)", unsafe_allow_html=True)
                    with c_item2:
                        if row['email'].lower() != "issayoume2012@gmail.com":
                            if st.button("🗑️ Révoquer", key=f"del_wl_{row['id']}"):
                                execute_query("DELETE FROM whitelist_users WHERE id = ?", (row['id'],))
                                st.success("Accès révoqué.")
                                st.rerun()
                        else:
                            st.caption("🔒 Propriétaire")
                    st.divider()

elif menu == "📑 EXPORT RAPPORT PARCELLE":
    st.title("📑 Centre d'Exportation de Rapport Officiel")
    st.info(f"Génération du rapport PDF signé et daté pour la parcelle active : **{champ_selectionne}**")
    date_exp = st.date_input("Date officielle du rapport", value=date.today())
    
    if champ_selectionne and champ_selectionne != "Aucune parcelle":
        pdf_bytes = export_parcelle_pdf(champ_selectionne, date_exp)
        st.download_button(
            label=f"📥 Télécharger le Rapport PDF de '{champ_selectionne}'",
            data=pdf_bytes,
            file_name=f"rapport_{champ_selectionne}_{date_exp.strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )
    else:
        st.warning("Veuillez d'abord sélectionner une parcelle valide.")
