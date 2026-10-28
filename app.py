"""LaunchLoop: a local, simulated workshop growth dashboard."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import campaign_generator
import database
import growth_metrics as metrics
import referral_manager

st.set_page_config(page_title="LaunchLoop | Growth Engine", page_icon="↗", layout="wide")
database.initialize_database()

INK = "#172523"
MINT = "#126B59"
CORAL = "#D66A4A"
GOLD = "#E6B75A"
CHANNELS = [
    "College clubs and student ambassadors",
    "WhatsApp and student communities",
    "Peer referrals",
    "Paid promotional experiment",
]

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root { --ink:#172523; --muted:#62716d; --paper:#f5f7f3; --line:#dce4df; --mint:#126b59; --coral:#d66a4a; }
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif; color:var(--ink); }
    .stApp { background: radial-gradient(ellipse at 92% 2%, rgba(230,183,90,.16), transparent 28%), var(--paper); }
    h1, h2, h3 { font-family:'Manrope',sans-serif !important; color:var(--ink); letter-spacing:0 !important; }
    h1 { font-weight:800 !important; }
    [data-testid="stSidebar"] { background:#e9efea; border-right:1px solid var(--line); }
    [data-testid="stMetric"] { background:rgba(255,255,255,.82); border:1px solid var(--line); padding:16px 18px; border-radius:8px; min-height:114px; }
    [data-testid="stMetricLabel"] { color:var(--muted); font-weight:600; }
    [data-testid="stMetricValue"] { color:var(--ink); font-family:'Manrope',sans-serif; }
    .brand-mark { font:800 24px Manrope,sans-serif; color:var(--mint); margin:4px 0 0; }
    .brand-tag { color:var(--muted); font-size:12px; margin:0 0 22px; }
    .eyebrow { color:var(--mint); font-weight:700; font-size:12px; text-transform:uppercase; letter-spacing:1px; }
    .notice { padding:13px 16px; border:1px solid #d5b067; border-left:4px solid #c78d28; background:#fff8e9; border-radius:6px; color:#59451e; font-weight:700; }
    .subtle { color:var(--muted); font-size:14px; }
    .section-rule { border-top:1px solid var(--line); margin:24px 0; }
    div[data-testid="stForm"] { border:1px solid var(--line); border-radius:8px; background:rgba(255,255,255,.65); }
    .stButton > button, .stDownloadButton > button { border-radius:6px; font-weight:700; }
    </style>
    """,
    unsafe_allow_html=True,
)


def money(amount: float) -> str:
    return f"₹{amount:,.0f}"


def heading(title: str, subtitle: str) -> None:
    st.title(title)
    st.markdown(f'<p class="subtle">{subtitle}</p>', unsafe_allow_html=True)


def get_filtered_registrations() -> pd.DataFrame:
    data = database.get_registrations()
    if data.empty:
        return data
    data["registered_at"] = pd.to_datetime(data["registered_at"], errors="coerce", utc=True)
    return data


def overview_page() -> None:
    heading("Growth overview", "A decision dashboard for the seven-day workshop registration sprint.")
    st.markdown(
        '<div class="notice">DEMO MODE — All sample registrations and campaign results are simulated. No real campaign has been executed.</div>',
        unsafe_allow_html=True,
    )
    rows = get_filtered_registrations()
    plans = database.get_campaign_plans()
    codes = database.get_referral_codes()
    all_time_total = metrics.registration_total(rows)
    if rows.empty:
        min_day = max_day = date.today()
    else:
        registration_days = rows["registered_at"].dt.date.dropna()
        min_day = registration_days.min() if not registration_days.empty else date.today()
        max_day = registration_days.max() if not registration_days.empty else date.today()
    default_start = max(min_day, max_day - timedelta(days=6))
    date_range = st.date_input("Chart date range", value=(default_start, max_day), min_value=min_day, max_value=max_day)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_day, end_day = date_range
    else:
        start_day = end_day = date_range
    channel_names = sorted(rows["channel"].dropna().unique().tolist()) if not rows.empty else []
    chosen_channel = st.selectbox("Channel filter for daily and referral views", ["All channels", *channel_names])

    total = all_time_total
    target = 500
    remaining = metrics.remaining_registrations(total, target)
    achieved = metrics.percentage_of_target(total, target)
    budget = float(plans["planned_budget"].sum()) if not plans.empty else 0.0
    spend = database.get_simulated_spend()
    cost = metrics.cost_per_registration(spend, total)
    active_channels = int(rows["channel"].nunique()) if not rows.empty else 0
    metric_columns = st.columns(4)
    metric_columns[0].metric("Total registrations", f"{total:,}")
    metric_columns[1].metric("Target registrations", f"{target:,}")
    metric_columns[2].metric("Remaining", f"{remaining:,}")
    metric_columns[3].metric("Target achieved", f"{achieved:.1f}%")
    metric_columns = st.columns(4)
    metric_columns[0].metric("Budget allocated", money(budget), help="Hypothetical planned budget, not money spent.")
    metric_columns[1].metric("Simulated spend", money(spend), help="A manually entered demo value; no real spend occurs.")
    metric_columns[2].metric("Cost per registration", money(cost) if cost is not None else "—")
    metric_columns[3].metric("Active channels", f"{active_channels}")
    st.caption("Budget allocated is a planning hypothesis. Simulated spend is stored separately and does not represent a real transaction.")

    dates = rows.copy()
    if not dates.empty:
        dates = dates[dates["registered_at"].dt.date.between(start_day, end_day)]
    channel_rollup = metrics.registrations_by_channel(dates)
    chart_rows = dates if chosen_channel == "All channels" else dates[dates["channel"] == chosen_channel]
    daily = metrics.registrations_by_day(chart_rows, start_day, end_day)
    if daily.empty:
        calendar = pd.DataFrame({"day": pd.date_range(start_day, end_day, freq="D").date, "registrations": 0})
    else:
        calendar = pd.DataFrame({"day": pd.date_range(start_day, end_day, freq="D").date}).merge(daily, on="day", how="left").fillna({"registrations": 0})
        calendar["registrations"] = calendar["registrations"].astype(int)
    referral_rows = metrics.referral_contribution(chart_rows, codes)
    left, right = st.columns(2)
    with left:
        st.subheader("Registrations by channel")
        if channel_rollup.empty:
            st.info("No registrations in this date range yet. Load synthetic demo rows from Registration tracker to explore the chart.")
        else:
            fig = px.bar(channel_rollup, x="channel", y="registrations", color="channel", color_discrete_sequence=[MINT, CORAL, GOLD, "#497b94"])
            fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title="Registrations", margin=dict(t=10, b=10), height=320)
            st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Daily registrations")
        fig = px.line(calendar, x="day", y="registrations", markers=True, color_discrete_sequence=[CORAL])
        fig.update_layout(xaxis_title=None, yaxis_title="Registrations", margin=dict(t=10, b=10), height=320)
        st.plotly_chart(fig, use_container_width=True)
    left, right = st.columns(2)
    with left:
        st.subheader("Referral code performance")
        if referral_rows.empty:
            st.info("Referral codes will appear here after initialization.")
        else:
            fig = px.bar(referral_rows, x="code", y="registrations", hover_data=["ambassador_label", "contribution_pct"], color_discrete_sequence=[MINT])
            fig.update_layout(xaxis_title="Referral code", yaxis_title="Attributed registrations", margin=dict(t=10, b=10), height=300)
            st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Progress to 500")
        fig = go.Figure(go.Bar(x=[min(total, target), max(target - total, 0)], y=["Registrations"], orientation="h", marker_color=[MINT, "#dce4df"], text=[min(total, target), max(target - total, 0)], textposition="inside"))
        fig.update_layout(showlegend=False, xaxis=dict(range=[0, target], title="Registrations"), yaxis=dict(showticklabels=False), margin=dict(t=20, b=20), height=180)
        st.plotly_chart(fig, use_container_width=True)


def registration_tracker_page() -> None:
    heading("Registration tracker", "Manage simulated registrations and inspect the source of every row.")
    st.info("Use demo identifiers and reserved `.invalid` email addresses only. All entries here are simulation data.")
    with st.form("registration_form", clear_on_submit=True):
        st.subheader("Add a simulated registration")
        a, b = st.columns(2)
        name = a.text_input("Student name or demo identifier", placeholder="Demo Student 021")
        email = b.text_input("Email", placeholder="demo+021@example.invalid")
        college = a.text_input("College", placeholder="Demo Engineering College")
        channel = b.selectbox("Acquisition channel", CHANNELS)
        codes = database.get_referral_codes()["code"].tolist()
        referral = st.selectbox("Referral code (optional)", ["None", *codes])
        variant = st.selectbox("Campaign variant (optional)", ["None", "A", "B"])
        submitted = st.form_submit_button("Add simulated registration", type="primary")
        if submitted:
            if not name.strip() or not college.strip():
                st.error("Enter a demo identifier and college label.")
            elif not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()):
                st.error("Enter a valid email address. For demo rows, use an address such as demo+021@example.invalid.")
            else:
                try:
                    database.add_registration(name, email, college, channel, None if referral == "None" else referral,
                                              None if variant == "None" else variant, source="manual")
                    st.success("Simulated registration added.")
                except (database.DuplicateRegistrationError, database.InvalidReferralCodeError, ValueError) as exc:
                    st.error(str(exc))
                except sqlite3.Error:
                    st.error("The local database could not save this registration. Try again.")
    st.markdown('<div class="section-rule"></div>', unsafe_allow_html=True)
    left, right = st.columns([1, 1])
    with left:
        if st.button("Load synthetic sample data", help="Adds only sample_data CSV rows; repeated loads do not duplicate them."):
            try:
                count = database.load_sample_registrations()
                st.success(f"Loaded {count} new synthetic rows. Existing sample emails were skipped.")
            except (OSError, sqlite3.Error, KeyError) as exc:
                st.error(f"Sample data could not be loaded: {exc}")
    with right:
        confirmed = st.checkbox("Confirm removal of synthetic sample rows")
        if st.button("Reset sample data", disabled=not confirmed):
            try:
                removed = database.reset_sample_registrations()
                st.success(f"Removed {removed} synthetic sample rows. Manual simulations were kept.")
            except sqlite3.Error:
                st.error("Sample rows could not be removed from the local database.")

    rows = database.get_registrations()
    if rows.empty:
        st.markdown("### No registrations yet\nLoad the synthetic sample set or add a clearly labeled simulation above.")
        return
    filter_cols = st.columns(2)
    channels = ["All", *sorted(rows["channel"].dropna().unique().tolist())]
    selected_channel = filter_cols[0].selectbox("Filter channel", channels)
    referrals = ["All", "No referral", *sorted(rows["referral_code"].dropna().unique().tolist())]
    selected_referral = filter_cols[1].selectbox("Filter referral code", referrals)
    query = st.text_input("Search records", placeholder="Search demo identifier, email, college, or code")
    visible = rows.copy()
    if selected_channel != "All":
        visible = visible[visible["channel"] == selected_channel]
    if selected_referral == "No referral":
        visible = visible[visible["referral_code"].isna() | (visible["referral_code"] == "")]
    elif selected_referral != "All":
        visible = visible[visible["referral_code"] == selected_referral]
    if query.strip():
        visible = visible[visible.astype(str).apply(lambda col: col.str.contains(query.strip(), case=False, na=False)).any(axis=1)]
    display = visible.copy()
    display["source"] = display["source"].map({"sample": "Synthetic sample", "manual": "Manual simulation"}).fillna("Simulation")
    st.caption(f"Showing {len(display):,} of {len(rows):,} simulation records")
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.download_button("Export filtered records as CSV", display.to_csv(index=False).encode("utf-8"), "launchloop_registrations.csv", "text/csv")


def referral_tracker_page() -> None:
    heading("Referral tracker", "Attribute a registration to the code recorded at sign-up. No payments or rewards are involved.")
    st.caption("Attribution uses the referral code recorded during registration. Email uniqueness prevents counting the same person twice in this simulation.")
    codes = database.get_referral_codes()
    rows = database.get_registrations()
    leaderboard = metrics.referral_contribution(rows, codes)
    if leaderboard.empty:
        st.info("No referral codes are available yet.")
    else:
        st.dataframe(leaderboard.rename(columns={"code": "Referral code", "ambassador_label": "Ambassador", "registrations": "Attributed registrations", "contribution_pct": "Share of registrations (%)"}), use_container_width=True, hide_index=True)
        chart = px.bar(leaderboard.sort_values("registrations"), x="registrations", y="code", orientation="h", color_discrete_sequence=[MINT], hover_data=["ambassador_label", "contribution_pct"])
        chart.update_layout(xaxis_title="Attributed registrations", yaxis_title=None, margin=dict(t=10, b=10), height=340)
        st.plotly_chart(chart, use_container_width=True)
    left, right = st.columns(2)
    with left:
        with st.form("create_referral_code", clear_on_submit=True):
            st.subheader("Create a unique code")
            new_code = st.text_input("Code", placeholder="CAMPUS06")
            label = st.text_input("Ambassador label", placeholder="Student ambassador 06")
            create = st.form_submit_button("Create referral code")
            if create:
                try:
                    referral_manager.create_code(new_code, label)
                    st.success("Referral code created.")
                except (ValueError, sqlite3.Error) as exc:
                    st.error(str(exc) or "The code could not be created.")
    with right:
        with st.form("referral_registration", clear_on_submit=True):
            st.subheader("Record an attributed simulation")
            name = st.text_input("Demo identifier", placeholder="Demo Student 022")
            email = st.text_input("Unique demo email", placeholder="demo+022@example.invalid")
            college = st.text_input("College", placeholder="Demo Engineering College")
            code = st.selectbox("Valid referral code", codes["code"].tolist() or ["No codes available"])
            create_registration = st.form_submit_button("Record referral registration", type="primary")
            if create_registration:
                if not name.strip() or not college.strip() or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()):
                    st.error("Enter a demo identifier, college, and valid demo email.")
                else:
                    try:
                        if not referral_manager.validate_referral_code(code):
                            raise database.InvalidReferralCodeError("Choose a currently valid referral code.")
                        database.add_registration(name, email, college, "Peer referrals", referral_code=code, source="manual")
                        st.success("Attributed simulated registration recorded.")
                    except (ValueError, sqlite3.Error) as exc:
                        st.error(str(exc) or "The registration could not be recorded.")


def experiment_page() -> None:
    heading("Campaign experiments", "Compare two message hypotheses using editable, simulated funnel inputs.")
    st.warning("Example results are simulated inputs, not evidence that an experiment has run. Real tests need comparable audiences and a consistent measurement period.")
    variants = database.get_experiment_variants()
    forms = st.columns(2)
    for index, variant in variants.iterrows():
        with forms[index % 2]:
            st.markdown(f"#### Variant {variant['variant']}")
            st.write(variant["message"])
            with st.form(f"variant_{variant['variant']}"):
                reach = st.number_input("People reached", min_value=0, step=1, value=int(variant["people_reached"]), key=f"reach_{variant['variant']}")
                clicks = st.number_input("Link clicks", min_value=0, step=1, value=int(variant["clicks"]), key=f"clicks_{variant['variant']}")
                registrations = st.number_input("Hypothetical registrations", min_value=0, step=1, value=int(variant["registrations"]), key=f"registrations_{variant['variant']}")
                submitted = st.form_submit_button(f"Save Variant {variant['variant']} inputs")
                if submitted:
                    try:
                        database.update_experiment_variant(variant["variant"], int(reach), int(clicks), int(registrations))
                        st.success(f"Variant {variant['variant']} simulation inputs saved.")
                    except (ValueError, sqlite3.Error) as exc:
                        st.error(str(exc) or "Experiment inputs could not be saved.")
    variants = database.get_experiment_variants()
    variants["CTR (%)"] = variants.apply(lambda row: metrics.click_through_rate(int(row["clicks"]), int(row["people_reached"])), axis=1)
    variants["Click-to-registration (%)"] = variants.apply(lambda row: metrics.click_to_registration_rate(int(row["registrations"]), int(row["clicks"])), axis=1)
    variants["Results"] = "Simulated"
    st.subheader("Funnel comparison")
    st.dataframe(variants[["variant", "people_reached", "clicks", "registrations", "CTR (%)", "Click-to-registration (%)", "Results"]].rename(columns={"variant": "Variant", "people_reached": "Reach", "clicks": "Clicks", "registrations": "Registrations"}), use_container_width=True, hide_index=True)
    chart_data = variants.melt(id_vars="variant", value_vars=["CTR (%)", "Click-to-registration (%)"], var_name="Metric", value_name="Rate (%)")
    chart = px.bar(chart_data, x="variant", y="Rate (%)", color="Metric", barmode="group", color_discrete_sequence=[CORAL, MINT])
    chart.update_layout(xaxis_title="Message variant", yaxis_title="Rate (%)", margin=dict(t=15, b=10), height=320)
    st.plotly_chart(chart, use_container_width=True)
    enough_data = len(variants) >= 2 and (variants["clicks"] >= 20).all()
    if enough_data:
        best = variants.sort_values("Click-to-registration (%)", ascending=False).iloc[0]
        st.info(f"Variant {best['variant']} currently has the higher click-to-registration rate in these simulated inputs ({best['Click-to-registration (%)']:.2f}%). This is descriptive only, not a significance claim.")
    else:
        st.caption("A higher-conversion callout appears only after both variants have at least 20 simulated clicks; this is a lightweight data-volume guard, not a statistical test.")


def assistant_page() -> None:
    heading("AI campaign assistant", "Generate channel-ready workshop copy from local templates, with no external AI service.")
    st.caption("Template-generated copy; this page does not call a live AI model.")
    with st.form("message_options"):
        audience = st.selectbox("Audience", list(campaign_generator.AUDIENCES))
        channel = st.selectbox("Channel", ["WhatsApp", "Email", "College club announcement", "Social media"])
        tone = st.selectbox("Tone", ["Friendly", "Professional", "Energetic"])
        benefit = st.selectbox("Primary benefit", list(campaign_generator.BENEFITS))
        cta = st.text_input("Call to action", value="Save your spot")
        generate = st.form_submit_button("Generate message", type="primary")
    if generate or "generated_message" not in st.session_state:
        counter = st.session_state.get("generation_count", 0) + 1
        st.session_state["generation_count"] = counter
        st.session_state["generated_message"] = campaign_generator.generate_message(audience, channel, tone, benefit, cta, seed=counter)
    if st.button("Regenerate wording"):
        counter = st.session_state.get("generation_count", 0) + 1
        st.session_state["generation_count"] = counter
        st.session_state["generated_message"] = campaign_generator.generate_message(audience, channel, tone, benefit, cta, seed=counter)
    st.text_area("Copy-ready message", key="generated_message", height=240)
    st.caption("No registration URL was supplied, so the generated copy uses [REGISTRATION LINK]. Review claims and add an approved link before sharing.")


def planner_page() -> None:
    heading("Channel planner", "Shape the seven-day acquisition hypothesis and keep its budget transparent.")
    st.info("Planning assumptions, not guaranteed results. ₹0 organic allocations assume existing student communities and volunteer distribution; coordination still has operational costs.")
    plans = database.get_campaign_plans()
    edited = st.data_editor(
        plans,
        hide_index=True,
        use_container_width=True,
        disabled=["channel", "is_reserve"],
        column_config={
            "channel": st.column_config.TextColumn("Acquisition channel"),
            "registration_target": st.column_config.NumberColumn("Registration target", min_value=0, step=1, format="%d"),
            "planned_budget": st.column_config.NumberColumn("Planned budget (₹)", min_value=0, step=100, format="₹%.0f"),
            "is_reserve": st.column_config.CheckboxColumn("Reserve", help="Reserve budget is not assigned a registration target."),
        },
        key="campaign_plan_editor",
    )
    try:
        total_target, total_budget, reserve = metrics.campaign_plan_totals(edited)
    except ValueError as exc:
        st.error(str(exc))
        return
    reserve_mask = edited["is_reserve"].map(lambda value: bool(value) if pd.notna(value) else False).astype(bool)
    target_col, budget_col, reserve_col = st.columns(3)
    target_col.metric("Planned registrations", f"{total_target:,}", "Target: 500")
    budget_col.metric("Planned budget", money(total_budget), "Hypothetical")
    reserve_col.metric("Contingency reserve", money(reserve))
    if total_budget > 2000:
        st.warning(f"Planned budget exceeds the ₹2,000 hypothetical cap by {money(total_budget - 2000)}.")
    if total_target != 500:
        st.warning(f"Current channel targets total {total_target}, not the 500-registration objective.")
    target_rows = edited.loc[~reserve_mask].copy()
    target_rows["Target share (%)"] = target_rows["registration_target"].fillna(0).apply(lambda value: round(value / total_target * 100, 1) if total_target else 0)
    chart = px.bar(target_rows, x="channel", y="registration_target", color_discrete_sequence=[MINT], hover_data=["Target share (%)"])
    chart.update_layout(xaxis_title=None, yaxis_title="Registration target", margin=dict(t=10, b=10), height=310)
    st.plotly_chart(chart, use_container_width=True)
    if st.button("Save channel plan", type="primary"):
        try:
            database.save_campaign_plans(edited)
            st.success("Channel plan saved.")
        except (ValueError, sqlite3.Error, TypeError) as exc:
            st.error(str(exc) or "The channel plan could not be saved.")
    st.subheader("Seven-day campaign schedule")
    schedule = pd.DataFrame([
        ("Day 1", "Confirm workshop details, audience, and approved registration page"),
        ("Day 2", "Prepare message variants and sharing kit for student communities"),
        ("Day 3", "Invite campus clubs and brief volunteer ambassadors"),
        ("Day 4", "Begin community distribution; monitor source attribution"),
        ("Day 5", "Review funnel inputs and adjust channel emphasis"),
        ("Day 6", "Share a reminder with participating communities"),
        ("Day 7", "Close the registration window and summarize learnings"),
    ], columns=["Day", "Planning activity"])
    st.dataframe(schedule, use_container_width=True, hide_index=True)
    st.markdown('<div class="section-rule"></div>', unsafe_allow_html=True)
    spend = database.get_simulated_spend()
    with st.form("spend_form"):
        proposed_spend = st.number_input("Simulated spend (₹; no real money)", min_value=0.0, value=spend, step=100.0)
        save_spend = st.form_submit_button("Save simulated spend")
        if save_spend:
            try:
                database.save_simulated_spend(proposed_spend)
                st.success("Simulated spend value saved separately from planned budget.")
            except (ValueError, sqlite3.Error) as exc:
                st.error(str(exc) or "Simulated spend could not be saved.")


PAGES = {
    "Growth overview": overview_page,
    "Registration tracker": registration_tracker_page,
    "Referral tracker": referral_tracker_page,
    "Campaign experiments": experiment_page,
    "AI campaign assistant": assistant_page,
    "Channel planner": planner_page,
}

with st.sidebar:
    st.markdown('<div class="brand-mark">LaunchLoop ↗</div><div class="brand-tag">Turn Student Communities Into Measurable Growth.</div>', unsafe_allow_html=True)
    selection = st.radio("Workspace", list(PAGES), label_visibility="collapsed")
    st.markdown("---")
    st.caption("SIMULATION ONLY")
    st.caption("No students are contacted and no money is spent by this app.")

PAGES[selection]()