"""Ultra-hard jury Q&A for Simulation page and BTS EMS pipeline."""

from __future__ import annotations

SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Architecture et positionnement produit",
        [
            (
                "Pourquoi une page Simulation separee au lieu d'utiliser uniquement l'historique reel ?",
                "L'historique (pages 1-5) lit des exports parquet pre-calcules. La Simulation "
                "re-joue un scenario contrefactuel horaire (date/heure/stations choisies) en "
                "re-inferant NB1+NB2+NB3. C'est un bac a sable what-if pour demo jury et "
                "formation NOC sans modifier les donnees de production.",
            ),
            (
                "Quelle est la difference entre Simulation et page Optimisation RL (NB3) ?",
                "Optimisation RL affiche l'etat agrege du reseau sur le dataset exporte. "
                "Simulation genere des donnees synthetiques pas a pas, journalise alertes/decisions "
                "dans session_state et permet pause, multi-jours, replay demo live.",
            ),
            (
                "La Simulation est-elle du temps reel ?",
                "Non. Chaque heure est calculee a la demande a partir de profils historiques "
                "(_pick_profile) + jitter deterministe. L'autorefresh (30 s par defaut) simule "
                "le defilement du temps pour la demo, pas une connexion SNMP/EMS live.",
            ),
            (
                "Quels fichiers forment la couche presentation vs metier ?",
                "UI: views/p5_simulation.py, views/simulation_ui.py. Metier: "
                "views/simulation_common.py, services/synthetic_bts.py, services/simulation_events.py, "
                "services/sim_inference.py, services/nb_inference.py.",
            ),
            (
                "Pourquoi Streamlit et pas une API REST + front separe ?",
                "Choix PFE: time-to-demo, deploiement Streamlit Cloud, acces direct aux "
                "artefacts Hub. En production TT, on isolerait inference (FastAPI/batch) "
                "et garderait Streamlit ou Grafana comme couche viz.",
            ),
            (
                "Comment garantissez-vous la coherence avec les notebooks NB1/NB2/NB3 ?",
                "Memes artefacts joblib sur HuggingFace, run_nb_pipeline() partage entre "
                "dashboard et notebooks. Fallback apply_offline_nb23() si Hub indisponible. "
                "SIM_SCHEMA_VERSION=3 purge les sessions legacy incompatibles.",
            ),
        ],
    ),
    (
        "Mecanique interne de la Simulation",
        [
            (
                "Que se passe-t-il exactement quand on clique Demarrer ?",
                "reset partiel session sim, sim_running=True, sim_tick=0, calcul "
                "sim_total_ticks via scenario_timestamps(), bootstrap_simulation() appelle "
                "advance_scenario(steps=1) -> hourly_snapshot -> enrich_with_pipeline -> "
                "append_sim_data + record_events.",
            ),
            (
                "Comment est calcule sim_total_ticks pour 3 jours demarrant a 14h ?",
                "Jour 1: heures 14-23 (10 ticks). Jours 2-3: 24h chacun (48). Total=58. "
                "Formule: (24-start_hour) + 24*(num_days-1). Code: services/calendar_tn.scenario_timestamps.",
            ),
            (
                "Pourquoi bootstrap_simulation met sim_tick a 1 et non 0 apres la 1ere heure ?",
                "sim_tick compte les heures deja materialisees dans sim_data. Apres bootstrap "
                "n=1 heure generee, tick=1. Le prochain advance part de idx=tick.",
            ),
            (
                "Comment fonctionne maybe_autorefresh sans bloquer l'UI ?",
                "streamlit-autorefresh declenche un rerun toutes les N secondes si sim_running "
                "et non pause. Compteur _sim_ar_count detecte le changement et pose sim_advance=True. "
                "process_tick() consomme ce flag et avance d'une heure.",
            ),
            (
                "Que fait purge_stale_sim_session et pourquoi c'est critique ?",
                "Si schema version change, pipeline legacy (profil_historique, scenario_rules) "
                "ou conso_optimisee absente: reset pour eviter KPI incoherents apres deploy. "
                "Ne purge pas si sim_running (simulation en cours).",
            ),
            (
                "Comment Simuler la journee complete evite-t-il le crash Streamlit Cloud ?",
                "generate_period() concatene toutes les lignes brutes puis un seul (ou few) "
                "appels enrich_with_pipeline par chunks de 360 lignes, au lieu de 24 appels "
                "pipeline separes qui timeout.",
            ),
            (
                "Pourquoi sim_data est tronque avec .tail(max_rows) ?",
                "max_rows = max(72, 24*jours) * nb_stations. Limite memoire session Streamlit "
                "Cloud et garde fenetre recente pour graphiques/journal.",
            ),
            (
                "Le jitter est-il aleatoire a chaque rerun ?",
                "Non. seed = hash(station_id, date ISO, heure) % 2**31 dans _jitter. "
                "Meme scenario = memes valeurs conso/pred pour une station/heure donnee.",
            ),
            (
                "D'ou viennent les profils horaires par station ?",
                "sim_engine() charge referentiel via _load_sim_reference() (dataset enrichi). "
                "_profile_lookup groupe par station, heure, mois, week-end, Ramadan, ferie. "
                "_pick_profile cascade vers profil heure seule puis _fallback_profile.",
            ),
            (
                "Que se passe-t-il si Hub HuggingFace est down pendant une simulation ?",
                "enrich_with_pipeline catch Exception -> apply_offline_nb23(). La simulation "
                "continue avec regles heuristiques; inference_pipeline marque offline. "
                "Message possible sur courbe si ecart faible.",
            ),
        ],
    ),
    (
        "NB1 - Prediction et ecarts",
        [
            (
                "Quel modele predit conso_predite en Simulation ?",
                "LightGBM charge via pipeline_inference.joblib si disponible (run_nb_pipeline). "
                "Sinon conso_predite vient du profil synthetique jittere (~9% autour du profil).",
            ),
            (
                "Comment est calcule ecart_pct affiche dans le tableau ?",
                "services/nb_metrics.compute_ecart_pct: (conso_reelle - conso_predite) / conso_predite * 100. "
                "Agregation reseau KPI: somme conso vs somme pred (pas moyenne des ecarts).",
            ),
            (
                "Pourquoi un ecart negatif de -6% n'est pas forcement une alerte ?",
                "Alerte ecart_conso declenche si |ecart| >= 30% ET QoS >= seuil (0.6). "
                "-6% sous prediction = bon comportement, pas incident.",
            ),
            (
                "Les bandes Q10/Q90 sont-elles utilisees en Simulation ?",
                "Generees (pred*0.9/1.1 en synthetique, ou NB1 pipeline). Pas de declenchement "
                "alerte direct sur Q10/Q90 dans simulation_events; seuil fixe 30%/50%.",
            ),
            (
                "La prediction est-elle recalculee a chaque heure simulee ?",
                "Oui si pipeline actif: run_nb_pipeline recalcule conso_predite, scores NB2, "
                "actions NB3 pour le batch horaire soumis.",
            ),
            (
                "Peut-on simuler une date future ?",
                "Oui techniquement (date_input libre). Contexte calendaire (Ramadan, ferie) "
                "s'applique via calendar_context. Pas de donnees meteo reelles futures.",
            ),
        ],
    ),
    (
        "NB2 - Anomalies et seuils",
        [
            (
                "Comment le seuil d'anomalie est-il resolu en Simulation ?",
                "resolve_nb2_seuil_ensemble() depuis stats reseau exportees JSON. "
                "_anomaly_seuil(scale) = seuil / scale. Si absent, certaines alertes "
                "anomalie_sans_action ne se declenchent pas (seuil None).",
            ),
            (
                "Que signifie nb_votes_anomalie dans le moteur de mode ?",
                "Nombre de detecteurs NB2 ayant vote anomalie. >=5 votes -> mode CRITIQUE "
                "meme si score modere (decision_service.decider_mode).",
            ),
            (
                "Pourquoi une anomalie peut exister sans action automatique ?",
                "Alerte type anomalie_sans_action: score >= seuil, QoS OK, mais aucune "
                "action_proposee/action_rl nommee. Design: alerter NOC pour arbitrage humain.",
            ),
            (
                "Difference entre alerte qos_risque et mode CRITIQUE ?",
                "qos_risque: score anomalie eleve + QoS < seuil (optimisation interdite). "
                "mode CRITIQUE: logique NB3 globale (score>0.6 ou votes>=5). Les deux peuvent "
                "coexister; journal et badge UI peuvent differer.",
            ),
            (
                "Les alertes sont-elles dedupliquees ?",
                "merge_event_log concatene et garde max 300 entrees. alert_ref = station|timestamp|type. "
                "Acquittement via sim_ack_refs + persist_alert_ack SQLite.",
            ),
            (
                "Peut-on baisser la sensibilite aux fausses alertes en demo ?",
                "classify_tick_rows accepte anomaly_sensitivity (defaut 1.0). UI actuelle "
                "ne expose pas le slider; seuil effectif = seuil_reseau / sensitivity.",
            ),
        ],
    ),
    (
        "NB3 - Modes, actions, economies, RL",
        [
            (
                "Pourquoi mode NORMAL avec action Free cooling et gain > 0 ?",
                "mode_operation (MoteurDecisionEnergie) mesure urgence reseau. action_proposee "
                "(StrategieOptimisation) mesure opportunite energetique (meteo). Free cooling "
                "ne requiert pas creneau ECO 0h-6h. Ce n'est pas contradictoire metier.",
            ),
            (
                "Quelles conditions exactes declenchent mode ECO ?",
                "score < 0.25, CPU < 50%, heure entre 0 et 6, optimisation_qos_autorisee=1. "
                "Toutes simultanement (decision_service seuils eco_*).",
            ),
            (
                "Comment economie_estimee_kwh est calculee pour free cooling ?",
                "optimization_service: conso * 0.15 si T<22C, vent>3 m/s, HR<75%, pas d'action "
                "prioritaire sleep/reduction. Plafonnee a 42% conso (MAX_ECO_FRAC_DEFAULT).",
            ),
            (
                "Formule finale economie_kwh retenue ?",
                "harmonize_nb3_economies: max(economie_estimee_kwh, economie_rl_kwh) puis "
                "min(..., NB3_MAX_ECO_FRAC * conso) avec NB3_MAX_ECO_FRAC=0.48.",
            ),
            (
                "Pourquoi prefer_rl=True dans le tableau mais False dans la carte detail ?",
                "Tableau ops: action affichee = action_rl (decision automatisee). Carte detail: "
                "action_proposee expert d'abord (demo strategie regles metier au jury).",
            ),
            (
                "Comment RL est-il simule sans reentrainer en live ?",
                "Artefacts RL dans pipeline; _fill_rl_economie_from_actions mappe fractions "
                "par action (ex: free_cooling 12%, sleep 40%). Pas d'apprentissage online.",
            ),
            (
                "Pourquoi plafond 48% de la consommation ?",
                "Garde-fou realisme reseau: impossible d'eteindre plus de la moitie de la charge "
                "BTS sans violer contraintes QoS/alimentation. Configurable NB3_MAX_ECO_FRAC.",
            ),
            (
                "Que signifie conso_optimisee_kwh sur la courbe ?",
                "max(consommation_kwh - economie_kwh, 0). Courbe verte = conso apres action "
                "optimisation retenue (expert ou RL).",
            ),
            (
                "Sleep mode: economie depend-elle de la technologie ?",
                "Oui. ECO_SLEEP_PAR_TECHNO: 2G=0.062, 3G=1.608, 4G=1.845, 4G+=2.04 kWh/ref, "
                "cap a 48% conso (settings.NB3_MAX_ECO_FRAC pour sleep).",
            ),
            (
                "Une action critique ecrase-t-elle free cooling ?",
                "Oui. optimization_service ligne critique: action alerte_noc_prioritaire "
                "et economie_estimee_kwh=0 si mode CRITIQUE ou score>0.6.",
            ),
        ],
    ),
    (
        "UI, UX et pieges jury",
        [
            (
                "Pourquoi le texte disait 'aucune action requise' avec un gain affiche ?",
                "Bug UX corrige: mode_explanation() renvoyait message generique pour NORMAL "
                "sans lire action_proposee. Desormais: 'optimisation possible : {action}'.",
            ),
            (
                "Gain heure vs Gain cumule: difference ?",
                "Gain heure = somme economie_kwh derniere timestamp * 0.40 DT. Gain cumule = "
                "somme sur tout sim_data (historique simulation).",
            ),
            (
                "Pourquoi la courbe optimisee peut etre a 0 ?",
                "Session legacy ou pipeline sans NB3. purge_stale_sim_session + Stop/Demarrer "
                "force recalcul. Warning affiche si conso>0.05 et conso_opt<=0.01.",
            ),
            (
                "Que signifie progression 16/16 en pause ?",
                "sim_running=False ou sim_paused=True: autorefresh inactif. 16/16 = scenario "
                "termine (ou journee complete) sans erreur.",
            ),
            (
                "Pourquoi certaines stations manquent sur la carte ?",
                "render_mini_map exige latitude/longitude dans latest_all. Stations sans GPS "
                "dans referentiel sont exclues silencieusement du scatter.",
            ),
            (
                "Traite vs Ignorer une alerte: impact metier ?",
                "persist_alert_ack en SQLite (acquitte / faux_positif). Compteur Alertes ouvertes "
                "decremente. Pas de re-simulation automatique.",
            ),
            (
                "Export PDF sommaire vs CSV: contenu ?",
                "CSV = sim_data brut ligne a ligne. PDF = build_simulation_report agrege "
                "(total reseau, par station, alertes) via generate_simulation_sommaire_pdf.",
            ),
        ],
    ),
    (
        "Securite, roles, deploiement",
        [
            (
                "Un ingenieur peut-il simuler une station d'un autre gouvernorat ?",
                "Non si non assignee. station_options() filtre engineer_assigned_stations() "
                "pour role != admin.",
            ),
            (
                "Les donnees simulees sont-elles persistees cote serveur ?",
                "sim_data reste en session_state Streamlit (volatile). Seuls acquittements "
                "alertes vont en SQLite. Pas d'historique simulation multi-session.",
            ),
            (
                "Que contient SECRET_KEY et pourquoi c'est important ?",
                "HMAC sessions auth (security_middleware). En prod: variable env, pas default dev. "
                "Streamlit Cloud: secrets.toml.",
            ),
            (
                "Rate limiting sur la Simulation ?",
                "Middleware global _GLOBAL_RATE_LIMITS sur auth/actions sensibles. Simulation "
                "lourde limitee surtout par timeout Streamlit Cloud (~plusieurs minutes max).",
            ),
            (
                "Comment proteger HF_TOKEN en demo ?",
                "settings.HF_TOKEN via .env/secrets, jamais commit. Lecture read-only Hub public "
                "si repo public sans token.",
            ),
        ],
    ),
    (
        "Mathematiques, formules, agregations",
        [
            (
                "Conversion kWh -> DT: ou est le tarif ?",
                "settings.PRIX_KWH_TN = 0.40 DT/kWh (configurable .env). kwh_to_dt() dans "
                "simulation_common multiplie par ce facteur.",
            ),
            (
                "CO2 evite est-il calcule en Simulation ?",
                "Pas en KPI direct page Simulation. FACTEUR_CO2_TN=0.53 existe settings pour "
                "autres pages. Extension possible: gain_kwh * facteur.",
            ),
            (
                "Agregation multi-stations sur courbe sans focus ?",
                "build_chart somme conso/pred/conso_opt par timestamp sur parc selectionne. "
                "Caption: 'somme horaire sur le parc selectionne'.",
            ),
            (
                "Moyenne ecart % dans rapport PDF par station ?",
                "ecart_pct_series(sub).mean() par station dans build_simulation_report, "
                "pas ecart des sommes.",
            ),
            (
                "Calendar scale nuit vs midi ?",
                "_calendar_scale: x0.85 si h<=5 ou h>=23, x1.05 si 12-14h, modulateurs "
                "Ramadan/ferie/week-end. Applique avant jitter sur conso.",
            ),
        ],
    ),
    (
        "Limites, critiques attendues, reponses",
        [
            (
                "Votre simulation n'est pas du vrai reseau. Comment repondre ?",
                "Exact. C'est un demonstrateur pedagogique what-if calibré sur profils TT reels. "
                "Production = connecteurs OSS/BSS + SCADA + validation terrain. PFE prouve "
                "l'enchainement algorithmique NB1-3 et l'UX NOC.",
            ),
            (
                "LightGBM sur donnees synthetiques: fuite de labels ?",
                "En sim, conso_predite peut etre recalculee par NB1 sur features synthetiques "
                "coherentes. Pas de fuite train/test car pas reentrainement live. Ecarts "
                "jitter injectent realisme.",
            ),
            (
                "RL en production sur le reseau radio ?",
                "Non deploye. RL offline entraine en NB3, inference seulement. Garde-fous QoS "
                "et plafond 48%. TT exigerait shadow mode + rollback + homologation radio.",
            ),
            (
                "Scalabilite 10 000 stations ?",
                "Limite actuelle: session Streamlit, pipeline batch, UI dataframe. Architecture "
                "cible: Spark/Flink batch horaire + cache Redis + API read-only.",
            ),
            (
                "Pourquoi SQLite et pas PostgreSQL ?",
                "PFE/deploiement Streamlit Cloud simple (comptes, ack alertes). PostgreSQL "
                "recommande multi-utilisateurs production.",
            ),
            (
                "Comment valider que la demo n'est pas 'fabriquee' ?",
                "Montrer inference_pipeline dans sim_data, comparer une station avec page "
                "Prediction historique, exporter CSV, expliquer seed jitter reproductible, "
                "desactiver Hub pour montrer fallback offline.",
            ),
        ],
    ),
    (
        "Questions ultra-hard (pieges)",
        [
            (
                "Si je change sim_num_days pendant sim_running, que se passe-t-il ?",
                "sim_total_ticks recalcule seulement au Demarrer. Changer slider en cours "
                "modifie param future advance mais pas total deja fixe -> possible desync "
                "progression. Bonne pratique: Stop puis reconfigurer.",
            ),
            (
                "Ordre de priorite des regles action_proposee ?",
                "sleep > reduction_puissance > free_cooling > eco_calendaire > alerte_2g > "
                "critique NOC. Chaque regle ne s'applique que si action encore monitoring_standard "
                "(sauf critique qui ecrase tout).",
            ),
            (
                "Pourquoi classify_tick_rows utilise prefer_rl=True pour message alerte ?",
                "Messages alerte orientes action automatisee deployable (RL/pipeline). Journal "
                "decisions privilegie action_expert si action_proposee nommee.",
            ),
            (
                "Difference inference_pipeline nb1_nb2_nb3 vs nb23_offline ?",
                "nb1_nb2_nb3 = pipeline Hub complet LightGBM+detecteurs+NB3. offline = "
                "apply_offline_nb23 regles simplifiees. purge_stale reset si legacy detecte.",
            ),
            (
                "Peut-on avoir sim_tick > sim_total_ticks ?",
                "Non normalement. advance_simulation stoppe si tick >= len(stamps). "
                "Journee complete set sim_tick=total explicitement.",
            ),
            (
                "Comment reproductibilite demo jury a l'identique ?",
                "Meme date, heure debut, stations triees, meme version artefacts Hub, "
                "meme SIM_SCHEMA_VERSION. Eviter changer intervalle autorefresh (n'affecte pas "
                "donnees, seulement rythme).",
            ),
            (
                "Que repondre si jury demande latence inference par heure ?",
                "Mesurer localement: hourly_snapshot ~X ms sans Hub, generate_period batch "
                "Y secondes pour N stations * 24h. Optimisation batch chunks 360 lignes "
                "pour respecter timeout Streamlit ~60-180s.",
            ),
            (
                "Le mode ECO nuit-only est-il realiste pour TT ?",
                "Heuristique PFE alignee cahier des charges demo (creneau faible trafic). "
                "TT peut elargir via decision_service.seuils eco_heure_debut/fin configurables.",
            ),
            (
                "Justification economique 0.40 DT/kWh ?",
                "Tarif moyen industriel Tunisie utilise pour KPI financiers homogenes. "
                "Configurable PRIX_KWH_TN; sensibilite dans rapport excel possible.",
            ),
            (
                "Si deux onglets Streamlit ouverts, sessions independantes ?",
                "Oui. session_state isole par session navigateur. Pas de collision sim_data "
                "entre jurys differents sur Cloud (instances separees par user session).",
            ),
            (
                "Comment prouver que le gain 0.80 DT n'est pas invente ?",
                "Tracabilite: economie_kwh = min(max(expert,RL), 0.48*conso). free_cooling "
                "expert = 15% conso. 2.01 kWh * 0.40 = 0.804 DT. Verifiable dans CSV export.",
            ),
            (
                "Quelle est la difference entre alerte et decision journal ?",
                "Alerte = evenement NOC a traiter (seuils depasses, modes critiques). "
                "Decision = action optimisation journalisee avec economie estimee. "
                "Une heure peut generer les deux, l'une ou aucune.",
            ),
            (
                "Le jury dit: 'NORMAL veut dire rien a faire'. Reponse ?",
                "NORMAL = pas d'urgence NOC (pas CRITIQUE/ATTENTION). Cela n'interdit pas "
                "une optimisation opportuniste (free cooling) si meteo favorable. Distinction "
                "urgence vs opportunite energetique.",
            ),
            (
                "Comment demontrer le pipeline sans code source ouvert ?",
                "Export CSV: colonnes inference_pipeline, anomalie_score_ensemble, action_rl, "
                "economie_kwh. Comparer 2 heures consecutives: scores changent, preuve inference.",
            ),
        ],
    ),
    (
        "Comparaison avec les autres pages dashboard",
        [
            (
                "Page Prediction vs Simulation: meme LightGBM ?",
                "Meme artefact NB1 si Hub charge. Prediction lit historique exporte; Simulation "
                "re-genere features synthetiques horaires puis inferre.",
            ),
            (
                "Page Anomalies vs alertes Simulation ?",
                "Anomalies = vue statique dataset complet avec filtres admin. Simulation = "
                "alertes dynamiques classify_tick_rows() sur flux horaire simule + acquittement.",
            ),
            (
                "Page Optimisation vs gain cumule Simulation ?",
                "Optimisation = KPI reseau pre-calcules exports NB3. Simulation recalcule "
                "gain cumule live sur sim_data session avec memes formules harmonize_nb3_economies.",
            ),
            (
                "Vue reseau (P1) filtre-t-il les memes stations que Simulation ?",
                "Filtres globaux sidebar influencent default_sim_date via merged_active_filters. "
                "Liste stations sim = station_options(role) independante des filtres gouvernorat.",
            ),
            (
                "Carte Folium page reseau vs mini-map Simulation ?",
                "Reseau: toutes stations filtrees admin. Sim: latest_all uniquement, modes "
                "simules, action_a_faire format_action_label.",
            ),
        ],
    ),
    (
        "Tests, qualite et maintenance",
        [
            (
                "Existence de tests automatises sur Simulation ?",
                "tests/test_formatting.py (resolve_row_action), tests/test_nb_metrics.py "
                "(economie). Pas de test E2E Streamlit simulation; validation manuelle demo.",
            ),
            (
                "Comment detecter regression apres changement NB3 ?",
                "Incrementer SIM_SCHEMA_VERSION -> purge auto sessions. Verifier colonnes "
                "inference_pipeline, conso_optimisee_kwh non nulles apres bootstrap.",
            ),
            (
                "Que faire si sim_bootstrap_error persiste ?",
                "Stop, verifier stations selectionnees, connexion Hub, logs Streamlit. "
                "Message typique: impossible generer premiere heure -> ref vide ou engine fail.",
            ),
            (
                "Pourquoi streamlit-autorefresh est optional import ?",
                "Compatibilite environnements sans dep. Si absent, maybe_autorefresh noop: "
                "simulation manuelle tick-by-tick via reruns seulement apres Demarrer.",
            ),
            (
                "Impact d'un deploy mid-simulation pour un utilisateur ?",
                "Session Streamlit perdue (cold start). sim_data efface. Utilisateur doit "
                "relancer scenario. Acquittements SQLite persistent.",
            ),
        ],
    ),
    (
        "Questions finales piege (niveau expert)",
        [
            (
                "Pourquoi hash() pour seed jitter et pas random() ?",
                "Reproductibilite demo et tests: meme entrees -> memes consos. hash() Python "
                "salted par version interpreter; acceptable PFE, production utiliserait seed fixe explicite.",
            ),
            (
                "Le modele voit-il la station_id en inference ?",
                "Features NB1 incluent contexte station/zone via encodage pipeline joblib. "
                "Station_id seule insuffisante; profil agrege apporte techno, zone, historique.",
            ),
            (
                "Peut-on simuler sans aucune station assignee en admin ?",
                "Admin voit toutes stations dataset. Si dataset vide -> warning aucune station. "
                "Ingenieur sans assignation -> liste vide -> page bloquee.",
            ),
            (
                "Difference entre sim_paused et sim_running=False ?",
                "Pause: running True, autorefresh ignore, donnees conservees. running False: "
                "fin scenario ou stop; autorefresh desactive, tick fige.",
            ),
            (
                "Le PDF sommaire simulation inclut-il les decisions journal ?",
                "generate_simulation_sommaire_pdf inclut alertes et rapport build_simulation_report. "
                "Decisions detaillees plutot dans CSV sim_data + onglet Journal UI.",
            ),
            (
                "Comment repondre: 'Pourquoi pas Grafana/Kibana ?' ?",
                "PFE oriente metier radio TT avec actions NB3 integrees, pas seulement viz. "
                "Streamlit = prototype UX NOC. Grafana possible en couche metrics parallele.",
            ),
            (
                "Validation statistique des 48% plafond ?",
                "Heuristique ingenieurie basee contraintes QoS/alimentation BTS, pas optimisation "
                "mathematique globale. Parametre configurable pour etude sensibilite.",
            ),
            (
                "Que se passe-t-il si conso_predite = 0 ?",
                "ecart_pct evite division par zero (retour 0 ou NaN gere). Alertes ecart "
                "conditionnees sur abs(ecart)>=30 avec QoS OK.",
            ),
            (
                "Multi-utilisateur Streamlit Cloud: fuite de donnees sim ?",
                "Non entre sessions: session_state isole par cookie session. Donnees sim "
                "non ecrites en base partagee sauf ack alertes liees au username.",
            ),
            (
                "Derniere phrase si jury bloque sur 'c'est fake' ?",
                "Proposer export CSV de la session, ouvrir le fichier source synthetic_bts.py "
                "ligne _jitter, recalculer a la main 15% free cooling sur conso affichee.",
            ),
        ],
    ),
]
