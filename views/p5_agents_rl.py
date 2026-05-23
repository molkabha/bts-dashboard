"""Page 5 - Agents RL — vue operationnelle."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config.theme import PLOTLY_DARK, PLOTLY_LIGHT
from security.middleware import security_middleware
from ui.components import header, render_artifact_gallery, section
from ui.utils import session_outputs


AGENT_LABELS = {
    "q_learning": "Q-Learning",
    "sarsa": "SARSA",
    "double_q_learning": "Double Q-Learning",
    "expected_sarsa": "Expected SARSA",
    "q_learning_adaptatif": "Q-Learning Adaptatif",
    "sarsa_lambda": "SARSA Lambda",
    "dyna_q": "Dyna-Q",
}


def page_agents_rl():
    security_middleware.enforce()
    header("Agents RL", "Optimisation par apprentissage — vue operationnelle")

    outputs = session_outputs()
    nb3 = outputs.get("nb3", {})
    rl_data = nb3.get("rl_resultats_tous_agents", {})

    if not rl_data:
        st.info("Donnees agents RL non disponibles dans les artefacts NB3.")
        return

    df_rl = pd.DataFrame.from_dict(rl_data, orient="index").reset_index(names="Agent")
    if "economie_pct" in df_rl.columns:
        df_rl = df_rl.sort_values("economie_pct", ascending=False).reset_index(drop=True)

    best = df_rl.iloc[0]
    agent_name = str(best.get("Agent", "Q-Learning"))
    eco_pct = float(best.get("economie_pct", 0) or 0)
    confiance = min(99, max(50, 100 - float(best.get("pct_violations", 10) or 10) * 2))

    st.markdown(f"""
<div class="info-box" style="margin-bottom:16px;">
  <div class="ib-title">Agent actif</div>
  <div class="ib-body" style="font-size:15px;font-weight:800;">
    {agent_name} | Decision : Mode ECO | Economie : {eco_pct:.0f}% | Confiance : {confiance:.0f}%
  </div>
</div>
""", unsafe_allow_html=True)

    template = PLOTLY_DARK if st.session_state.get("ui_dark_mode") else PLOTLY_LIGHT

    with section("Economie moyenne par agent"):
        if "economie_pct" in df_rl.columns:
            fig = px.bar(df_rl, x="Agent", y="economie_pct", title="Economie moyenne (%)",
                         color="economie_pct", color_continuous_scale="Greens")
            fig.update_layout(template=template, margin=dict(l=0, r=0, t=30, b=0), height=300, showlegend=False)
            st.plotly_chart(fig, width="stretch")

    with section("Recapitulatif agents"):
        cols_show = ["Agent", "economie_pct", "pct_violations"]
        cols_show = [c for c in cols_show if c in df_rl.columns]
        summary = df_rl[cols_show].head(7).copy()
        summary.columns = ["Agent", "Economie %", "Violations QoS %"][:len(cols_show)]
        st.dataframe(summary, width="stretch", hide_index=True)

    if st.button("Simuler 24h avec cet agent", type="primary", width="stretch"):
        st.session_state["nav_page_ingenieur"] = "Simulation"
        st.session_state["nav_page_admin"] = st.session_state.get("nav_page_admin", "Vue executive")
        st.session_state["_nav_override"] = 6
        st.rerun()

    with st.expander("Detail technique — courbes de convergence"):
        render_artifact_gallery(
            [("rl_7agents_apprentissage.png", "Convergence des 7 agents RL")],
            title="Apprentissage RL",
            columns=1,
        )
