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
# 2. SYSTÈME D'INSCRIPTION & AUTHENTIFICATION
# ==========================================
def auth_system():
    if "registered_tech" not in st.session_state:
        st.session_state.registered_tech = None
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.registered_tech is None:
        st.title("👨‍🌾 Enregistrement Initial - Technicien Supérieur")
        st.info("Bienvenue ! Configurez votre compte professionnel et définissez votre propre mot de passe d'accès.")

        with st.form("form_registration"):
            col1, col2 = st.columns(2)
            with col1:
                nom = st.text_input("Nom de famille *")
                prenom = st.text_input("Prénom *")
                gmail = st.text_input("Adresse Gmail / Google Workspace *", placeholder="votre.email@gmail.com")
                phone = st.text_input("Numéro de Téléphone")
            with col2:
                matricule = st.text_input("Matricule / Code TS", value="TS-001")
                password_custom = st.text_input("Définissez votre Mot de Passe *", type="password", help="Choisissez un mot de passe sécurisé")
                password_confirm = st.text_input("Confirmez votre Mot de Passe *", type="password")
                sync_gdocs = st.checkbox("Activer la synchronisation avec Google Drive / Docs", value=True)

            submit_reg = st.form_submit_button("Créer mon compte Technicien & Définir le mot de passe", use_container_width=True)

            if submit_reg:
                if not nom or not prenom or not gmail or not password_custom:
                    st.error("❌ Veuillez remplir tous les champs obligatoires (*).")
                elif password_custom != password_confirm:
                    st.error("❌ Les mots de passe ne correspondent pas.")
                else:
                    st.session_state.registered_tech = {
                        "nom": nom,
                        "prenom": prenom,
                        "gmail": gmail,
                        "phone": phone,
                        "matricule": matricule,
                        "password": password_custom,
                        "sync_gdocs": sync_gdocs
                    }
                    st.session_state.authenticated = True
                    st.success("✅ Compte créé avec succès ! Vos paramètres ont été enregistrés.")
                    st.rerun()
        return False

    elif not st.session_state.authenticated:
        tech_data = st.session_state.registered_tech
        st.title("🔒 Connexion - Espace Technicien Supérieur")
        st.caption(f"Compte associé : **{tech_data['prenom']} {tech_data['nom']}** ({tech_data['gmail']})")

        pwd_input = st.text_input("Saisissez votre mot de passe :", type="password")
        
        col_b1, col_b2 = st.columns([1, 2])
        with col_b1:
            if st.button("Se Connecter", use_container_width=True):
                if pwd_input == tech_data['password']:
                    st.session_state.authenticated = True
                    st.success("✅ Connexion réussie !")
                    st.rerun()
                else:
                    st.error("❌ Mot de passe incorrect.")
        with col_b2:
            if st.button("Réinitialiser le profil / Compte", use_container_width=True):
                st.session_state.registered_tech = None
                st.session_state.authenticated = False
                st.rerun()
        return False

    return True

if not auth_system():
    st.stop()

# ==========================================
# 3. INITIALISATION DE LA BASE DE DONNÉES VIDE
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
# 4. EXPORTATIONS AVEC DATE & ZONE SIGNATURE
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
    
    # En-tête du Rapport
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
        "1. Pointages & Horaires des Membres (Journée)": st.session_state.db_pointage[st.session_state.db_pointage['date'].astype(str) == str(date_rapport)] if not st.session_state.db_pointage.empty else pd.DataFrame(),
        "2. Parcelles & Lieux d'Exploitation": st.session_state.db_champs,
        "3. Groupes de Travail & Membres": st.session_state.db_equipes,
        "4. Récoltes & Pesées": st.session_state.db_recoltes,
        "5. Dépenses & Financials": st.session_state.db_depenses,
        "6. Stock du Magasin / Intrants": st.session_state.db_intrants,
        "7. Suivi du Parc Matériel": st.session_state.db_materiel,
        "8. Traçabilité des Lots": st.session_state.db_tracabilite,
        "9. Sessions d'Irrigation": st.session_state.db_irrigation,
        "10. Risk & Alertes Météo": st.session_state.db_alertes_meteo
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

# --- A. TABLEAU DE BORD ---
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
        st.info("👋 Votre base de données est vide. Rendez-vous dans le menu **'🌱 Cartographie & Parcelles'** pour enregistrer vos premiers lieux de travail.")
    else:
        st.subheader("📍 Aperçu des Parcelles")
        st.dataframe(st.session_state.db_champs[["nom", "superficie_ha", "culture_actuelle", "statut"]], use_container_width=True)

# --- B. CARTOGRAPHIE DYNAMIQUE INTERACTIVE ---
elif menu == "🌱 Cartographie & Parcelles":
    st.title("🌱 Cartographie Dynamique & Géolocalisation des Parcelles")
    
    if 'lat_active' not in st.session_state:
        st.session_state['lat_active'] = 16.0300
        st.session_state['lon_active'] = -16.4800

    col_map, col_form = st.columns([2, 1])
    
    with col_map:
        st.subheader("🗺️ Carte Interactive")
        st.caption("👈 Cliquez sur la carte pour définir la position GPS.")
        
        center_lat = float(st.session_state['lat_active'])
        center_lon = float(st.session_state['lon_active'])
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles="OpenStreetMap")
        
        for _, r in st.session_state.db_champs.iterrows():
            popup_content = f"<b>{r['nom']}</b><br>Culture: {r['culture_actuelle']}<br>Surface: {r['superficie_ha']} Ha"
            icon_name = r.get('icone_lieu', 'leaf')
            
            folium.Marker(
                location=[r['latitude'], r['longitude']],
                popup=popup_content,
                tooltip=f"📍 {r['nom']} ({r['culture_actuelle']})",
                icon=folium.Icon(color="green" if r['statut'] == "En croissance" else "blue", icon=icon_name)
            ).add_to(m)
            
        folium.Marker(
            location=[center_lat, center_lon],
            popup="<b>📍 Point Sélectionné</b>",
            tooltip="Coordonnées actives",
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(m)
            
        map_data = st_folium(
            m, 
            width="100%", 
            height=480, 
            key="folium_map_stable",
            returned_objects=["last_clicked"]
        )
        
        if map_data and map_data.get("last_clicked"):
            st.session_state['lat_active'] = round(map_data["last_clicked"]["lat"], 6)
            st.session_state['lon_active'] = round(map_data["last_clicked"]["lng"], 6)

    with col_form:
        st.subheader("➕ Enregistrer ce Lieu")
        st.info(f"📍 **Position capturée :**\n- Lat : `{st.session_state['lat_active']}`\n- Lon : `{st.session_state['lon_active']}`")

        with st.form("form_champ", clear_on_submit=False):
            nom_p = st.text_input("Nom de la parcelle / Lieu *")
            surf_p = st.number_input("Superficie (Ha)", min_value=0.1, value=1.0, step=0.1)
            
            lat_p = st.number_input("Latitude GPS", value=float(st.session_state['lat_active']), format="%.6f")
            lon_p = st.number_input("Longitude GPS", value=float(st.session_state['lon_active']), format="%.6f")
            
            cult_p = st.text_input("Culture principale (ex: Riz, Maïs, Oignon)")
            stat_p = st.selectbox("Statut de la parcelle", ["En préparation", "Semé", "En croissance", "Prêt à récolter"])
            
            logo_lieu = st.selectbox("Logo / Icône du lieu", [
                "leaf (🌾 Feuille / Culture)",
                "home (🏠 Bâtiment / Ferme)",
                "tint (💧 Point d'eau / Irrigation)",
                "star (⭐ Zone Prioritaire)",
                "info-sign (📍 Marqueur Repère)"
            ])
            icon_code = logo_lieu.split(" ")[0]

            submit_p = st.form_submit_button("💾 Enregistrer la parcelle", use_container_width=True)
            
            if submit_p:
                if not nom_p:
                    st.error("❌ Veuillez saisir un nom pour le lieu.")
                else:
                    new_id = len(st.session_state.db_champs) + 1
                    new_row = {
                        "id": new_id,
                        "nom": nom_p,
                        "superficie_ha": surf_p,
                        "latitude": round(lat_p, 6),
                        "longitude": round(lon_p, 6),
                        "culture_actuelle": cult_p,
                        "statut": stat_p,
                        "icone_lieu": icon_code
                    }
                    st.session_state.db_champs = pd.concat([st.session_state.db_champs, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"✅ Parcelle '{nom_p}' enregistrée avec succès !")
                    st.rerun()

    st.divider()
    st.subheader("📋 Liste des Parcelles & Lieux (Éditable)")
    
    updated_df = st.data_editor(
        st.session_state.db_champs,
        use_container_width=True,
        num_rows="dynamic",
        key="editor_parcelles_lieux"
    )
    st.session_state.db_champs = updated_df

# --- C. GROUPES, CHEFS DE GROUPE & MEMBRES ---
elif menu == "👥 Groupes & Membres":
    st.title("👥 Gestion des Groupes, Chefs de Groupe & Membres")
    
    t1, t2 = st.tabs(["👥 Structure des Groupes", "👷 Répertoire des Membres"])
    
    with t1:
        st.subheader("Création et Structuration des Groupes de Travail")
        st.dataframe(st.session_state.db_equipes, use_container_width=True)
        
        with st.form("form_groupe"):
            nom_g = st.text_input("Nom du Groupe (ex: Brigade Irrigation Nord)")
            chef_g = st.text_input("Nom du Chef de Groupe *")
            membres_init = st.text_area("Membres initiaux (séparés par des virgules)", placeholder="Mamadou Diallo, Moussa Sow, Fatou Fall")
            
            if st.form_submit_button("Créer le Groupe"):
                if nom_g and chef_g:
                    new_id = len(st.session_state.db_equipes) + 1
                    new_row = {
                        "id": new_id, 
                        "nom_groupe": nom_g, 
                        "chef_groupe": chef_g, 
                        "membres": membres_init
                    }
                    st.session_state.db_equipes = pd.concat([st.session_state.db_equipes, pd.DataFrame([new_row])], ignore_index=True)
                    
                    new_emp_chef = {"id": len(st.session_state.db_employes) + 1, "nom": chef_g, "role": "Chef de Groupe", "groupe_id": new_id, "tarif_journalier": 5000}
                    st.session_state.db_employes = pd.concat([st.session_state.db_employes, pd.DataFrame([new_emp_chef])], ignore_index=True)
                    
                    if membres_init:
                        m_list = [m.strip() for m in membres_init.split(",") if m.strip()]
                        for item in m_list:
                            new_emp = {"id": len(st.session_state.db_employes) + 1, "nom": item, "role": "Membre Ouvrier", "groupe_id": new_id, "tarif_journalier": 3000}
                            st.session_state.db_employes = pd.concat([st.session_state.db_employes, pd.DataFrame([new_emp])], ignore_index=True)
                            
                    st.success("✅ Groupe et membres enregistrés avec succès !")
                    st.rerun()
                else:
                    st.error("❌ Le nom du groupe et du chef de groupe sont requis.")

    with t2:
        st.subheader("Ajouter un Membre Individuel à un Groupe")
        if not st.session_state.db_equipes.empty:
            st.dataframe(st.session_state.db_employes, use_container_width=True)
            
            with st.form("form_membre"):
                nom_m = st.text_input("Nom Complet du membre")
                role_m = st.selectbox("Rôle dans le groupe", ["Membre Ouvrier", "Chef de Groupe", "Assistant / Technicien"])
                grp_m = st.selectbox("Groupe d'affectation", st.session_state.db_equipes['nom_groupe'].tolist())
                tarif_m = st.number_input("Tarif journalier (FCFA)", min_value=0, value=3000)
                
                if st.form_submit_button("Rattacher le membre au groupe"):
                    if nom_m:
                        grp_row = st.session_state.db_equipes[st.session_state.db_equipes['nom_groupe'] == grp_m].iloc[0]
                        grp_id = grp_row['id']
                        
                        new_id = len(st.session_state.db_employes) + 1
                        new_row = {"id": new_id, "nom": nom_m, "role": role_m, "groupe_id": grp_id, "tarif_journalier": tarif_m}
                        st.session_state.db_employes = pd.concat([st.session_state.db_employes, pd.DataFrame([new_row])], ignore_index=True)
                        
                        anc_membres = str(grp_row['membres']) if pd.notna(grp_row['membres']) else ""
                        nouveau_membres = f"{anc_membres}, {nom_m}" if anc_membres else nom_m
                        st.session_state.db_equipes.loc[st.session_state.db_equipes['id'] == grp_id, 'membres'] = nouveau_membres
                        
                        st.success(f"✅ {nom_m} ajouté au groupe {grp_m} !")
                        st.rerun()
        else:
            st.warning("Veuillez d'abord créer au moins un groupe dans l'onglet ci-dessus.")

# --- D. POINTAGE DES HORAIRES (GLOBAL & INDIVIDUEL) ---
elif menu == "⏰ Pointage des Horaires":
    st.title("⏰ Registre de Pointage des Horaires de Travail")
    st.caption("Pointage rapide et simultané de l'ensemble de l'effectif ou saisie individuelle.")

    tab_masser, tab_indiv, tab_historique = st.tabs([
        "⚡ Pointage Massif (Tous les employés)", 
        "👤 Pointage Individuel", 
        "📋 Historique & Fiches de Pointage"
    ])

    # --- 1. POINTAGE MASSIF DE TOUS LES EMPLOYÉS ---
    with tab_masser:
        st.subheader("⚡ Saisie Globale pour Tous les Employés")
        
        if st.session_state.db_employes.empty:
            st.warning("⚠️ Aucun employé n'est enregistré pour l'instant. Ajoutez d'abord des employés dans le menu '👥 Groupes & Membres'.")
        else:
            st.markdown("#### 1️⃣ Définir le cadre de travail de la journée")
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                date_p_global = st.date_input("Date du pointage global", value=date.today(), key="p_date_globale")
                parc_p_global = st.selectbox("Parcelle de travail principale", st.session_state.db_champs['nom'].tolist() if not st.session_state.db_champs.empty else ["Général"], key="p_parc_globale")
            
            with col_p2:
                def_arr = st.time_input("Heure Arrivée standard", value=time(8, 0), key="p_arr_def")
                def_pause_dep = st.time_input("Heure Début Pause standard", value=time(12, 0), key="p_pdep_def")
                
            with col_p3:
                def_pause_fin = st.time_input("Heure Fin Pause standard", value=time(13, 0), key="p_pfin_def")
                def_dep = st.time_input("Heure Départ standard", value=time(17, 0), key="p_dep_def")

            st.divider()
            st.markdown("#### 2️⃣ Pré-remplissage & Ajustements par employé")
            st.caption("Modifiez le statut de présence, les horaires ou ajoutez des remarques spécifiques pour chaque ouvrier.")

            df_emp = st.session_state.db_employes.copy()
            grp_map = dict(zip(st.session_state.db_equipes['id'], st.session_state.db_equipes['nom_groupe'])) if not st.session_state.db_equipes.empty else {}
            df_emp['groupe_nom'] = df_emp['groupe_id'].map(grp_map).fillna("N/A")

            df_grid = pd.DataFrame({
                "Employé": df_emp['nom'],
                "Groupe": df_emp['groupe_nom'],
                "Présent(e)": True,
                "Parcelle": parc_p_global,
                "Arrivée": def_arr.strftime("%H:%M"),
                "Début Pause": def_pause_dep.strftime("%H:%M"),
                "Fin Pause": def_pause_fin.strftime("%H:%M"),
                "Départ": def_dep.strftime("%H:%M"),
                "Remarques / Observations": ""
            })

            grid_edited = st.data_editor(
                df_grid,
                use_container_width=True,
                num_rows="fixed",
                column_config={
                    "Présent(e)": st.column_config.CheckboxColumn("Présent ?", help="Décocher si l'employé est absent"),
                    "Arrivée": st.column_config.TextColumn("Arrivée (HH:MM)"),
                    "Début Pause": st.column_config.TextColumn("Début Pause (HH:MM)"),
                    "Fin Pause": st.column_config.TextColumn("Fin Pause (HH:MM)"),
                    "Départ": st.column_config.TextColumn("Départ (HH:MM)"),
                    "Remarques / Observations": st.column_config.TextColumn("Remarque", width="medium")
                },
                disabled=["Employé", "Groupe"],
                key="editor_pointage_massif"
            )

            if st.button("💾 Valider et Enregistrer Tous les Pointages", type="primary", use_container_width=True):
                nouveaux_pointages = []
                
                for _, row in grid_edited.iterrows():
                    is_present = row["Présent(e)"]
                    statut_str = "Présent" if is_present else "Absent"
                    
                    if is_present:
                        try:
                            t_arr = datetime.strptime(row["Arrivée"], "%H:%M")
                            t_dep_p = datetime.strptime(row["Début Pause"], "%H:%M")
                            t_fin_p = datetime.strptime(row["Fin Pause"], "%H:%M")
                            t_dep = datetime.strptime(row["Départ"], "%H:%M")

                            duree_matin = max(0, (t_dep_p - t_arr).total_seconds() / 3600.0)
                            duree_aprem = max(0, (t_dep - t_fin_p).total_seconds() / 3600.0)
                            heures_eff = round(duree_matin + duree_aprem, 2)
                        except Exception:
                            heures_eff = 8.0
                    else:
                        heures_eff = 0.0

                    new_id = len(st.session_state.db_pointage) + len(nouveaux_pointages) + 1
                    nouveaux_pointages.append({
                        "id": new_id,
                        "date": date_p_global,
                        "employe_nom": row["Employé"],
                        "groupe_nom": row["Groupe"],
                        "champ_nom": row["Parcelle"],
                        "statut_presence": statut_str,
                        "heure_arrivee": row["Arrivée"] if is_present else "-",
                        "heure_debut_pause": row["Début Pause"] if is_present else "-",
                        "heure_fin_pause": row["Fin Pause"] if is_present else "-",
                        "heure_depart": row["Départ"] if is_present else "-",
                        "heures_effectives": heures_eff,
                        "remarque": row["Remarques / Observations"] if is_present else "Absent"
                    })

                if nouveaux_pointages:
                    st.session_state.db_pointage = pd.concat([st.session_state.db_pointage, pd.DataFrame(nouveaux_pointages)], ignore_index=True)
                    st.success(f"✅ Pointage groupé enregistré avec succès pour **{len(nouveaux_pointages)} employés** pour la date du {date_p_global.strftime('%d/%m/%Y')} !")
                    st.rerun()

    # --- 2. POINTAGE INDIVIDUEL ---
    with tab_indiv:
        st.subheader("👤 Saisie Individuelle d'un Employé")

        if not st.session_state.db_employes.empty:
            with st.form("form_pointage_detail"):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    date_p = st.date_input("Date du pointage", value=date.today(), key="p_ind_date")
                    emp_p = st.selectbox("Sélectionner l'Employé / Membre", st.session_state.db_employes['nom'].tolist(), key="p_ind_emp")
                    parc_p = st.selectbox("Parcelle de travail", st.session_state.db_champs['nom'].tolist() if not st.session_state.db_champs.empty else ["Général"], key="p_ind_parc")
                    statut_indiv = st.selectbox("Statut de présence", ["Présent", "Absent", "Congé / Justifié"])

                with col_b:
                    h_arr = st.time_input("Heure d'Arrivée (Prise de poste)", value=time(8, 0), key="p_ind_harr")
                    h_dep_p = st.time_input("Heure Début de Pause", value=time(12, 0), key="p_ind_hdep_p")

                with col_c:
                    h_fin_p = st.time_input("Heure Fin de Pause", value=time(13, 0), key="p_ind_hfin_p")
                    h_dep = st.time_input("Heure de Départ (Fin de journée)", value=time(17, 0), key="p_ind_hdep")

                remarque_p = st.text_input("Remarques / Retard / Heures Sup.", key="p_ind_rem")

                if st.form_submit_button("💾 Valider le Pointage Individuel", use_container_width=True):
                    if statut_indiv == "Présent":
                        t_arr = datetime.combine(date.today(), h_arr)
                        t_dep_p = datetime.combine(date.today(), h_dep_p)
                        t_fin_p = datetime.combine(date.today(), h_fin_p)
                        t_dep = datetime.combine(date.today(), h_dep)

                        duree_matin = max(0, (t_dep_p - t_arr).total_seconds() / 3600.0)
                        duree_aprem = max(0, (t_dep - t_fin_p).total_seconds() / 3600.0)
                        heures_eff = round(duree_matin + duree_aprem, 2)
                    else:
                        heures_eff = 0.0

                    emp_row = st.session_state.db_employes[st.session_state.db_employes['nom'] == emp_p].iloc[0]
                    grp_id = emp_row['groupe_id']
                    grp_nom = st.session_state.db_equipes[st.session_state.db_equipes['id'] == grp_id]['nom_groupe'].values[0] if not st.session_state.db_equipes.empty else "N/A"

                    new_id = len(st.session_state.db_pointage) + 1
                    new_row = {
                        "id": new_id,
                        "date": date_p,
                        "employe_nom": emp_p,
                        "groupe_nom": grp_nom,
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
                    st.success(f"✅ Pointage individuel pour {emp_p} enregistré ! ({heures_eff} h effectives)")
                    st.rerun()
        else:
            st.warning("Veuillez d'abord enregistrer des membres dans la section '👥 Groupes & Membres'.")

    # --- 3. HISTORIQUE DE POINTAGE ---
    with tab_historique:
        st.subheader("📋 Historique complet des pointages")
        st.dataframe(st.session_state.db_pointage, use_container_width=True)

# --- E. PLANNING & TRAVAUX ---
elif menu == "📅 Planning & Travaux":
    st.title(f"📅 Attribution des Tâches - Parcelle : {champ_selectionne}")
    if champ_id_actif:
        taches = st.session_state.db_taches[st.session_state.db_taches['champ_id'] == champ_id_actif]
        st.dataframe(taches, use_container_width=True)
        
        if not st.session_state.db_equipes.empty:
            with st.form("form_tache"):
                st.write("### ➕ Programmer un travail")
                eq_t = st.selectbox("Groupe en charge", st.session_state.db_equipes['nom_groupe'].tolist())
                act_t = st.selectbox("Nature des travaux", ["Labour / Préparation", "Semis / Repiquage", "Irrigation", "Désherbage / Biffage", "Fertilisation", "Traitement Phytosanitaire", "Récolte"])
                hrs_t = st.number_input("Heures prévues", min_value=1.0, value=6.0)
                stt_t = st.selectbox("Statut", ["Planifié", "En cours", "Terminé"])
                
                if st.form_submit_button("Valider l'affectation"):
                    eq_id = st.session_state.db_equipes[st.session_state.db_equipes['nom_groupe'] == eq_t]['id'].values[0]
                    new_id = len(st.session_state.db_taches) + 1
                    new_row = {"id": new_id, "champ_id": champ_id_actif, "groupe_id": eq_id, "type_travail": act_t, "date_tache": date.today(), "heures_travaillees": hrs_t, "statut": stt_t}
                    st.session_state.db_taches = pd.concat([st.session_state.db_taches, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("Tâche planifiée !")
                    st.rerun()
        else:
            st.warning("Créez d'abord un groupe dans '👥 Groupes & Membres'.")

# --- F. RÉCOLTES & RENDEMENTS ---
elif menu == "🌾 Récoltes & Rendements":
    st.title(f"🌾 Suivi des Pesées : {champ_selectionne}")
    if champ_id_actif:
        recs = st.session_state.db_recoltes[st.session_state.db_recoltes['champ_id'] == champ_id_actif]
        st.dataframe(recs, use_container_width=True)
        
        with st.form("form_rec"):
            c1, c2, c3 = st.columns(3)
            cult = c1.text_input("Variété récoltée")
            qte = c2.number_input("Quantité (Kg)", min_value=0.0)
            pu = c3.number_input("Prix unitaire (FCFA)", min_value=0, value=350)
            if st.form_submit_button("Enregistrer la pesée"):
                new_row = {"champ_id": champ_id_actif, "culture": cult, "date_recolte": date.today(), "quantite_kg": qte, "prix_unitaire": pu}
                st.session_state.db_recoltes = pd.concat([st.session_state.db_recoltes, pd.DataFrame([new_row])], ignore_index=True)
                st.success("Pesée enregistrée !")
                st.rerun()

# --- G. FINANCES & MARGES (AVEC CAPTURE DE FACTURE) ---
elif menu == "💰 Finances & Marges":
    st.title(f"💰 Bilan Financier & Factures : {champ_selectionne}")
    if champ_id_actif:
        deps = st.session_state.db_depenses[st.session_state.db_depenses['champ_id'] == champ_id_actif]
        st.dataframe(deps, use_container_width=True)
        
        st.subheader("➕ Enregistrer une nouvelle dépense / facture")
        with st.form("form_dep", clear_on_submit=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                motif = st.text_input("Motif de la dépense *")
                mnt = st.number_input("Montant (FCFA) *", min_value=0, step=500)
                date_dep = st.date_input("Date de la dépense", value=date.today())
            with col_f2:
                facture_file = st.file_uploader("📸 Joindre / Photographier la facture (Image ou PDF)", type=['jpg', 'jpeg', 'png', 'pdf'])
            
            if st.form_submit_button("💾 Enregistrer la dépense"):
                if motif and mnt > 0:
                    fact_name = facture_file.name if facture_file else "Aucune"
                    new_row = {
                        "champ_id": champ_id_actif, 
                        "type": motif, 
                        "montant": mnt, 
                        "date": date_dep,
                        "facture_nom": fact_name
                    }
                    st.session_state.db_depenses = pd.concat([st.session_state.db_depenses, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"✅ Dépense enregistrée avec succès ! (Facture : {fact_name})")
                    st.rerun()
                else:
                    st.error("❌ Veuillez renseigner le motif et un montant valide.")

        if facture_file:
            st.subheader("📸 Aperçu de la facture jointe :")
            if facture_file.type.startswith('image/'):
                st.image(facture_file, width=300)
            else:
                st.info(f"📄 Fichier PDF attaché : {facture_file.name}")

# --- H. STOCKS D'INTRANTS (AVEC CAPTURE DE FACTURE) ---
elif menu == "📦 Stocks d'Intrants":
    st.title("📦 Gestion du Magasin, Intrants & Factures d'Achat")
    st.dataframe(st.session_state.db_intrants, use_container_width=True)
    
    st.subheader("➕ Réceptionner un Produit / Approvisionnement")
    with st.form("form_intrant", clear_on_submit=True):
        col_i1, col_i2 = st.columns(2)
        with col_i1:
            nom_i = st.text_input("Nom de l'intrant / Produit *")
            cat_i = st.selectbox("Catégorie", ["Engrais", "Herbicide", "Fongicide", "Insecticide", "Semences", "Carburant", "Autres"])
            stk_i = st.number_input("Quantité reçue / en stock", min_value=0)
            unit_i = st.text_input("Unité (Sacs, Litres, Kg, Boîtes)")
            seuil_i = st.number_input("Seuil d'alerte stock bas", min_value=1, value=5)
        
        with col_i2:
            facture_i = st.file_uploader("📸 Joindre le bon de commande / Facture fournisseur", type=['jpg', 'jpeg', 'png', 'pdf'])
        
        if st.form_submit_button("💾 Enregistrer au magasin"):
            if nom_i:
                fact_name = facture_i.name if facture_i else "Aucune"
                new_row = {
                    "nom": nom_i, 
                    "categorie": cat_i, 
                    "stock_actuel": stk_i, 
                    "unite": unit_i, 
                    "seuil_alerte": seuil_i,
                    "facture_nom": fact_name
                }
                st.session_state.db_intrants = pd.concat([st.session_state.db_intrants, pd.DataFrame([new_row])], ignore_index=True)
                st.success("✅ Intrant enregistré au magasin !")
                st.rerun()
            else:
                st.error("❌ Le nom du produit est obligatoire.")

# --- I. PLUVIOMÉTRIE ---
elif menu == "🌧️ Pluviométrie":
    st.title(f"🌧️ Relevés Pluviométriques : {champ_selectionne}")
    if champ_id_actif:
        st.dataframe(st.session_state.db_pluviometrie[st.session_state.db_pluviometrie['champ_id'] == champ_id_actif], use_container_width=True)
        
        with st.form("form_pluie"):
            mm = st.number_input("Précipitations (mm)", min_value=0.0, step=0.5)
            if st.form_submit_button("Saisir la pluie"):
                new_row = {"champ_id": champ_id_actif, "date": date.today(), "pluie_mm": mm}
                st.session_state.db_pluviometrie = pd.concat([st.session_state.db_pluviometrie, pd.DataFrame([new_row])], ignore_index=True)
                st.success("Relevé enregistré !")
                st.rerun()

# --- J. INCIDENTS ---
elif menu == "⚠️ Incidents":
    st.title(f"⚠️ Traitement & Incidents Sanitaires : {champ_selectionne}")
    if champ_id_actif:
        st.dataframe(st.session_state.db_incidents[st.session_state.db_incidents['champ_id'] == champ_id_actif], use_container_width=True)
        
        with st.form("form_inc"):
            desc = st.text_area("Description du problème")
            grav = st.selectbox("Gravité", ["Faible", "Moyenne", "Élevée"])
            act = st.text_input("Action à entreprendre")
            if st.form_submit_button("Déclarer l'incident"):
                new_row = {"champ_id": champ_id_actif, "date": date.today(), "description": desc, "gravite": grav, "action": act}
                st.session_state.db_incidents = pd.concat([st.session_state.db_incidents, pd.DataFrame([new_row])], ignore_index=True)
                st.success("Incident enregistré !")
                st.rerun()

# --- K. MAINTENANCE MATÉRIEL ---
elif menu == "🚜 Maintenance Matériel (Nouveau)":
    st.title("🚜 1. Gestion du Parc Matériel & Maintenance")
    st.dataframe(st.session_state.db_materiel, use_container_width=True)
    
    with st.form("form_mat"):
        nom_mat = st.text_input("Nom de l'Équipement")
        cat_mat = st.selectbox("Catégorie", ["Tracteur", "Motopompe", "Pulvérisateur", "Moissonneuse", "Autre"])
        statut_mat = st.selectbox("Statut", ["Opérationnel", "En maintenance", "Hors service"])
        d_prev = st.date_input("Prochaine révision", value=date.today())
        
        if st.form_submit_button("Ajouter Matériel"):
            if nom_mat:
                new_row = {
                    "id": len(st.session_state.db_materiel)+1, 
                    "nom_equipement": nom_mat, 
                    "categorie": cat_mat, 
                    "statut_marche": statut_mat, 
                    "date_derniere_revision": date.today(), 
                    "prochaine_revision": d_prev
                }
                st.session_state.db_materiel = pd.concat([st.session_state.db_materiel, pd.DataFrame([new_row])], ignore_index=True)
                st.success("Matériel enregistré !")
                st.rerun()

# --- L. TRAÇABILITÉ & LOTS (CORRIGÉ & FONCTIONNEL) ---
elif menu == "🏷️ Traçabilité & Lots (Nouveau)":
    st.title("🏷️ 2. Traçabilité des Lots & Certification")
    st.dataframe(st.session_state.db_tracabilite, use_container_width=True)

    st.subheader("➕ Créer un Code Lot de Traçabilité")
    with st.form("form_tracabilite", clear_on_submit=True):
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            code_lot = st.text_input("Code unique du Lot", value=f"LOT-{date.today().strftime('%Y%m%d')}-01")
            parcelle_lot = st.selectbox("Parcelle d'origine", st.session_state.db_champs['nom'].tolist() if not st.session_state.db_champs.empty else ["Général"])
            culture_lot = st.text_input("Culture / Variété", value="Riz / Maïs")
        with col_t2:
            date_rec_lot = st.date_input("Date de récolte du lot", value=date.today())
            certif = st.selectbox("Norme / Certification", ["Bio / GlobalGAP", "Conforme Norme Nationale", "Standard", "En cours de contrôle"])
            client_lot = st.text_input("Destinataire / Client / Acheteur", placeholder="Ex: Grossiste / Usine")

        if st.form_submit_button("💾 Créer le Lot de Traçabilité"):
            new_id = len(st.session_state.db_tracabilite) + 1
            new_row = {
                "id": new_id,
                "lot_code": code_lot,
                "champ_nom": parcelle_lot,
                "culture": culture_lot,
                "date_recolte": date_rec_lot,
                "norme_certification": certif,
                "acheteur": client_lot
            }
            st.session_state.db_tracabilite = pd.concat([st.session_state.db_tracabilite, pd.DataFrame([new_row])], ignore_index=True)
            st.success(f"✅ Lot '{code_lot}' enregistré avec succès !")
            st.rerun()

# --- M. IRRIGATION & EAU (CORRIGÉ & FONCTIONNEL) ---
elif menu == "💧 Irrigation & Eau (Nouveau)":
    st.title("💧 3. Irrigation & Suivi des Volumes d'Eau")
    st.dataframe(st.session_state.db_irrigation, use_container_width=True)

    st.subheader("➕ Enregistrer une session d'irrigation")
    with st.form("form_irrigation", clear_on_submit=True):
        col_i1, col_i2 = st.columns(2)
        with col_i1:
            parcelle_irr = st.selectbox("Parcelle irriguée", st.session_state.db_champs['nom'].tolist() if not st.session_state.db_champs.empty else ["Général"])
            date_irr = st.date_input("Date d'irrigation", value=date.today())
            methode_irr = st.selectbox("Méthode d'irrigation", ["Goutte-à-goutte", "Aspersion", "Submersion / Gravitaire", "Canon à eau"])
        with col_i2:
            vol_eau = st.number_input("Volume d'eau consommé (m³)", min_value=0.0, value=50.0, step=5.0)
            duree_irr = st.number_input("Durée du pompage / d'arrosage (Heures)", min_value=0.5, value=3.0, step=0.5)

        if st.form_submit_button("💾 Enregistrer la session d'irrigation"):
            new_id = len(st.session_state.db_irrigation) + 1
            new_row = {
                "id": new_id,
                "champ_nom": parcelle_irr,
                "date": date_irr,
                "volume_eau_m3": vol_eau,
                "methode": methode_irr,
                "duree_heures": duree_irr
            }
            st.session_state.db_irrigation = pd.concat([st.session_state.db_irrigation, pd.DataFrame([new_row])], ignore_index=True)
            st.success("✅ Session d'irrigation enregistrée !")
            st.rerun()

# --- N. RISQUES & MÉTÉO (CORRIGÉ & FONCTIONNEL) ---
elif menu == "🌤️ Risques & Météo (Nouveau)":
    st.title("🌤️ 4. Gestion des Risques & Directives Météo")
    st.dataframe(st.session_state.db_alertes_meteo, use_container_width=True)

    st.subheader("➕ Émettre une Alerte Météo ou Consigne Technicien")
    with st.form("form_meteo", clear_on_submit=True):
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            date_met = st.date_input("Date du bulletin / Alerte", value=date.today())
            type_r = st.selectbox("Type de Risque", ["Vague de chaleur / Sécheresse", "Inondation / Pluie violente", "Vent fort / Tempête", "Invasion de ravageurs", "Gel / Froid extrême"])
            niv_a = st.selectbox("Niveau d'Alerte", ["🟢 Faible / Vigilance", "🟡 Modéré / Attention", "🔴 Élevé / Urgence"])
        with col_m2:
            consigne_ts = st.text_area("Recommandation / Directives du TS", placeholder="Exemple : Suspendre l'épandage d'engrais et renforcer l'ancrage des serres.")

        if st.form_submit_button("💾 Publier l'Alerte / Directive"):
            new_id = len(st.session_state.db_alertes_meteo) + 1
            new_row = {
                "id": new_id,
                "date": date_met,
                "type_risque": type_r,
                "niveau_alerte": niv_a,
                "recommandation_ts": consigne_ts
            }
            st.session_state.db_alertes_meteo = pd.concat([st.session_state.db_alertes_meteo, pd.DataFrame([new_row])], ignore_index=True)
            st.success("✅ Alerte météo enregistrée !")
            st.rerun()

# --- O. RENTABILITÉ & ROI ---
elif menu == "📈 Rentabilité & ROI (Nouveau)":
    st.title("📈 5. Calculateur de Rentabilité & ROI")
    if not st.session_state.db_champs.empty:
        res = []
        for _, c in st.session_state.db_champs.iterrows():
            cid = c['id']
            ca = st.session_state.db_recoltes[st.session_state.db_recoltes['champ_id'] == cid].apply(lambda x: x['quantite_kg']*x['prix_unitaire'], axis=1).sum() if not st.session_state.db_recoltes.empty else 0
            ch = st.session_state.db_depenses[st.session_state.db_depenses['champ_id'] == cid]['montant'].sum() if not st.session_state.db_depenses.empty else 0
            res.append({"Parcelle": c['nom'], "Ventes (FCFA)": ca, "Charges (FCFA)": ch, "Marge Nette": ca - ch})
        st.dataframe(pd.DataFrame(res), use_container_width=True)

# =========================================================================
# EXPORT COMPLET
# =========================================================================
elif menu == "📑 EXPORT COMPLET (Toutes données + Signature)":
    st.title("📑 Générateur de Rapport Synthétique d'Exploitation")
    st.info("Ce module rassemble **absolument tout ce que vous avez renseigné** dans l'application, classé par date avec une section réservée aux **signatures officielles**.")

    st.subheader("🗓️ Choisir la Date du Rapport")
    date_export = st.date_input("Sélectionner la journée de travail à éditer :", value=date.today())

    st.divider()
    st.write("### 🖨️ Téléchargement des Fichiers de Synthèse")
    
    col_dl1, col_dl2 = st.columns(2)
    
    with col_dl1:
        st.markdown("#### 📄 Rapport PDF Certifié (avec Signatures)")
        st.caption("Document officiel prêt à imprimer contenant toutes les sections et l'espace pour signer.")
        
        pdf_data = export_global_pdf(date_export)
        st.download_button(
            label="📥 Télécharger le Rapport PDF Général avec Signatures",
            data=pdf_data,
            file_name=f"Rapport_Complet_AgriGestion_{date_export.strftime('%Y-%m-%d')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    with col_dl2:
        st.markdown("#### 📊 Classeur Excel Multi-Feuilles")
        st.caption("Exportation brute de toutes les tables de la base de données (Pointages, Récoltes, Finances, etc.).")
        
        excel_data = export_global_to_excel()
        st.download_button(
            label="📥 Télécharger le Registre Excel Global (.xlsx)",
            data=excel_data,
            file_name=f"Base_De_Donnees_AgriGestion_{date_export.strftime('%Y-%m-%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
