"""Generate PDF documentation for the Simulation page (A to Z + constraints)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.pdf_builder import DocPDF  # noqa: E402


def build_pdf() -> DocPDF:
    pdf = DocPDF(doc_title="Page Simulation - BTS EMS")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.cover(
        "Page Simulation BTS EMS",
        "Guide complet de A a Z, pipeline technique et contraintes",
    )

    pdf.h2("1. Objectif de la page")
    pdf.p(
        "La page Simulation (menu 6 du dashboard Streamlit) reproduit le fonctionnement "
        "energetique d'un parc de stations BTS sur une date choisie, heure par heure. "
        "Elle enchaine prediction NB1, detection d'anomalies NB2 et decisions d'optimisation "
        "NB3 sur des donnees synthetiques derivees du referentiel historique Tunisie Telecom."
    )
    pdf.bullet(
        [
            "Fichier principal UI : views/p5_simulation.py",
            "Logique metier partagee : views/simulation_common.py",
            "Composants visuels : views/simulation_ui.py",
            "Generation horaire : services/synthetic_bts.py",
            "Evenements (alertes / journal) : services/simulation_events.py",
            "Calendrier tunisien : services/calendar_tn.py",
        ]
    )

    pdf.h2("2. Acces, securite et perimetre")
    pdf.p(
        "L'acces passe par security_middleware.enforce() au chargement de la page. "
        "Seules les stations autorisees pour le role connecte sont proposables."
    )
    pdf.table(
        ["Role", "Perimetre stations", "Remarque"],
        [
            ["Administrateur", "Toutes les stations du dataset", "Vue reseau complete"],
            ["Ingenieur reseau", "Stations assignees", "engineer_assigned_stations()"],
            ["Autre / non auth", "Acces bloque", "Redirection login"],
        ],
        [45, 55, 90],
    )
    pdf.p(
        "Si aucune station n'est disponible sur le perimetre, un avertissement "
        "'Aucune station disponible sur votre perimetre.' stoppe la page."
    )

    pdf.h2("3. Parcours utilisateur de A a Z")
    pdf.h3("Etape A - Arrivee sur la page")
    pdf.bullet(
        [
            "Titre : Simulation - Parc BTS a une date donnee, heure par heure",
            "Purge automatique d'une session obsolete (purge_stale_sim_session)",
            "Date par defaut : filtre global actif, sinon sb_date_from, sinon date du jour",
            "Chargement du moteur de reference sim_engine() (cache session)",
        ]
    )

    pdf.h3("Etape B - Barre d'outils (toolbar)")
    pdf.table(
        ["Controle", "Cle session", "Description"],
        [
            ["Stations", "sim_stations", "Multiselect + Tout / Reinit."],
            ["Date", "sim_date", "Jour du scenario"],
            ["Debut", "sim_start_hour", "Heure de demarrage 00h-23h"],
            ["Demarrer", "-", "Lance sim_running + 1ere heure"],
            ["Pause / Reprendre", "sim_paused", "Gele l'avancement auto"],
            ["Stop", "-", "reset_simulation() efface la session sim"],
        ],
        [40, 45, 105],
    )

    pdf.h3("Etape C - Demarrer une simulation pas a pas")
    pdf.bullet(
        [
            "Reinitialise sim_data, sim_alerts, sim_decisions, sim_tick=0",
            "Calcule sim_total_ticks selon date, heure debut et duree (jours)",
            "bootstrap_simulation() genere la premiere heure",
            "maybe_autorefresh() avance +1 h toutes les N secondes (defaut 30 s)",
            "process_tick() consomme sim_advance et appelle advance_simulation(steps=1)",
            "A la fin du scenario, sim_running passe a False automatiquement",
        ]
    )

    pdf.h3("Etape D - Options avancees (expander)")
    pdf.bullet(
        [
            "Duree (jours) : sim_num_days de 1 a 7 jours",
            "Intervalle (+1 h) : sim_auto_interval de 10 a 120 secondes",
            "Simuler la journee complete : execute toutes les heures restantes du jour en batch",
            "Exports CSV + PDF sommaire disponibles si sim_data non vide",
        ]
    )

    pdf.h3("Etape E - Bandeau d'information et progression")
    pdf.p(
        "Affiche l'heure simulee, le libelle calendaire (week-end, feries TN, Ramadan), "
        "le nombre de stations, la progression tick/total et l'etat Pause ou +1h/Ns."
    )

    pdf.h3("Etape F - KPIs reseau (5 metriques)")
    pdf.table(
        ["Metrique", "Calcul", "Unite"],
        [
            ["Heure simulee", "timestamp max de sim_data", "HH:MM"],
            ["Conso reseau", "Somme consommation_kwh derniere heure", "kWh"],
            ["Gain heure", "total_gain_kwh(latest) x PRIX_KWH_TN", "DT"],
            ["Gain cumule", "total_gain_kwh(sim_data) cumule", "DT / kWh"],
            ["Alertes ouvertes", "Alertes non acquittees (sim_ack_refs)", "nombre"],
        ],
        [45, 95, 50],
    )

    pdf.h3("Etape G - Table Etat du parc")
    pdf.p(
        "Tableau Streamlit de la derniere heure simulee : Station, Mode, Conso, Predit, "
        "Ecart %, Gain (DT), QoS, Anomalie, Action (RL prioritaire)."
    )

    pdf.h3("Etape H - Detail station (decision card)")
    pdf.p(
        "Selectbox 'Detail d'une station' affiche une carte : badge mode (NORMAL, ECO, "
        "ATTENTION, CRITIQUE), action expert, explication mode_explanation(), ecart reel/predit "
        "et gain estime en DT et kWh."
    )

    pdf.h3("Etape I - Onglet Courbe")
    pdf.bullet(
        [
            "Graphique Plotly : consommation reelle, predite LightGBM, consommation optimisee",
            "Focus une station ou somme horaire du parc selectionne",
            "Lignes verticales : heures avec alertes",
            "KPIs sous le graphique + avertissements pipeline legacy",
        ]
    )

    pdf.h3("Etape J - Onglet Journal")
    pdf.bullet(
        [
            "Alertes a verifier : Traite / Ignorer (persiste en SQLite via persist_alert_ack)",
            "Actions appliquees : historique des decisions NB3 avec gain estime",
            "Maximum 6 alertes pending visibles, 20 decisions dans le tableau",
        ]
    )

    pdf.h3("Etape K - Onglet Carte")
    pdf.p(
        "Carte mini parc : positions GPS, couleur par mode_operation, popup action a faire. "
        "Requiert latitude/longitude dans les donnees."
    )

    pdf.h3("Etape L - Exports")
    pdf.bullet(
        [
            "CSV : simulation_donnees.csv (toutes les lignes sim_data)",
            "PDF sommaire : total reseau, detail par station, alertes (generate_simulation_sommaire_pdf)",
        ]
    )

    pdf.h2("4. Pipeline technique horaire")
    pdf.h3("4.1 Construction synthetique (_build_hourly_rows)")
    pdf.p(
        "Pour chaque station et chaque heure, le moteur pioche un profil historique "
        "(station, heure, mois, week-end, Ramadan, feries), applique un facteur calendaire "
        "et un jitter deterministe (seed = hash station+date+heure)."
    )

    pdf.h3("4.2 Enrichissement NB1 + NB2 + NB3")
    pdf.bullet(
        [
            "Mode interactif : enrich_with_pipeline() -> run_nb_pipeline() si artefacts Hub",
            "Fallback : apply_offline_nb23() si pipeline indisponible ou erreur",
            "Journee complete : generate_period() concatene toutes les heures puis pipeline en batch (chunks 360 lignes)",
            "Harmonisation economies : max(expert, RL) plafonne a NB3_MAX_ECO_FRAC (48%) de la conso",
        ]
    )

    pdf.h3("4.3 Moteur de modes (NB3)")
    pdf.table(
        ["Mode", "Conditions principales", "Action type"],
        [
            ["CRITIQUE", "Score anomalie eleve ou >=5 votes", "Alerte NOC"],
            ["ATTENTION", "Ecart > 30% ou score + votes", "Monitoring renforce"],
            ["ECO", "Score bas, CPU<50%, creneau 0h-6h, QoS OK", "Sleep / reduction / free cooling"],
            ["NORMAL", "Sinon", "Monitoring standard"],
        ],
        [35, 85, 70],
    )

    pdf.h3("4.4 Strategies expert (action_proposee)")
    pdf.bullet(
        [
            "sleep_mode_secteur : 1h-5h, charge voix/data < 15%, QoS > 0.8",
            "reduction_puissance : 4G/3G, puissance > 40.5 dBm, CPU < 50%",
            "free_cooling : T<22C, vent>3 m/s, humidite<75%",
            "eco_calendaire : week-end ou ferie, 2h-6h, charge data faible",
            "alerte_noc_prioritaire : ecrase si mode CRITIQUE ou score > 0.6",
        ]
    )

    pdf.h2("5. Moteur d'alertes et journal")
    pdf.p("classify_tick_rows() analyse chaque ligne horaire et produit alertes + decisions.")
    pdf.table(
        ["Type alerte", "Declencheur", "Severite"],
        [
            ["mode_critique", "mode_operation = CRITIQUE", "CRITIQUE"],
            ["ecart_conso", "|ecart_pct| >= 30% et QoS OK", "ATTENTION ou CRITIQUE si >=50%"],
            ["anomalie_sans_action", "score >= seuil NB2 sans action nommee", "ATTENTION/CRITIQUE"],
            ["qos_risque", "anomalie + QoS < seuil", "CRITIQUE"],
        ],
        [45, 85, 60],
    )
    pdf.p(
        "Decisions journalisees si action nommee (free cooling, sleep, etc.) avec economie estimee, "
        "ou si economie > 0.05 kWh en mode ECO/ATTENTION/CRITIQUE."
    )

    pdf.h2("6. Etat de session Streamlit (cles principales)")
    pdf.table(
        ["Cle", "Type", "Role"],
        [
            ["sim_data", "DataFrame", "Historique horaire toutes stations"],
            ["sim_running", "bool", "Simulation pas-a-pas active"],
            ["sim_paused", "bool", "Pause autorefresh"],
            ["sim_tick", "int", "Nombre d'heures deja simulees"],
            ["sim_total_ticks", "int", "Total heures du scenario"],
            ["sim_alerts", "list", "Journal alertes (max 300)"],
            ["sim_decisions", "list", "Journal actions (max 300)"],
            ["sim_ack_refs", "set", "Alertes traitees / ignorees"],
            ["sim_schema_version", "int", "Invalidation si version change (v3)"],
            ["sim_full_day_request", "bool", "Declencheur journee complete"],
        ],
        [50, 35, 105],
    )

    pdf.h2("7. Contraintes fonctionnelles")
    pdf.bullet(
        [
            "Au moins 1 station selectionnee pour demarrer ou simuler la journee",
            "Heure de debut : entier 0-23 ; fin du 1er jour a 23h inclus",
            "Multi-jours : jours suivants de 0h a 23h (scenario_timestamps)",
            "Nombre max de ticks = (24 - start_hour) + 24 x (num_days - 1)",
            "Prix energie : PRIX_KWH_TN = 0.40 DT/kWh (config/settings.py)",
            "Seuil QoS par defaut : 0.6 ; optimisation autorisee si score_qos >= seuil",
            "Economie max par ligne : 48% de consommation_kwh (NB3_MAX_ECO_FRAC)",
            "Alertes acquittees persistees en base SQLite (dashboard_ops.sqlite3)",
            "Ingenieur : ne voit que ses stations assignees",
        ]
    )

    pdf.h2("8. Contraintes techniques et limites")
    pdf.bullet(
        [
            "Dependance streamlit-autorefresh pour avancement automatique (optionnel)",
            "Pipeline ML : necessite artefacts HuggingFace (pipeline_inference.joblib, etc.)",
            "Sans Hub : mode offline NB23 (resultats moins riches, pas de LightGBM live)",
            "Session stale purgee si inference_pipeline legacy ou schema v3 incompatible",
            "sim_data tronque : max(72, 24 x jours) x nb_stations lignes (append tail)",
            "Journee complete : 1 appel pipeline batch (chunks) pour limiter timeout Streamlit Cloud",
            "Carte : indisponible si coordonnees GPS absentes",
            "Exports PDF : encodage latin-1 (accents simplifies dans le footer PDF app)",
            "Determinisme partiel : jitter horaire seed fixe, mais RL peut varier selon artefacts",
            "Performance : parc large (>15 stations) + journee complete = plusieurs secondes a dizaines de secondes",
        ]
    )

    pdf.h2("9. Formules metier essentielles")
    pdf.bullet(
        [
            "ecart_pct = (conso_reelle - conso_predite) / conso_predite x 100",
            "economie_kwh = min(max(economie_estimee_kwh, economie_rl_kwh), 48% x conso)",
            "conso_optimisee_kwh = max(conso - economie_kwh, 0)",
            "gain_DT = economie_kwh x 0.40",
            "progression = sim_tick / sim_total_ticks",
        ]
    )

    pdf.h2("10. Scenarios de test recommandes (demo jury)")
    pdf.bullet(
        [
            "Demo rapide : 1-3 stations, debut 08h, Demarrer, laisser avancer 2-3 ticks",
            "Demo complete : Options avancees > Simuler la journee complete",
            "Demo alertes : choisir date week-end + station 4G, observer free cooling / eco calendaire",
            "Demo NOC : station avec ecart simule eleve -> alerte ecart_conso",
            "Export jury : CSV + PDF sommaire apres simulation terminee",
        ]
    )

    pdf.h2("11. FAQ jury (extraits)")
    pdf.qa(
        1,
        "La simulation utilise-t-elle des donnees reelles temps reel ?",
        "Non. Ce sont des snapshots synthetiques bases sur profils historiques, enrichis par NB1/NB2/NB3.",
    )
    pdf.qa(
        2,
        "Pourquoi NORMAL avec action Free cooling ?",
        "Le mode reflète l'urgence reseau ; l'action expert reflete une optimisation energétique possible selon la meteo.",
    )
    pdf.qa(
        3,
        "Que fait le bouton Simuler la journee complete ?",
        "Genere en une fois toutes les heures de  start_hour a 23h via generate_period(), sans attendre l'autorefresh.",
    )
    pdf.qa(
        4,
        "Comment est calcule le gain affiche ?",
        "Max des economies expert et RL, harmonisees et plafonnees, converties en DT au tarif 0.40 DT/kWh.",
    )
    pdf.qa(
        5,
        "Que se passe-t-il si le pipeline Hub est indisponible ?",
        "Fallback offline : regles NB2/NB3 simplifiees, courbes et modes restent coherents mais sans LightGBM live.",
    )

    pdf.h2("12. References code")
    pdf.bullet(
        [
            "views/p5_simulation.py - page_simulation(), toolbar, journal, KPIs",
            "views/simulation_common.py - bootstrap, advance, exports, cartes, graphiques",
            "services/synthetic_bts.py - hourly_snapshot, generate_period, sim_engine",
            "services/simulation_events.py - classify_tick_rows, persist_alert_ack",
            "services/optimization_service.py - regles action_proposee / economie_estimee",
            "services/decision_service.py - mode_operation CRITIQUE/ATTENTION/ECO/NORMAL",
            "utils/pdf_export.py - generate_simulation_sommaire_pdf",
            "config/settings.py - PRIX_KWH_TN, NB3_MAX_ECO_FRAC, SIM_SCHEMA_VERSION",
        ]
    )

    return pdf


def main() -> None:
    out = ROOT / "docs" / "Page_Simulation_BTS_EMS.pdf"
    pdf = build_pdf()
    pdf.save(out)
    print(f"PDF genere : {out}")


if __name__ == "__main__":
    main()
