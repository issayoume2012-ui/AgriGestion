import streamlit as st
import pandas as pd
from datetime import datetime, date, time
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
        .gdoc-badge { background-color: #4285F4; color: white; padding: 4px 10px; border-radius: 8px; font-size: 12px; }
        div.stButton > button { width: 100%; border-radius: 8px; font-weight: bold; }
        @media(max-width: 768px) {
            .stMetric { font-size: 14px !important; }
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. GESTION DE LA BASE DE DONNÉES SQLITE (PERSISTANCE)
# ==========================================
def get_connection():
    return sqlite3.connect('agrigestion.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS champs (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT, superficie_ha REAL, latitude REAL, longitude REAL, culture_actuelle TEXT, statut TEXT, icone_lieu TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS equipes (id INTEGER PRIMARY KEY AUTOINCREMENT, nom_groupe TEXT, chef_groupe TEXT, membres TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS employes (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT, role TEXT, groupe_nom TEXT, tarif_journalier REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS pointage (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, employe_nom TEXT, groupe_nom TEXT, champ_nom TEXT, statut_presence TEXT, heure_arrivee TEXT, heure_debut_pause TEXT, heure_fin_pause TEXT, heure_depart TEXT, heures_effectives REAL, remarque TEXT)''')
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
# 3. SYSTÈME D'AUTHENTIFICATION AVEC LISTE BLANCHE
# ==========================================
def auth_system():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 Accès Sécurisé - Espace Restreint")
        st.info("Cet outil est protégé. Seuls les e-mails enregistrés dans la liste blanche peuvent se connecter.")

        with st.form("form_login_admin"):
            email_input = st.text_input("Adresse e-mail professionnelle *", placeholder="issayoume2012@gmail.com")
            password_input = st.text_input("Mot de passe d'accès *", type="password")
            submit_login = st.form_submit_button("Se Connecter", use_container_width=True)

            if submit_login:
                email_propre = email_input.strip().lower()
                liste_blanche = {
                    "issayoume2012@gmail.com": {
                        "password": "issayoume2026",
                        "nom": "Youme",
                        "prenom": "Issa",
                        "matricule": "TS-ADMIN-01",
                        "phone": "+221 XX XXX XX XX",
                        "role": "Administrateur Principal"
                    }
                }

                if email_propre in liste_blanche:
                    infos_user = liste_blanche[email_propre]
                    if password_input == infos_user["password"]:
                        st.session_state.authenticated = True
                        st.session_state.registered_tech = {
                            "nom": infos_user["nom"],
                            "prenom": infos_user["prenom"],
                            "gmail": email_propre,
                            "phone": infos_user["phone"],
                            "matricule": infos_user["matricule"],
                            "sync_gdocs": True
                        }
                        st.success(f"✅ Accès autorisé. Bienvenue, {infos_user['prenom']} !")
                        st.rerun()
                    else:
                        st.error("❌ Mot de passe incorrect pour cet e-mail.")
                else:
                    st.error("❌ Accès refusé. Cette adresse e-mail ne figure pas dans la liste blanche.")
        return False

    return True

if not auth_system():
    st.stop()

# ==========================================
# 4. FONCTIONS D'EXPORTATION (EXCEL & PDF)
# ==========================================
def export_global_to_excel():
    output = io.BytesIO()
    tables = ['champs', 'equipes', 'employes', 'pointage', 'taches', 'recoltes', 'depenses', 'intrants', 'materiel', 'tracabilite', 'irrigation', 'alertes_meteo']
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for t in tables:
            df = load_table(t)
            df.to_excel(writer, index=False, sheet_name=t.capitalize()[:31])
    return output.getvalue()

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
    header_info = f"<b>JOURNÉE DU : {date_str}</b> | <b>Technicien :</b> {tech['prenom']} {tech['nom']} ({tech['matricule']})<br/>"
    elements.append(Paragraph(header_info, normal_style))
    elements.append(Spacer(1, 10))

    tables_dict = {
        "1. Pointages & Horaires": load_table('pointage'),
        "2. Parcelles": load_table('champs'),
        "3. Récoltes": load_table('recoltes'),
        "4. Dépenses": load_table('depenses'),
        "5. Intrants": load_table('intrants'),
        "6. Matériel": load_table('materiel'),
        "7. Traçabilité": load_table('tracabilite'),
        "8. Irrigation": load_table('irrigation'),
        "9. Pluviométrie": load_table('pluviometrie'),
        "10. Incidents & Météo": load_table('incidents')
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
# 5. NAVIGATION EN HAUT DE PAGE (TOP BAR)
# ==========================================
tech = st.session_state.registered_tech

st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; background-color: #ffffff; padding: 10px 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 15px;">
        <div><b>🌾 AgriGestion Pro</b> | <span style="color: #10b981;">{tech['prenom']} {tech['nom']}</span> ({tech['matricule']})</div>
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
# 6. MODULES APPLICATIFS PERSISTANTS
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
    st.title("👥 Groupes & Membres")
    t1, t2 = st.tabs(["👥 Groupes", "👷 Employés / Membres"])
    with t1:
        st.dataframe(load_table('equipes'), use_container_width=True)
        with st.form("form_groupe"):
            nom_g = st.text_input("Nom du Groupe (ex: Équipe Semis)")
            chef_g = st.text_input("Chef de Groupe")
            if st.form_submit_button("Créer Groupe"):
                if nom_g:
                    execute_query("INSERT INTO equipes (nom_groupe, chef_groupe, membres) VALUES (?, ?, ?)", (nom_g, chef_g, ""))
                    st.success("✅ Groupe créé avec succès !")
                    st.rerun()
    with t2:
        df_eq_list = load_table('equipes')
        st.dataframe(load_table('employes'), use_container_width=True)
        with st.form("form_employe"):
            nom_e = st.text_input("Nom complet de l'employé *")
            role_e = st.text_input("Rôle (ex: Ouvrier, Chauffeur)")
            
            if not df_eq_list.empty:
                groupe_associe = st.selectbox("Affecter au Groupe", df_eq_list['nom_groupe'].tolist())
            else:
                groupe_associe = "Général"
                
            tarif_e = st.number_input("Tarif journalier (FCFA)", min_value=0, value=2500)
            if st.form_submit_button("Ajouter Employé au Groupe"):
                if nom_e:
                    execute_query("INSERT INTO employes (nom, role, groupe_nom, tarif_journalier) VALUES (?, ?, ?, ?)", (nom_e, role_e, groupe_associe, tarif_e))
                    st.success("✅ Employé ajouté !")
                    st.rerun()

elif menu == "⏰ Pointage des Horaires":
    st.title("⏰ Registre de Pointage Global (Par Groupe)")
    
    df_eqs = load_table('equipes')
    df_emps = load_table('employes')
    
    if df_eqs.empty and df_emps.empty:
        st.warning("⚠️ Veuillez d'abord créer des groupes et ajouter des employés dans le menu '👥 Groupes & Membres'.")
    else:
        # Sélection du groupe pour le pointage global
        groupes_dispos = df_eqs['nom_groupe'].tolist() if not df_eqs.empty else ["Général"]
        groupe_pointe = st.selectbox("🎯 Sélectionner le Groupe à pointer :", groupes_dispos)
        
        # Filtrer les membres du groupe sélectionné
        membres_groupe = df_emps[df_emps['groupe_nom'] == groupe_pointe] if not df_emps.empty else pd.DataFrame()
        
        with st.form("form_pointage_global"):
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                date_p = st.date_input("Date du pointage", value=date.today())
            with c_d2:
                parc_p = st.selectbox("Parcelle concernée", db_champs['nom'].tolist() if not db_champs.empty else ["Général"])
            
            st.divider()
            st.subheader(f"👷 Liste des membres du groupe : {groupe_pointe}")
            
            presence_data = {}
            if not membres_groupe.empty:
                for idx, row in membres_groupe.iterrows():
                    nom_emp = row['nom']
                    col_p1, col_p2, col_p3 = st.columns([2, 1, 2])
                    with col_p1:
                        st.markdown(f"**{nom_emp}** *({row['role']})*")
                    with col_p2:
                        statut = st.checkbox("Présent", value=True, key=f"pres_{idx}")
                    with col_p3:
                        rem = st.text_input("Remarque", value="", key=f"rem_{idx}", placeholder="Retard / Absence...")
                    presence_data[nom_emp] = {"statut": "Présent" if statut else "Absent", "remarque": rem}
            else:
                st.info("Aucun employé enregistré spécifiquement dans ce groupe. Vous pouvez faire une saisie rapide ci-dessous :")
                nom_libre = st.text_input("Nom de l'employé")
                statut_libre = st.checkbox("Présent", value=True)
                presence_data = {nom_libre: {"statut": "Présent" if statut_libre else "Absent", "remarque": ""}} if nom_libre else {}

            st.divider()
            c_h1, c_h2 = st.columns(2)
            with c_h1:
                h_arr = st.time_input("Heure d'arrivée collective", value=time(8, 0))
                h_dp = st.time_input("Début pause", value=time(12, 0))
            with c_h2:
                h_fp = st.time_input("Fin pause", value=time(13, 0))
                h_dep = st.time_input("Heure de départ", value=time(17, 0))

            submit_pointage = st.form_submit_button("💾 Valider et Enregistrer le Pointage du Groupe", use_container_width=True)
            
            if submit_pointage:
                if not presence_data:
                    st.error("❌ Aucun employé à pointer.")
                else:
                    for emp, info in presence_data.items():
                        if emp:
                            heures_eff = 8.0 if info["statut"] == "Présent" else 0.0
                            execute_query(
                                "INSERT INTO pointage (date, employe_nom, groupe_nom, champ_nom, statut_presence, heure_arrivee, heure_debut_pause, heure_fin_pause, heure_depart, heures_effectives, remarque) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (
                                    str(date_p), 
                                    emp, 
                                    groupe_pointe, 
                                    parc_p, 
                                    info["statut"], 
                                    h_arr.strftime("%H:%M") if info["statut"] == "Présent" else "-", 
                                    h_dp.strftime("%H:%M") if info["statut"] == "Présent" else "-", 
                                    h_fp.strftime("%H:%M") if info["statut"] == "Présent" else "-", 
                                    h_dep.strftime("%H:%M") if info["statut"] == "Présent" else "-", 
                                    heures_eff, 
                                    info["remarque"]
                                )
                            )
                    st.success("✅ Pointage global du groupe enregistré avec succès !")
                    st.rerun()

        st.subheader("📋 Historique Global des Pointages")
        st.dataframe(load_table('pointage'), use_container_width=True)

elif menu == "📅 Planning & Travaux":
    st.title(f"📅 Planning - {champ_selectionne}")
    if champ_id_actif:
        df_t = load_table('taches')
        st.dataframe(df_t[df_t['champ_id'] == champ_id_actif], use_container_width=True)
        with st.form("form_tache"):
            type_trav = st.selectbox("Type de travaux", ["Labour", "Semis", "Fertilisation", "Récolte"])
            hrs_t = st.number_input("Heures", min_value=1.0, value=8.0)
            if st.form_submit_button("Valider"):
                execute_query("INSERT INTO taches (champ_id, groupe_id, type_travail, date_tache, heures_travaillees, statut) VALUES (?, ?, ?, ?, ?, ?)", (champ_id_actif, 1, type_trav, str(date.today()), hrs_t, "Planifié"))
                st.success("✅ Tâche planifiée !")
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
    st.title(f"💰 Finances - {champ_selectionne}")
    if champ_id_actif:
        df_d = load_table('depenses')
        st.dataframe(df_d[df_d['champ_id'] == champ_id_actif], use_container_width=True)
        with st.form("form_dep"):
            motif = st.text_input("Motif de la dépense")
            mnt = st.number_input("Montant (FCFA)", min_value=0.0)
            if st.form_submit_button("Enregistrer Dépense"):
                execute_query("INSERT INTO depenses (champ_id, type, montant, date, facture_nom) VALUES (?, ?, ?, ?, ?)", (champ_id_actif, motif, mnt, str(date.today()), "Aucune"))
                st.success("✅ Dépense enregistrée !")
                st.rerun()

elif menu == "📦 Stocks d'Intrants":
    st.title("📦 Stocks d'Intrants")
    st.dataframe(load_table('intrants'), use_container_width=True)
    with st.form("form_intrant"):
        nom_i = st.text_input("Nom de l'intrant")
        cat_i = st.selectbox("Catégorie", ["Engrais", "Semence", "Pesticide"])
        stk_i = st.number_input("Stock actuel", min_value=0.0)
        unit_i = st.text_input("Unité (ex: Sacs, Litres)")
        if st.form_submit_button("Ajouter Intrant"):
            execute_query("INSERT INTO intrants (nom, categorie, stock_actuel, unite, seuil_alerte, facture_nom) VALUES (?, ?, ?, ?, ?, ?)", (nom_i, cat_i, stk_i, unit_i, 5.0, "Aucune"))
            st.success("✅ Intrant ajouté !")
            st.rerun()

elif menu == "🌧️ Pluviométrie":
    st.title(f"🌧️ Pluviométrie - {champ_selectionne}")
    if champ_id_actif:
        df_p = load_table('pluviometrie')
        st.dataframe(df_p[df_p['champ_id'] == champ_id_actif], use_container_width=True)
        with st.form("form_pluie"):
            mm = st.number_input("Hauteur de pluie (mm)", min_value=0.0, format="%.1f")
            date_pluie = st.date_input("Date de relevé", value=date.today())
            if st.form_submit_button("Enregistrer Pluviométrie", use_container_width=True):
                execute_query("INSERT INTO pluviometrie (champ_id, date, pluie_mm) VALUES (?, ?, ?)", (champ_id_actif, str(date_pluie), mm))
                st.success("✅ Relevé pluviométrique enregistré !")
                st.rerun()

elif menu == "⚠️ Incidents":
    st.title(f"⚠️ Incidents - {champ_selectionne}")
    if champ_id_actif:
        df_inc = load_table('incidents')
        st.dataframe(df_inc[df_inc['champ_id'] == champ_id_actif], use_container_width=True)
        with st.form("form_inc"):
            desc = st.text_area("Description de l'incident (attaque nuisible, météo, etc.)")
            grav = st.selectbox("Gravité", ["Faible", "Modéré", "Critique"])
            action_corrective = st.text_input("Action corrective envisagée")
            if st.form_submit_button("Déclarer l'incident", use_container_width=True):
                execute_query("INSERT INTO incidents (champ_id, date, description, gravite, action) VALUES (?, ?, ?, ?, ?)", (champ_id_actif, str(date.today()), desc, grav, action_corrective))
                st.success("✅ Incident déclaré !")
                st.rerun()

elif menu == "🚜 Maintenance Matériel":
    st.title("🚜 Maintenance du Parc Matériel")
    st.dataframe(load_table('materiel'), use_container_width=True)
    with st.form("form_mat"):
        nom_mat = st.text_input("Nom de l'équipement (ex: Tracteur, Motopompe)")
        cat_mat = st.selectbox("Catégorie", ["Motorisé", "Outil", "Irrigation"])
        statut_mat = st.selectbox("Statut", ["Opérationnel", "En panne", "En révision"])
        if st.form_submit_button("Ajouter Équipement", use_container_width=True):
            execute_query("INSERT INTO materiel (nom_equipement, categorie, statut_marche, date_derniere_revision, prochaine_revision) VALUES (?, ?, ?, ?, ?)", (nom_mat, cat_mat, statut_mat, str(date.today()), str(date.today())))
            st.success("✅ Matériel ajouté !")
            st.rerun()

elif menu == "🏷️ Traçabilité & Lots":
    st.title("🏷️ Traçabilité des Lots de Récolte")
    st.dataframe(load_table('tracabilite'), use_container_width=True)
    with st.form("form_trac"):
        code_l = st.text_input("Code unique du Lot (ex: LOT-2026-01)")
        cult_l = st.text_input("Culture concernée")
        norme = st.selectbox("Norme / Certification", ["Bio", "GlobalGAP", "Standard"])
        acheteur = st.text_input("Acheteur / Destination")
        if st.form_submit_button("Créer le Lot", use_container_width=True):
            execute_query("INSERT INTO tracabilite (lot_code, champ_nom, culture, date_recolte, norme_certification, acheteur) VALUES (?, ?, ?, ?, ?, ?)", (code_l, champ_selectionne, cult_l, str(date.today()), norme, acheteur))
            st.success("✅ Lot tracé enregistré !")
            st.rerun()

elif menu == "💧 Irrigation & Eau":
    st.title(f"💧 Gestion de l'Eau & Irrigation - {champ_selectionne}")
    if champ_id_actif:
        df_irr = load_table('irrigation')
        st.dataframe(df_irr[df_irr['champ_nom'] == champ_selectionne], use_container_width=True)
        with st.form("form_irr"):
            vol = st.number_input("Volume d'eau (m³)", min_value=0.0)
            methode = st.selectbox("Méthode d'irrigation", ["Aspersion", "Goutte à goutte", "Gravitaire"])
            duree = st.number_input("Durée (heures)", min_value=0.5, value=2.0)
            if st.form_submit_button("Enregistrer l'irrigation", use_container_width=True):
                execute_query("INSERT INTO irrigation (champ_nom, date, volume_eau_m3, methode, duree_heures) VALUES (?, ?, ?, ?, ?)", (champ_selectionne, str(date.today()), vol, methode, duree))
                st.success("✅ Session d'irrigation enregistrée !")
                st.rerun()

elif menu == "🌤️ Risques & Météo":
    st.title("🌤️ Risques & Alertes Météo")
    st.dataframe(load_table('alertes_meteo'), use_container_width=True)
    with st.form("form_meteo"):
        risque = st.selectbox("Type de risque", ["Sécheresse", "Inondation", "Tempête / Vent violent", "Attaque parasitaire"])
        niveau = st.selectbox("Niveau d'alerte", ["Faible", "Modéré", "Élevé", "Critique"])
        reco = st.text_input("Recommandation technique pour le terrain")
        if st.form_submit_button("Publier l'alerte", use_container_width=True):
            execute_query("INSERT INTO alertes_meteo (date, type_risque, niveau_alerte, recommandation_ts) VALUES (?, ?, ?, ?)", (str(date.today()), risque, niveau, reco))
            st.success("✅ Alerte météo publiée !")
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
    col_r2.metric("Total Ventes / Récoltes", f"{total_rec:,.0f} FCFA")
    col_r3.metric("Marge Nette", f"{marge:,.0f} FCFA", delta="Bénéfice" if marge >= 0 else "Déficit")

elif menu == "📑 EXPORT COMPLET":
    st.title("📑 Centre d'Exportation & Validation")
    date_exp = st.date_input("Date du rapport officiel", value=date.today())
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Télécharger Excel Global", data=export_global_to_excel(), file_name="export_agricole.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    with col2:
        st.download_button("📥 Télécharger Rapport PDF Signé", data=export_global_pdf(date_exp), file_name="rapport_agricole.pdf", mime="application/pdf", use_container_width=True)
