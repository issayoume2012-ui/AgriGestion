import streamlit as st
import pandas as pd
from datetime import datetime, date, time
import io

# Importation pour la cartographie dynamique interactive
import folium
from streamlit_folium import st_folium

# Imports pour les exports PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# 1. CONFIGURATION DE LA PAGE STREAMLIT
# ==========================================
st.set_page_config(
    page_title="AgriGestion Pro - Technicien Supérieur",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        .stApp { background-color: #f8f9fa; }
        .tech-badge { background-color: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold; }
        .gdoc-badge { background-color: #4285F4; color: white; padding: 4px 10px; border-radius: 8px; font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SYSTÈME D'AUTHENTIFICATION AVEC LISTE BLANCHE
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
                
                # LISTE BLANCHE : Définissez ici les e-mails autorisés et leurs mots de passe associés
                liste_blanche = {
                    "issayoume2012@gmail.com": {
                        "password": "i1801", # Mot de passe par défaut modifiable ici
                        "nom": "Youme",
                        "prenom": "Issa",
                        "matricule": "TS-ADMIN-01",
                        "phone": "+221 XX XXX XX XX",
                        "role": "Administrateur Principal"
                    },
                    # Exemple pour ajouter un autre utilisateur si besoin :
                    # "assistant@gmail.com": {
                    #     "password": "mon_autre_mdp",
                    #     "nom": "Nom",
                    #     "prenom": "Prénom",
                    #     "matricule": "EMP-02",
                    #     "phone": "+221 ...",
                    #     "role": "Assistant"
                    # }
                }

                # Vérification si l'e-mail est dans la liste blanche
                if email_propre in liste_blanche:
                    infos_user = liste_blanche[email_propre]
                    # Vérification du mot de passe correspondant
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
                    st.error("❌ Accès refusé. Cette adresse e-mail ne figure pas dans la liste blanche des utilisateurs autorisés.")
        return False

    return True

if not auth_system():
    st.stop()

# ==========================================
# 3. INITIALISATION DE LA BASE DE DONNÉES
# ==========================================
def init_empty_db():
    if 'db_champs' not in st.session_state:
        st.session_state.db_champs = pd.DataFrame(columns=["id", "nom", "superficie_ha", "latitude", "longitude", "culture_actuelle", "statut", "icone_lieu"])

    if 'db_equipes' not in st.session_state:
        st.session_state.db_equipes = pd.DataFrame(columns=["id", "nom_groupe", "chef_groupe", "membres"])

    if 'db_employes' not in st.session_state:
        st.session_state.db_employes = pd.DataFrame(columns=["id", "nom", "role", "groupe_id", "tarif_journalier"])

    if 'db_pointage' not in st.session_state:
        st.session_state.db_pointage = pd.DataFrame(columns=[
            "id", "date", "employe_nom", "groupe_nom", "champ_nom", "statut_presence",
            "heure_arrivee", "heure_debut_pause", "heure_fin_pause", "heure_depart", 
            "heures_effectives", "remarque"
        ])

    if 'db_taches' not in st.session_state:
        st.session_state.db_taches = pd.DataFrame(columns=["id", "champ_id", "groupe_id", "type_travail", "date_tache", "heures_travaillees", "statut"])

    if 'db_recoltes' not in st.session_state:
        st.session_state.db_recoltes = pd.DataFrame(columns=["champ_id", "culture", "date_recolte", "quantite_kg", "prix_unitaire"])

    if 'db_depenses' not in st.session_state:
        st.session_state.db_depenses = pd.DataFrame(columns=["champ_id", "type", "montant", "date", "facture_nom"])

    if 'db_intrants' not in st.session_state:
        st.session_state.db_intrants = pd.DataFrame(columns=["nom", "categorie", "stock_actuel", "unite", "seuil_alerte", "facture_nom"])

    if 'db_pluviometrie' not in st.session_state:
        st.session_state.db_pluviometrie = pd.DataFrame(columns=["champ_id", "date", "pluie_mm"])

    if 'db_incidents' not in st.session_state:
        st.session_state.db_incidents = pd.DataFrame(columns=["champ_id", "date", "description", "gravite", "action"])

    if 'db_materiel' not in st.session_state:
        st.session_state.db_materiel = pd.DataFrame(columns=["id", "nom_equipement", "categorie", "statut_marche", "date_derniere_revision", "prochaine_revision"])

    if 'db_tracabilite' not in st.session_state:
        st.session_state.db_tracabilite = pd.DataFrame(columns=["id", "lot_code", "champ_nom", "culture", "date_recolte", "norme_certification", "acheteur"])

    if 'db_irrigation' not in st.session_state:
        st.session_state.db_irrigation = pd.DataFrame(columns=["id", "champ_nom", "date", "volume_eau_m3", "methode", "duree_heures"])

    if 'db_alertes_meteo' not in st.session_state:
        st.session_state.db_alertes_meteo = pd.DataFrame(columns=["id", "date", "type_risque", "niveau_alerte", "recommandation_ts"])

init_empty_db()

# ==========================================
# 4. FONCTIONS D'EXPORTATION (EXCEL & PDF)
# ==========================================
def export_global_to_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        st.session_state.db_champs.to_excel(writer, index=False, sheet_name='Parcelles')
        st.session_state.db_equipes.to_excel(writer, index=False, sheet_name='Groupes')
        st.session_state.db_employes.to_excel(writer, index=False, sheet_name='Membres')
        st.session_state.db_pointage.to_excel(writer, index=False, sheet_name='Pointages')
        st.session_state.db_taches.to_excel(writer, index=False, sheet_name='Planning')
        st.session_state.db_recoltes.to_excel(writer, index=False, sheet_name='Recoltes')
        st.session_state.db_depenses.to_excel(writer, index=False, sheet_name='Depenses')
        st.session_state.db_intrants.to_excel(writer, index=False, sheet_name='Intrants')
        st.session_state.db_materiel.to_excel(writer, index=False, sheet_name='Materiel')
        st.session_state.db_tracabilite.to_excel(writer, index=False, sheet_name='Tracabilite')
        st.session_state.db_irrigation.to_excel(writer, index=False, sheet_name='Irrigation')
        st.session_state.db_alertes_meteo.to_excel(writer, index=False, sheet_name='Alertes_Meteo')
    return output.getvalue()

def export_global_pdf(date_rapport):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    
    tech = st.session_state.registered_tech
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, alignment=1, textColor=colors.HexColor('#1e3d59'))
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#10b981'), spaceBefore=10, spaceAfter=5)
    normal_style = styles['Normal']
    
    elements.append(Paragraph("RAPPORT GÉNÉRAL D'EXPLOITATION AGRICOLE", title_style))
    elements.append(Spacer(1, 10))
    
    date_str = date_rapport.strftime('%d/%m/%Y')
    header_info = f"<b>JOURNÉE DU : {date_str}</b><br/>"
    header_info += f"<b>Technicien Supérieur Responsable :</b> {tech['prenom']} {tech['nom']} (Matricule: {tech['matricule']})<br/>"
    header_info += f"<b>Contact :</b> {tech['gmail']} | <b>Tél :</b> {tech['phone']}<br/>"
    header_info += f"<b>Date d'édition du document :</b> {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
    
    elements.append(Paragraph(header_info, normal_style))
    elements.append(Spacer(1, 15))

    tables_dict = {
        "1. Pointages & Horaires des Membres": st.session_state.db_pointage[st.session_state.db_pointage['date'].astype(str) == str(date_rapport)] if not st.session_state.db_pointage.empty else pd.DataFrame(),
        "2. Parcelles & Lieux d'Exploitation": st.session_state.db_champs,
        "3. Groupes de Travail & Membres": st.session_state.db_equipes,
        "4. Récoltes & Pesées": st.session_state.db_recoltes,
        "5. Dépenses & Financials": st.session_state.db_depenses,
        "6. Stock du Magasin / Intrants": st.session_state.db_intrants,
        "7. Suivi du Parc Matériel": st.session_state.db_materiel,
        "8. Traçabilité des Lots": st.session_state.db_tracabilite,
        "9. Sessions d'Irrigation": st.session_state.db_irrigation,
        "10. Risques & Alertes Météo": st.session_state.db_alertes_meteo
    }

    for section_title, df_sec in tables_dict.items():
        elements.append(Paragraph(section_title, subtitle_style))
        if not df_sec.empty:
            data = [df_sec.columns.tolist()] + df_sec.astype(str).values.tolist()
            t = Table(data)
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
            elements.append(Paragraph("<i>Aucune donnée enregistrée pour cette section.</i>", normal_style))
        elements.append(Spacer(1, 10))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b><u>VALIDATION ET SIGNATURES OFFICIELLES</u></b>", subtitle_style))
    elements.append(Spacer(1, 10))

    signature_data = [
        ["Signature du Technicien Supérieur", "Signature du Chef d'Exploitation / Direction"],
        [f"\n\n\nNom: {tech['prenom']} {tech['nom']}\nDate: {date_str}", "\n\n\nNom: _____________________\nDate: ____/____/________"]
    ]
    
    sig_table = Table(signature_data, colWidths=[260, 260])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1e3d59')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f4f8')),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    return buffer.getvalue()

# ==========================================
# 5. BARRE LATÉRALE & NAVIGATION
# ==========================================
tech = st.session_state.registered_tech

with st.sidebar:
    st.markdown("### 👨‍🌾 Technicien Supérieur")
    st.markdown(f"**{tech['prenom']} {tech['nom']}**")
    st.caption(f"📧 {tech['gmail']}")
    st.caption(f"🆔 {tech['matricule']}")
    
    if tech.get("sync_gdocs"):
        st.markdown("<span class='gdoc-badge'>☁️ Drive Sync Actif</span>", unsafe_allow_html=True)
    
    st.divider()
    
    menu = st.radio("Navigation", [
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
        "🚜 Maintenance Matériel (Nouveau)",
        "🏷️ Traçabilité & Lots (Nouveau)",
        "💧 Irrigation & Eau (Nouveau)",
        "🌤️ Risques & Météo (Nouveau)",
        "📈 Rentabilité & ROI (Nouveau)",
        "📑 EXPORT COMPLET (Toutes données + Signature)"
    ])
    
    st.divider()
    if st.button("🚪 Déconnexion"):
        st.session_state.authenticated = False
        st.rerun()

champs_df = st.session_state.db_champs
if not champs_df.empty:
    liste_champs = {row['nom']: row['id'] for _, row in champs_df.iterrows()}
    champ_selectionne = st.sidebar.selectbox("📍 Parcelle Active :", list(liste_champs.keys()))
    champ_id_actif = liste_champs[champ_selectionne]
else:
    champ_id_actif = None
    champ_selectionne = "Aucune parcelle"

# ==========================================
# 6. MODULES APPLICATIFS
# ==========================================

if menu == "📊 Tableau de Bord":
    st.title("📊 Tableau de Bord d'Exploitation")
    m1, m2, m3, m4 = st.columns(4)
    tot_surf = st.session_state.db_champs['superficie_ha'].sum() if not st.session_state.db_champs.empty else 0
    tot_ouv = len(st.session_state.db_employes)
    tot_eq = len(st.session_state.db_equipes)
    tot_rec = st.session_state.db_recoltes['quantite_kg'].sum() if not st.session_state.db_recoltes.empty else 0
    
    m1.metric("Superficie Totale", f"{tot_surf:.2f} Ha")
    m2.metric("Groupes", f"{tot_eq}")
    m3.metric("Effectif Total", f"{tot_ouv}")
    m4.metric("Récoltes", f"{tot_rec/1000:.2f} Tonnes")
    st.divider()
    if st.session_state.db_champs.empty:
        st.info("👋 Votre base de données est vide. Rendez-vous dans le menu **'🌱 Cartographie & Parcelles'**.")
    else:
        st.subheader("📍 Aperçu des Parcelles")
        st.dataframe(st.session_state.db_champs[["nom", "superficie_ha", "culture_actuelle", "statut"]], use_container_width=True)

elif menu == "🌱 Cartographie & Parcelles":
    st.title("🌱 Cartographie Dynamique & Géolocalisation des Parcelles")
    if 'lat_active' not in st.session_state:
        st.session_state['lat_active'] = 14.6937
        st.session_state['lon_active'] = -17.4441

    col_map, col_form = st.columns([2, 1])
    with col_map:
        st.subheader("🗺️ Carte Interactive")
        center_lat = float(st.session_state['lat_active'])
        center_lon = float(st.session_state['lon_active'])
        m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles="OpenStreetMap")
        for _, r in st.session_state.db_champs.iterrows():
            folium.Marker(
                location=[r['latitude'], r['longitude']],
                popup=f"<b>{r['nom']}</b><br>Culture: {r['culture_actuelle']}",
                icon=folium.Icon(color="green" if r['statut'] == "En croissance" else "blue", icon="leaf")
            ).add_to(m)
        map_data = st_folium(m, width="100%", height=480, key="folium_map_stable", returned_objects=["last_clicked"])
        if map_data and map_data.get("last_clicked"):
            st.session_state['lat_active'] = round(map_data["last_clicked"]["lat"], 6)
            st.session_state['lon_active'] = round(map_data["last_clicked"]["lng"], 6)

    with col_form:
        st.subheader("➕ Enregistrer ce Lieu")
        with st.form("form_champ", clear_on_submit=False):
            nom_p = st.text_input("Nom de la parcelle / Lieu *")
            surf_p = st.number_input("Superficie (Ha)", min_value=0.1, value=1.0)
            lat_p = st.number_input("Latitude GPS", value=float(st.session_state['lat_active']), format="%.6f")
            lon_p = st.number_input("Longitude GPS", value=float(st.session_state['lon_active']), format="%.6f")
            cult_p = st.text_input("Culture principale")
            stat_p = st.selectbox("Statut", ["En préparation", "Semé", "En croissance", "Prêt à récolter"])
            if st.form_submit_button("💾 Enregistrer la parcelle", use_container_width=True):
                if nom_p:
                    new_row = {"id": len(st.session_state.db_champs)+1, "nom": nom_p, "superficie_ha": surf_p, "latitude": lat_p, "longitude": lon_p, "culture_actuelle": cult_p, "statut": stat_p, "icone_lieu": "leaf"}
                    st.session_state.db_champs = pd.concat([st.session_state.db_champs, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("✅ Parcelle enregistrée !")
                    st.rerun()

elif menu == "👥 Groupes & Membres":
    st.title("👥 Gestion des Groupes & Membres")
    t1, t2 = st.tabs(["👥 Structure des Groupes", "👷 Répertoire des Membres"])
    with t1:
        st.dataframe(st.session_state.db_equipes, use_container_width=True)
        with st.form("form_groupe"):
            nom_g = st.text_input("Nom du Groupe")
            chef_g = st.text_input("Chef de Groupe *")
            membres_init = st.text_area("Membres initiaux (séparés par des virgules)")
            if st.form_submit_button("Créer le Groupe"):
                if nom_g and chef_g:
                    gid = len(st.session_state.db_equipes) + 1
                    st.session_state.db_equipes = pd.concat([st.session_state.db_equipes, pd.DataFrame([{"id": gid, "nom_groupe": nom_g, "chef_groupe": chef_g, "membres": membres_init}])], ignore_index=True)
                    st.success("✅ Groupe créé !")
                    st.rerun()
    with t2:
        st.dataframe(st.session_state.db_employes, use_container_width=True)
        with st.form("form_employe"):
            nom_e = st.text_input("Nom complet de l'employé *")
            role_e = st.text_input("Rôle / Poste")
            tarif_e = st.number_input("Tarif journalier (FCFA)", min_value=0, value=2500)
            if st.form_submit_button("Ajouter l'employé"):
                if nom_e:
                    new_row = {"id": len(st.session_state.db_employes)+1, "nom": nom_e, "role": role_e, "groupe_id": 1, "tarif_journalier": tarif_e}
                    st.session_state.db_employes = pd.concat([st.session_state.db_employes, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("✅ Employé ajouté !")
                    st.rerun()

elif menu == "⏰ Pointage des Horaires":
    st.title("⏰ Registre de Pointage des Horaires")
    tab_masser, tab_indiv, tab_historique = st.tabs(["⚡ Pointage Massif", "👤 Pointage Individuel", "📋 Historique"])
    
    with tab_masser:
        if st.session_state.db_employes.empty:
            st.warning("⚠️ Aucun employé enregistré.")
        else:
            date_p_global = st.date_input("Date du pointage", value=date.today())
            parc_p_global = st.selectbox("Parcelle", st.session_state.db_champs['nom'].tolist() if not st.session_state.db_champs.empty else ["Général"])
            df_emp = st.session_state.db_employes.copy()
            df_emp['groupe_nom'] = "N/A"
            df_grid = pd.DataFrame({"Employé": df_emp['nom'], "Groupe": df_emp['groupe_nom'], "Présent(e)": True, "Parcelle": parc_p_global, "Arrivée": "08:00", "Début Pause": "12:00", "Fin Pause": "13:00", "Départ": "17:00", "Remarques": ""})
            grid_edited = st.data_editor(df_grid, use_container_width=True)
            if st.button("💾 Enregistrer le Pointage Massif", type="primary"):
                nouveaux = []
                for _, row in grid_edited.iterrows():
                    nouveaux.append({
                        "id": len(st.session_state.db_pointage) + len(nouveaux) + 1,
                        "date": date_p_global,
                        "employe_nom": row["Employé"],
                        "groupe_nom": row["Groupe"],
                        "champ_nom": row["Parcelle"],
                        "statut_presence": "Présent" if row["Présent(e)"] else "Absent",
                        "heure_arrivee": row["Arrivée"] if row["Présent(e)"] else "-",
                        "heure_debut_pause": row["Début Pause"] if row["Présent(e)"] else "-",
                        "heure_fin_pause": row["Fin Pause"] if row["Présent(e)"] else "-",
                        "heure_depart": row["Départ"] if row["Présent(e)"] else "-",
                        "heures_effectives": 8.0 if row["Présent(e)"] else 0.0,
                        "remarque": row["Remarques"]
                    })
                st.session_state.db_pointage = pd.concat([st.session_state.db_pointage, pd.DataFrame(nouveaux)], ignore_index=True)
                st.success("✅ Pointage massif enregistré !")
                st.rerun()

    with tab_indiv:
        if not st.session_state.db_employes.empty:
            with st.form("form_pointage_indiv"):
                date_p = st.date_input("Date", value=date.today())
                emp_p = st.selectbox("Employé", st.session_state.db_employes['nom'].tolist())
                parc_p = st.selectbox("Parcelle", st.session_state.db_champs['nom'].tolist() if not st.session_state.db_champs.empty else ["Général"])
                statut_indiv = st.selectbox("Statut", ["Présent", "Absent"])
                
                col_b, col_c = st.columns(2)
                with col_b:
                    h_arr = st.time_input("Heure d'Arrivée", value=time(8, 0))
                    h_dep_p = st.time_input("Début de Pause", value=time(12, 0))
                with col_c:
                    h_fin_p = st.time_input("Fin de Pause", value=time(13, 0))
                    h_dep = st.time_input("Heure de Départ", value=time(17, 0))
                remarque_p = st.text_input("Remarques / Retard")

                if st.form_submit_button("💾 Valider le Pointage Individuel", use_container_width=True):
                    heures_eff = 8.0 if statut_indiv == "Présent" else 0.0
                    new_row = {
                        "id": len(st.session_state.db_pointage) + 1,
                        "date": date_p,
                        "employe_nom": emp_p,
                        "groupe_nom": "N/A",
                        "champ_nom": parc_p,
                        "statut_presence": statut_indiv,
                        "heure_arrivee": h_arr.strftime("%H:%M") if statut_indiv == "Présent" else "-",
                        "heure_debut_pause": h_dep_p.strftime("%H:%M") if statut_indiv == "Présent" else "-",
                        "heure_fin_pause": h_fin_p.strftime("%H:%M") if statut_indiv == "Présent" else "-",
                        "heure_depart": h_dep.strftime("%H:%M") if statut_indiv == "Présent" else "-",
                        "heures_effectives": heures_eff,
                        "remarque": remarque_p
                    }
                    st.session_state.db_pointage = pd.concat([st.session_state.db_pointage, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("✅ Pointage individuel enregistré !")
                    st.rerun()
        else:
            st.warning("Veuillez d'abord enregistrer des membres dans la section '👥 Groupes & Membres'.")

    with tab_historique:
        st.dataframe(st.session_state.db_pointage, use_container_width=True)

elif menu == "📅 Planning & Travaux":
    st.title(f"📅 Planning - {champ_selectionne}")
    if champ_id_actif:
        st.dataframe(st.session_state.db_taches[st.session_state.db_taches['champ_id'] == champ_id_actif], use_container_width=True)
        with st.form("form_tache"):
            type_trav = st.selectbox("Type de travaux", ["Labour", "Semis", "Fertilisation", "Récolte"])
            hrs_t = st.number_input("Heures", min_value=1.0, value=8.0)
            if st.form_submit_button("Valider"):
                new_row = {"id": len(st.session_state.db_taches)+1, "champ_id": champ_id_actif, "groupe_id": 1, "type_travail": type_trav, "date_tache": date.today(), "heures_travaillees": hrs_t, "statut": "Planifié"}
                st.session_state.db_taches = pd.concat([st.session_state.db_taches, pd.DataFrame([new_row])], ignore_index=True)
                st.success("✅ Tâche planifiée !")
                st.rerun()

elif menu == "🌾 Récoltes & Rendements":
    st.title(f"🌾 Récoltes - {champ_selectionne}")
    if champ_id_actif:
        st.dataframe(st.session_state.db_recoltes[st.session_state.db_recoltes['champ_id'] == champ_id_actif], use_container_width=True)
        with st.form("form_rec"):
            cult = st.text_input("Culture")
            qte = st.number_input("Quantité (Kg)", min_value=0.0)
            pu = st.number_input("Prix unitaire (FCFA)", min_value=0.0, value=300.0)
            if st.form_submit_button("Enregistrer"):
                new_row = {"champ_id": champ_id_actif, "culture": cult, "date_recolte": date.today(), "quantite_kg": qte, "prix_unitaire": pu}
                st.session_state.db_recoltes = pd.concat([st.session_state.db_recoltes, pd.DataFrame([new_row])], ignore_index=True)
                st.success("✅ Récolte enregistrée !")
                st.rerun()

elif menu == "💰 Finances & Marges":
    st.title(f"💰 Finances - {champ_selectionne}")
    if champ_id_actif:
        st.dataframe(st.session_state.db_depenses[st.session_state.db_depenses['champ_id'] == champ_id_actif], use_container_width=True)
        with st.form("form_dep"):
            motif = st.text_input("Motif")
            mnt = st.number_input("Montant (FCFA)", min_value=0.0)
            facture_file = st.file_uploader("📸 Joindre facture", type=['jpg', 'pdf'])
            if st.form_submit_button("Enregistrer"):
                new_row = {"champ_id": champ_id_actif, "type": motif, "montant": mnt, "date": date.today(), "facture_nom": facture_file.name if facture_file else "Aucune"}
                st.session_state.db_depenses = pd.concat([st.session_state.db_depenses, pd.DataFrame([new_row])], ignore_index=True)
                st.success("✅ Dépense enregistrée !")
                st.rerun()

elif menu == "📦 Stocks d'Intrants":
    st.title("📦 Stocks d'Intrants")
    st.dataframe(st.session_state.db_intrants, use_container_width=True)
    with st.form("form_intrant"):
        nom_i = st.text_input("Nom de l'intrant")
        cat_i = st.selectbox("Catégorie", ["Engrais", "Semence", "Pesticide"])
        stk_i = st.number_input("Stock", min_value=0.0)
        unit_i = st.text_input("Unité")
        if st.form_submit_button("Ajouter"):
            new_row = {"nom": nom_i, "categorie": cat_i, "stock_actuel": stk_i, "unite": unit_i, "seuil_alerte": 5.0, "facture_nom": "Aucune"}
            st.session_state.db_intrants = pd.concat([st.session_state.db_intrants, pd.DataFrame([new_row])], ignore_index=True)
            st.success("✅ Intrant ajouté !")
            st.rerun()

elif menu == "🌧️ Pluviométrie":
    st.title("🌧️ Pluviométrie")
    if champ_id_actif:
        st.dataframe(st.session_state.db_pluviometrie[st.session_state.db_pluviometrie['champ_id'] == champ_id_actif], use_container_width=True)
        with st.form("form_pluie"):
            mm = st.number_input("Pluie (mm)", min_value=0.0)
            if st.form_submit_button("Enregistrer"):
                new_row = {"champ_id": champ_id_actif, "date": date.today(), "pluie_mm": mm}
                st.session_state.db_pluviometrie = pd.concat([st.session_state.db_pluviometrie, pd.DataFrame([new_row])], ignore_index=True)
                st.success("✅ Pluie enregistrée !")
                st.rerun()

elif menu == "⚠️ Incidents":
    st.title("⚠️ Incidents")
    if champ_id_actif:
        st.dataframe(st.session_state.db_incidents[st.session_state.db_incidents['champ_id'] == champ_id_actif], use_container_width=True)
        with st.form("form_inc"):
            desc = st.text_area("Description")
            grav = st.selectbox("Gravité", ["Faible", "Modéré", "Critique"])
            if st.form_submit_button("Déclarer"):
                new_row = {"champ_id": champ_id_actif, "date": date.today(), "description": desc, "gravite": grav, "action": "En attente"}
                st.session_state.db_incidents = pd.concat([st.session_state.db_incidents, pd.DataFrame([new_row])], ignore_index=True)
                st.success("✅ Incident déclaré !")
                st.rerun()

elif menu == "🚜 Maintenance Matériel (Nouveau)":
    st.title("🚜 Maintenance Matériel")
    st.dataframe(st.session_state.db_materiel, use_container_width=True)
    with st.form("form_mat"):
        nom_mat = st.text_input("Équipement")
        statut_mat = st.selectbox("Statut", ["Opérationnel", "En panne"])
        if st.form_submit_button("Ajouter"):
            new_row = {"id": len(st.session_state.db_materiel)+1, "nom_equipement": nom_mat, "categorie": "Général", "statut_marche": statut_mat, "date_derniere_revision": date.today(), "prochaine_revision": date.today()}
            st.session_state.db_materiel = pd.concat([st.session_state.db_materiel, pd.DataFrame([new_row])], ignore_index=True)
            st.success("✅ Matériel ajouté !")
            st.rerun()

elif menu == "🏷️ Traçabilité & Lots (Nouveau)":
    st.title("🏷️ Traçabilité des Lots")
    st.dataframe(st.session_state.db_tracabilite, use_container_width=True)
    with st.form("form_trac"):
        code_l = st.text_input("Code Lot")
        cult_l = st.text_input("Culture")
        if st.form_submit_button("Créer"):
            new_row = {"id": len(st.session_state.db_tracabilite)+1, "lot_code": code_l, "champ_nom": champ_selectionne, "culture": cult_l, "date_recolte": date.today(), "norme_certification": "Bio", "acheteur": "Client"}
            st.session_state.db_tracabilite = pd.concat([st.session_state.db_tracabilite, pd.DataFrame([new_row])], ignore_index=True)
            st.success("✅ Lot créé !")
            st.rerun()

elif menu == "💧 Irrigation & Eau (Nouveau)":
    st.title("💧 Irrigation")
    st.dataframe(st.session_state.db_irrigation, use_container_width=True)
    with st.form("form_irr"):
        vol = st.number_input("Volume (m3)", min_value=0.0)
        if st.form_submit_button("Enregistrer"):
            new_row = {"id": len(st.session_state.db_irrigation)+1, "champ_nom": champ_selectionne, "date": date.today(), "volume_eau_m3": vol, "methode": "Aspersion", "duree_heures": 2.0}
            st.session_state.db_irrigation = pd.concat([st.session_state.db_irrigation, pd.DataFrame([new_row])], ignore_index=True)
            st.success("✅ Irrigation enregistrée !")
            st.rerun()

elif menu == "🌤️ Risques & Météo (Nouveau)":
    st.title("🌤️ Risques & Météo")
    st.dataframe(st.session_state.db_alertes_meteo, use_container_width=True)
    with st.form("form_meteo"):
        risque = st.selectbox("Risque", ["Sécheresse", "Inondation"])
        if st.form_submit_button("Publier"):
            new_row = {"id": len(st.session_state.db_alertes_meteo)+1, "date": date.today(), "type_risque": risque, "niveau_alerte": "Modéré", "recommandation_ts": "Surveiller"}
            st.session_state.db_alertes_meteo = pd.concat([st.session_state.db_alertes_meteo, pd.DataFrame([new_row])], ignore_index=True)
            st.success("✅ Alerte publiée !")
            st.rerun()

elif menu == "📈 Rentabilité & ROI (Nouveau)":
    st.title("📈 Rentabilité & ROI")
    if not st.session_state.db_champs.empty:
        total_dep = st.session_state.db_depenses['montant'].sum() if not st.session_state.db_depenses.empty else 0
        total_rec = (st.session_state.db_recoltes['quantite_kg'] * st.session_state.db_recoltes['prix_unitaire']).sum() if not st.session_state.db_recoltes.empty else 0
        st.metric("Marge Nette Globale", f"{total_rec - total_dep:,.0f} FCFA")

elif menu == "📑 EXPORT COMPLET (Toutes données + Signature)":
    st.title("📑 Centre d'Exportation & Validation")
    date_exp = st.date_input("Date du rapport", value=date.today())
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Excel Global", data=export_global_to_excel(), file_name="export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    with col2:
        st.download_button("📥 Rapport PDF Signé", data=export_global_pdf(date_exp), file_name="rapport.pdf", mime="application/pdf", use_container_width=True)
