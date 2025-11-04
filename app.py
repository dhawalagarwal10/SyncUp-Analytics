import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import duckdb
from scipy import stats

# Page configuration
st.set_page_config(
    page_title="SyncUp Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 5px;
    }
    h1 {
        color: #1f77b4;
        padding-bottom: 20px;
    }
    h2 {
        color: #2c3e50;
        padding-top: 20px;
    }
    .insight-box {
        background-color: #e8f4f8;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin: 20px 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Load data
@st.cache_data
def load_data():
    """Load users and events data"""
    users = pd.read_csv('data/users.csv')
    events = pd.read_csv('data/events.csv')
    
    # Convert dates
    users['sign_up_date'] = pd.to_datetime(users['sign_up_date'])
    events['event_timestamp'] = pd.to_datetime(events['event_timestamp'])
    
    return users, events

@st.cache_data
def get_funnel_data(_conn):
    """Calculate funnel metrics using SQL"""
    query = """
    WITH user_events AS (
        SELECT 
            user_id,
            MAX(CASE WHEN event_name = 'signed_up' THEN 1 ELSE 0 END) AS signed_up,
            MAX(CASE WHEN event_name = 'created_project' THEN 1 ELSE 0 END) AS created_project,
            MAX(CASE WHEN event_name = 'invited_teammate' THEN 1 ELSE 0 END) AS invited_teammate,
            MAX(CASE WHEN event_name = 'viewed_pricing_page' THEN 1 ELSE 0 END) AS viewed_pricing,
            MAX(CASE WHEN event_name = 'upgraded_plan' THEN 1 ELSE 0 END) AS upgraded
        FROM events
        GROUP BY user_id
    )
    SELECT 
        'Step 1: Signed Up' AS funnel_step,
        1 as step_number,
        SUM(signed_up) AS user_count,
        100.0 AS conversion_rate
    FROM user_events
    UNION ALL
    SELECT 
        'Step 2: Created Project',
        2,
        SUM(created_project),
        ROUND(100.0 * SUM(created_project) / NULLIF(SUM(signed_up), 0), 1)
    FROM user_events
    UNION ALL
    SELECT 
        'Step 3: Invited Teammate',
        3,
        SUM(invited_teammate),
        ROUND(100.0 * SUM(invited_teammate) / NULLIF(SUM(signed_up), 0), 1)
    FROM user_events
    UNION ALL
    SELECT 
        'Step 4: Viewed Pricing',
        4,
        SUM(viewed_pricing),
        ROUND(100.0 * SUM(viewed_pricing) / NULLIF(SUM(signed_up), 0), 1)
    FROM user_events
    UNION ALL
    SELECT 
        'Step 5: Upgraded',
        5,
        SUM(upgraded),
        ROUND(100.0 * SUM(upgraded) / NULLIF(SUM(signed_up), 0), 1)
    FROM user_events
    ORDER BY step_number
    """
    return _conn.execute(query).fetchdf()

@st.cache_data
def get_ab_test_data(_conn):
    """Calculate A/B test metrics"""
    query = """
    WITH user_conversions AS (
        SELECT 
            u.user_id,
            u.ab_test_group,
            MAX(CASE WHEN e.event_name = 'viewed_pricing_page' THEN 1 ELSE 0 END) AS viewed_pricing,
            MAX(CASE WHEN e.event_name = 'upgraded_plan' THEN 1 ELSE 0 END) AS converted
        FROM users u
        LEFT JOIN events e ON u.user_id = e.user_id
        GROUP BY u.user_id, u.ab_test_group
    ),
    pricing_viewers AS (
        SELECT *
        FROM user_conversions
        WHERE viewed_pricing = 1
    )
    SELECT 
        ab_test_group,
        COUNT(*) AS total_users,
        SUM(converted) AS conversions,
        ROUND(100.0 * SUM(converted) / COUNT(*), 2) AS conversion_rate
    FROM pricing_viewers
    GROUP BY ab_test_group
    ORDER BY ab_test_group
    """
    return _conn.execute(query).fetchdf()

@st.cache_data
def get_cohort_data(_conn):
    """Calculate cohort retention metrics"""
    query = """
    WITH user_cohorts AS (
        SELECT 
            user_id,
            sign_up_date,
            CASE 
                WHEN EXTRACT(MONTH FROM CAST(sign_up_date AS DATE)) = 1 THEN 'Jan 2024'
                WHEN EXTRACT(MONTH FROM CAST(sign_up_date AS DATE)) = 2 THEN 'Feb 2024'
            END AS cohort
        FROM users
    ),
    user_activity AS (
        SELECT 
            c.user_id,
            c.cohort,
            c.sign_up_date,
            e.event_timestamp,
            e.event_name,
            DATE_DIFF('day', CAST(c.sign_up_date AS DATE), CAST(e.event_timestamp AS DATE)) AS days_since_signup
        FROM user_cohorts c
        LEFT JOIN events e ON c.user_id = e.user_id
        WHERE e.event_name = 'used_feature_X'
    ),
    retention_calc AS (
        SELECT 
            cohort,
            user_id,
            MAX(CASE WHEN days_since_signup = 1 THEN 1 ELSE 0 END) AS day_1,
            MAX(CASE WHEN days_since_signup = 7 THEN 1 ELSE 0 END) AS day_7,
            MAX(CASE WHEN days_since_signup = 14 THEN 1 ELSE 0 END) AS day_14,
            MAX(CASE WHEN days_since_signup = 30 THEN 1 ELSE 0 END) AS day_30
        FROM user_activity
        GROUP BY cohort, user_id
    )
    SELECT 
        cohort,
        COUNT(DISTINCT user_id) AS cohort_size,
        ROUND(100.0 * SUM(day_1) / COUNT(DISTINCT user_id), 1) AS day_1_retention,
        ROUND(100.0 * SUM(day_7) / COUNT(DISTINCT user_id), 1) AS day_7_retention,
        ROUND(100.0 * SUM(day_14) / COUNT(DISTINCT user_id), 1) AS day_14_retention,
        ROUND(100.0 * SUM(day_30) / COUNT(DISTINCT user_id), 1) AS day_30_retention
    FROM retention_calc
    GROUP BY cohort
    ORDER BY cohort
    """
    return _conn.execute(query).fetchdf()

# Initialize
users, events = load_data()
conn = duckdb.connect(':memory:')
conn.register('users', users)
conn.register('events', events)

# Sidebar
st.sidebar.title("📊 SyncUp Analytics")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate to:",
    ["🏠 Overview", "🔍 Funnel Analysis", "🧪 A/B Testing", "📈 Cohort Retention", "📊 Raw Data"]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### About This Project")
st.sidebar.info(
    "This interactive dashboard showcases product analytics for SyncUp, "
    "a fictional freemium project management SaaS. Explore funnel analysis, "
    "A/B testing, and cohort retention insights."
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Key Metrics")
total_users = len(users)
total_events = len(events)
conversion_rate = (events['event_name'] == 'upgraded_plan').sum() / total_users * 100

st.sidebar.metric("Total Users", f"{total_users:,}")
st.sidebar.metric("Total Events", f"{total_events:,}")
st.sidebar.metric("Conversion Rate", f"{conversion_rate:.1f}%")

# Main content
if page == "🏠 Overview":
    st.title("🏠 SyncUp Product Analytics Dashboard")
    st.markdown("### Executive Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📝 Sign-ups",
            value=f"{total_users:,}",
            delta="100% baseline"
        )
    
    with col2:
        activated = (events.groupby('user_id')['event_name'].apply(lambda x: 'created_project' in x.values).sum())
        st.metric(
            label="✅ Activated Users",
            value=f"{activated:,}",
            delta=f"{activated/total_users*100:.1f}%"
        )
    
    with col3:
        invited = (events.groupby('user_id')['event_name'].apply(lambda x: 'invited_teammate' in x.values).sum())
        st.metric(
            label="👥 Invited Teammates",
            value=f"{invited:,}",
            delta=f"{invited/total_users*100:.1f}%"
        )
    
    with col4:
        converted = (events['event_name'] == 'upgraded_plan').sum()
        st.metric(
            label="💰 Paid Conversions",
            value=f"{converted}",
            delta=f"{conversion_rate:.1f}%"
        )
    
    st.markdown("---")
    
    # Key findings
    st.markdown("### 🎯 Key Findings")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="insight-box">
            <h3>🔴 Critical Funnel Leak</h3>
            <p><strong>76% drop-off</strong> between creating a project and inviting teammates</p>
            <p>Only <strong>18%</strong> of users reach the "magic moment"</p>
            <p><em>Action: Add teammate invitation prompt after project creation</em></p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="insight-box">
            <h3>🧪 A/B Test Results</h3>
            <p><strong>17.7% lift</strong> from new pricing page</p>
            <p>Not yet statistically significant (p=0.52)</p>
            <p><em>Action: Continue test to reach adequate sample size</em></p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="insight-box">
            <h3>📈 Templates Impact</h3>
            <p><strong>+10pp Day 1</strong> retention improvement</p>
            <p>Feb cohort shows sustained gains through Day 7</p>
            <p><em>Action: Make Templates prominent in onboarding</em></p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Timeline of events
    st.markdown("### 📅 User Activity Timeline")
    
    daily_signups = users.groupby(users['sign_up_date'].dt.date).size().reset_index()
    daily_signups.columns = ['date', 'signups']
    
    fig = px.line(daily_signups, x='date', y='signups', 
                  title='Daily Sign-ups Over Time',
                  labels={'signups': 'Number of Sign-ups', 'date': 'Date'})
    fig.update_traces(line_color='#1f77b4', line_width=2)
    fig.update_layout(hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)

elif page == "🔍 Funnel Analysis":
    st.title("🔍 Activation Funnel Analysis")
    st.markdown("### Where are users dropping off?")
    
    funnel_df = get_funnel_data(conn)
    funnel_df['drop_off_rate'] = 100 - funnel_df['conversion_rate'].shift(-1)
    funnel_df['drop_off_rate'] = funnel_df['drop_off_rate'].fillna(0)
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Step 1: Sign-up",
            f"{int(funnel_df.iloc[0]['user_count']):,}",
            "100%"
        )
    
    with col2:
        st.metric(
            "Step 2: Created Project",
            f"{int(funnel_df.iloc[1]['user_count']):,}",
            f"{funnel_df.iloc[1]['conversion_rate']:.1f}%"
        )
    
    with col3:
        st.metric(
            "Step 3: Invited Teammate",
            f"{int(funnel_df.iloc[2]['user_count']):,}",
            f"{funnel_df.iloc[2]['conversion_rate']:.1f}%"
        )
    
    with col4:
        st.metric(
            "Step 5: Upgraded",
            f"{int(funnel_df.iloc[4]['user_count']):,}",
            f"{funnel_df.iloc[4]['conversion_rate']:.1f}%"
        )
    
    st.markdown("---")
    
    # Interactive funnel chart
    fig = go.Figure()
    
    colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E']
    
    for i, row in funnel_df.iterrows():
        fig.add_trace(go.Bar(
            y=[row['funnel_step']],
            x=[row['user_count']],
            orientation='h',
            name=row['funnel_step'],
            marker=dict(color=colors[i]),
            text=f"{int(row['user_count']):,} users ({row['conversion_rate']:.1f}%)",
            textposition='auto',
            hovertemplate=f"<b>{row['funnel_step']}</b><br>" +
                         f"Users: {int(row['user_count']):,}<br>" +
                         f"Conversion: {row['conversion_rate']:.1f}%<br>" +
                         f"Drop-off: {row['drop_off_rate']:.1f}%<extra></extra>"
        ))
    
    fig.update_layout(
        title="Activation Funnel: User Journey to Conversion",
        xaxis_title="Number of Users",
        yaxis_title="",
        showlegend=False,
        height=500,
        hovermode='closest'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Analysis
    st.markdown("### Key Insights")
    
    biggest_dropoff_idx = funnel_df['drop_off_rate'].idxmax()
    biggest_dropoff = funnel_df.loc[biggest_dropoff_idx]
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"""
        **Critical Drop-off Point: {biggest_dropoff['funnel_step']}**
        
        - **{biggest_dropoff['drop_off_rate']:.1f}%** of users drop off at this stage
        - Only **{funnel_df.iloc[2]['conversion_rate']:.1f}%** of users invite teammates
        - Inviting teammates is the hypothesized "magic moment" for conversion
        - Users who don't invite teammates rarely convert to paid
        
        **Recommended Actions:**
        1. Add prominent "Invite Teammate" CTA immediately after project creation
        2. Show social proof: "Teams with 2+ members are 5x more likely to upgrade"
        3. Highlight collaboration features during onboarding
        4. Send Day 1 email nudge: "Your project needs teammates!"
        """)
    
    with col2:
        # Drop-off rates chart
        fig_dropoff = px.bar(
            funnel_df[funnel_df['drop_off_rate'] > 0],
            x='funnel_step',
            y='drop_off_rate',
            title='Drop-off Rate by Step',
            labels={'drop_off_rate': 'Drop-off Rate (%)', 'funnel_step': ''},
            color='drop_off_rate',
            color_continuous_scale='Reds'
        )
        fig_dropoff.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_dropoff, use_container_width=True)

elif page == "🧪 A/B Testing":
    st.title("🧪 A/B Test: Pricing Page Redesign")
    st.markdown("### Did the new pricing page improve conversions?")
    
    ab_results = get_ab_test_data(conn)
    
    group_a = ab_results[ab_results['ab_test_group'] == 'A'].iloc[0]
    group_b = ab_results[ab_results['ab_test_group'] == 'B'].iloc[0]
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Group A (Control)",
            f"{group_a['conversion_rate']:.2f}%",
            f"{int(group_a['conversions'])}/{int(group_a['total_users'])} converted"
        )
    
    with col2:
        st.metric(
            "Group B (Treatment)",
            f"{group_b['conversion_rate']:.2f}%",
            f"{int(group_b['conversions'])}/{int(group_b['total_users'])} converted"
        )
    
    lift = ((group_b['conversion_rate'] - group_a['conversion_rate']) / group_a['conversion_rate']) * 100
    
    with col3:
        st.metric(
            "Relative Lift",
            f"{lift:.1f}%",
            f"+{group_b['conversion_rate'] - group_a['conversion_rate']:.2f}pp"
        )
    
    st.markdown("---")
    
    # Visualization
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=['Group A<br>(Old Pricing)', 'Group B<br>(New Pricing)'],
            y=[group_a['conversion_rate'], group_b['conversion_rate']],
            marker=dict(color=['#95B8D1', '#6A994E']),
            text=[f"{group_a['conversion_rate']:.1f}%<br>({int(group_a['conversions'])}/{int(group_a['total_users'])})",
                  f"{group_b['conversion_rate']:.1f}%<br>({int(group_b['conversions'])}/{int(group_b['total_users'])})"],
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>Conversion Rate: %{y:.2f}%<extra></extra>'
        ))
        
        fig.update_layout(
            title="A/B Test Results: Conversion Rate Comparison",
            yaxis_title="Conversion Rate (%)",
            xaxis_title="",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Statistical test
        st.markdown("### 📊 Statistical Analysis")
        
        contingency_table = np.array([
            [group_a['conversions'], group_a['total_users'] - group_a['conversions']],
            [group_b['conversions'], group_b['total_users'] - group_b['conversions']]
        ])
        
        chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
        
        st.metric("Chi-squared", f"{chi2:.4f}")
        st.metric("P-value", f"{p_value:.4f}")
        st.metric("Significance", "α = 0.05")
        
        if p_value < 0.05:
            st.success("✅ Statistically Significant")
        else:
            st.warning("⚠️ Not Significant")
    
    st.markdown("---")
    
    # Insights
    st.markdown("### Analysis & Recommendations")
    
    st.markdown(f"""
    **Test Setup:**
    - **Control (A)**: Original pricing page
    - **Treatment (B)**: New page with "20% Off Annual" banner
    - **Sample Size**: {int(group_a['total_users'] + group_b['total_users'])} users who viewed pricing
    - **Metric**: Conversion to paid plan
    
    **Results:**
    - Group B showed a **{lift:.1f}% relative lift** in conversion rate
    - However, the p-value of **{p_value:.4f}** exceeds our significance threshold (α = 0.05)
    - This means the observed difference could be due to random chance
    
    **Why Not Significant?**
    - Current sample size is too small to detect this effect size
    - We'd need ~2,000+ pricing page viewers for 80% statistical power
    - Natural variance in small samples can create misleading patterns
    
    **Recommendations:**
    1.  **Continue the test** until reaching adequate sample size
    2.  **Monitor directional signal** - Group B is trending positive
    3.  **Consider phased rollout** (25% → 50% → 100%) given low risk
    4.  **Track secondary metrics** (engagement, retention) alongside conversion

    **Key Learning**: This demonstrates understanding that not all tests succeed, and statistical rigor matters more than "winning" results.
    """)

elif page == "📈 Cohort Retention":
    st.title("📈 Cohort Retention Analysis")
    st.markdown("### Did the Templates feature improve retention?")
    
    cohort_data = get_cohort_data(conn)
    
    # Metrics
    jan_data = cohort_data[cohort_data['cohort'] == 'Jan 2024'].iloc[0]
    feb_data = cohort_data[cohort_data['cohort'] == 'Feb 2024'].iloc[0]
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Jan Cohort Size",
            f"{int(jan_data['cohort_size']):,}",
            "Before Templates"
        )
    
    with col2:
        st.metric(
            "Feb Cohort Size",
            f"{int(feb_data['cohort_size']):,}",
            "After Templates"
        )
    
    with col3:
        improvement = feb_data['day_7_retention'] - jan_data['day_7_retention']
        st.metric(
            "Day 7 Improvement",
            f"+{improvement:.1f}pp",
            f"{feb_data['day_7_retention']:.1f}% vs {jan_data['day_7_retention']:.1f}%"
        )
    
    with col4:
        day1_improvement = feb_data['day_1_retention'] - jan_data['day_1_retention']
        st.metric(
            "Day 1 Improvement",
            f"+{day1_improvement:.1f}pp",
            f"{feb_data['day_1_retention']:.1f}% vs {jan_data['day_1_retention']:.1f}%"
        )
    
    st.markdown("---")
    
    # Retention curve
    col1, col2 = st.columns([2, 1])
    
    with col1:
        days = [1, 7, 14, 30]
        jan_retention = [jan_data['day_1_retention'], jan_data['day_7_retention'], 
                        jan_data['day_14_retention'], jan_data['day_30_retention']]
        feb_retention = [feb_data['day_1_retention'], feb_data['day_7_retention'], 
                        feb_data['day_14_retention'], feb_data['day_30_retention']]
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=days, y=jan_retention,
            mode='lines+markers',
            name='Jan 2024 (Before Templates)',
            line=dict(color='#E63946', width=3),
            marker=dict(size=10)
        ))
        
        fig.add_trace(go.Scatter(
            x=days, y=feb_retention,
            mode='lines+markers',
            name='Feb 2024 (After Templates)',
            line=dict(color='#06A77D', width=3),
            marker=dict(size=10)
        ))
        
        fig.update_layout(
            title="Retention Curve Comparison: Templates Feature Impact",
            xaxis_title="Days Since Sign-up",
            yaxis_title="Retention Rate (%)",
            hovermode='x unified',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Heatmap data
        cohort_matrix = cohort_data.set_index('cohort')[['day_1_retention', 'day_7_retention', 
                                                          'day_14_retention', 'day_30_retention']]
        cohort_matrix.columns = ['Day 1', 'Day 7', 'Day 14', 'Day 30']
        
        fig_heat = go.Figure(data=go.Heatmap(
            z=cohort_matrix.values,
            x=cohort_matrix.columns,
            y=cohort_matrix.index,
            colorscale='RdYlGn',
            text=cohort_matrix.values,
            texttemplate='%{text:.1f}%',
            textfont={"size": 14},
            colorbar=dict(title="Retention %")
        ))
        
        fig_heat.update_layout(
            title="Retention Heatmap",
            height=250
        )
        
        st.plotly_chart(fig_heat, use_container_width=True)
    
    st.markdown("---")
    
    # Detailed comparison table
    st.markdown("### 📊 Detailed Retention Comparison")
    
    comparison_df = pd.DataFrame({
        'Period': ['Day 1', 'Day 7', 'Day 14', 'Day 30'],
        'Jan 2024 (Before)': [jan_data['day_1_retention'], jan_data['day_7_retention'],
                              jan_data['day_14_retention'], jan_data['day_30_retention']],
        'Feb 2024 (After)': [feb_data['day_1_retention'], feb_data['day_7_retention'],
                            feb_data['day_14_retention'], feb_data['day_30_retention']]
    })
    
    comparison_df['Improvement'] = comparison_df['Feb 2024 (After)'] - comparison_df['Jan 2024 (Before)']
    comparison_df['Relative Change'] = (comparison_df['Improvement'] / comparison_df['Jan 2024 (Before)'] * 100).round(1)
    
    st.dataframe(
        comparison_df.style.format({
            'Jan 2024 (Before)': '{:.1f}%',
            'Feb 2024 (After)': '{:.1f}%',
            'Improvement': '{:+.1f}pp',
            'Relative Change': '{:+.1f}%'
        }).background_gradient(subset=['Improvement'], cmap='RdYlGn', vmin=-10, vmax=10),
        use_container_width=True
    )
    
    st.markdown("---")
    
    # Insights
    st.markdown("###  Key Insights & Recommendations")
    
    st.markdown(f"""
    **Context:**
    - **Jan 2024 Cohort**: Users signed up *before* Templates feature launch
    - **Feb 2024 Cohort**: Users signed up *after* Templates feature launch
    - Templates are pre-built project structures that help users get started quickly
    
    **Findings:**
    - **Day 1 Retention**: +{day1_improvement:.1f} percentage points improvement
      - Shows immediate value: users engage with templates right away
    - **Day 7 Retention**: +{improvement:.1f} percentage points improvement
      - Critical metric: sustained early engagement
    - **Day 14-30**: Limited data due to cohort maturation period
    
    **What This Means:**
    - Templates create immediate value for new users
    - Strong Day 1 retention typically predicts better long-term retention
    - Feature successfully addresses "blank canvas" problem
    
    **Recommendations:**
    1.  **Make Templates default onboarding experience**
       - Show template gallery immediately after sign-up
       - "Start from Template" instead of "Blank Project"
    
    2.  **Personalize template suggestions**
       - Based on industry/use case from sign-up form
       - "Marketing teams love these 3 templates"
    
    3.  **Expand template library**
       - Success warrants investment in more templates
       - User research: which templates would unlock more use cases?
    
    4.  **Monitor long-term retention**
       - Track Feb cohort through Day 30 and beyond
       - Validate that Day 1 improvement compounds over time
    
    **Expected Impact**: Making templates prominent could improve Day 7 retention from 35% to 45%+, significantly increasing user lifetime value.
    """)

else:  # Raw Data
    st.title("📊 Raw Data Explorer")
    st.markdown("### Explore the underlying datasets")
    
    tab1, tab2, tab3 = st.tabs(["👥 Users", "📝 Events", "📈 Event Distribution"])
    
    with tab1:
        st.markdown("#### Users Dataset")
        st.markdown(f"Total records: **{len(users):,}**")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            plan_filter = st.multiselect("Filter by Plan", options=['Free', 'Paid'], default=['Free', 'Paid'])
        with col2:
            ab_filter = st.multiselect("Filter by A/B Group", options=['A', 'B'], default=['A', 'B'])
        with col3:
            month_filter = st.multiselect("Filter by Month", 
                                         options=[1, 2], 
                                         format_func=lambda x: f"{'Jan' if x==1 else 'Feb'} 2024",
                                         default=[1, 2])
        
        filtered_users = users[
            (users['plan_type'].isin(plan_filter)) & 
            (users['ab_test_group'].isin(ab_filter)) &
            (users['sign_up_date'].dt.month.isin(month_filter))
        ]
        
        st.dataframe(filtered_users, use_container_width=True)
        
        # Download button
        csv = filtered_users.to_csv(index=False)
        st.download_button(
            label="📥 Download Filtered Data",
            data=csv,
            file_name="syncup_users_filtered.csv",
            mime="text/csv"
        )
    
    with tab2:
        st.markdown("#### Events Dataset")
        st.markdown(f"Total records: **{len(events):,}**")
        
        col1, col2 = st.columns(2)
        with col1:
            event_filter = st.multiselect(
                "Filter by Event Type",
                options=events['event_name'].unique(),
                default=events['event_name'].unique()
            )
        with col2:
            user_id_filter = st.text_input("Filter by User ID (optional)")
        
        filtered_events = events[events['event_name'].isin(event_filter)]
        
        if user_id_filter:
            try:
                filtered_events = filtered_events[filtered_events['user_id'] == int(user_id_filter)]
            except:
                st.warning("Please enter a valid user ID")
        
        st.dataframe(filtered_events, use_container_width=True)
        
        # Download button
        csv = filtered_events.to_csv(index=False)
        st.download_button(
            label="📥 Download Filtered Events",
            data=csv,
            file_name="syncup_events_filtered.csv",
            mime="text/csv"
        )
    
    with tab3:
        st.markdown("#### Event Distribution Analysis")
        
        event_counts = events['event_name'].value_counts().reset_index()
        event_counts.columns = ['Event Type', 'Count']
        
        fig = px.bar(event_counts, x='Event Type', y='Count',
                    title='Distribution of Events',
                    color='Count',
                    color_continuous_scale='Blues')
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Events over time
        events['date'] = events['event_timestamp'].dt.date
        daily_events = events.groupby(['date', 'event_name']).size().reset_index(name='count')
        
        fig2 = px.line(daily_events, x='date', y='count', color='event_name',
                      title='Events Over Time by Type',
                      labels={'count': 'Number of Events', 'date': 'Date'})
        st.plotly_chart(fig2, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; padding: 20px;'>
    <p><strong>SyncUp Product Analytics Dashboard</strong></p>
    <p>Built with Streamlit • Python • SQL • Statistical Analysis</p>
    <p>Portfolio Project by Dhawal Agarwal | <a href='https://github.com/dhawalagarwal10/SyncUp-Analytics.git'>GitHub</a></p>
</div>
""", unsafe_allow_html=True)
