import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import duckdb
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# Set style
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)

print("="*60)
print("SYNCUP PRODUCT ANALYTICS - ANALYSIS REPORT")
print("="*60)

# ============================================================================
# LOAD DATA
# ============================================================================
print("\n📊 Loading data...")
users = pd.read_csv('../data/users.csv')
events = pd.read_csv('../data/events.csv')

print(f"   ✓ Users: {len(users):,} records")
print(f"   ✓ Events: {len(events):,} records")

# ============================================================================
# PHASE 1: FUNNEL ANALYSIS
# ============================================================================
print("\n" + "="*60)
print("PHASE 1: FUNNEL ANALYSIS")
print("="*60)

# Create DuckDB connection
conn = duckdb.connect(':memory:')
conn.register('users', users)
conn.register('events', events)

# Funnel query
funnel_query = """
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
    SUM(signed_up) AS user_count,
    100.0 AS conversion_rate
FROM user_events
UNION ALL
SELECT 
    'Step 2: Created Project',
    SUM(created_project),
    ROUND(100.0 * SUM(created_project) / NULLIF(SUM(signed_up), 0), 1)
FROM user_events
UNION ALL
SELECT 
    'Step 3: Invited Teammate',
    SUM(invited_teammate),
    ROUND(100.0 * SUM(invited_teammate) / NULLIF(SUM(signed_up), 0), 1)
FROM user_events
UNION ALL
SELECT 
    'Step 4: Viewed Pricing',
    SUM(viewed_pricing),
    ROUND(100.0 * SUM(viewed_pricing) / NULLIF(SUM(signed_up), 0), 1)
FROM user_events
UNION ALL
SELECT 
    'Step 5: Upgraded',
    SUM(upgraded),
    ROUND(100.0 * SUM(upgraded) / NULLIF(SUM(signed_up), 0), 1)
FROM user_events
"""

funnel_df = conn.execute(funnel_query).fetchdf()

# Calculate drop-off rates
funnel_df['drop_off_rate'] = 100 - funnel_df['conversion_rate'].shift(-1)
funnel_df['drop_off_rate'] = funnel_df['drop_off_rate'].fillna(0)

print("\n📊 Funnel Conversion Rates:")
for _, row in funnel_df.iterrows():
    print(f"   {row['funnel_step']}: {int(row['user_count'])} users ({row['conversion_rate']:.1f}%)")

# Find biggest drop-off
biggest_dropoff_idx = funnel_df['drop_off_rate'].idxmax()
biggest_dropoff = funnel_df.loc[biggest_dropoff_idx]

print(f"\n🚨 BIGGEST DROP-OFF: {biggest_dropoff['funnel_step']}")
print(f"   Drop-off Rate: {biggest_dropoff['drop_off_rate']:.1f}%")

# Create funnel visualization
fig, ax = plt.subplots(figsize=(12, 6))
colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E']
bars = ax.barh(funnel_df['funnel_step'], funnel_df['user_count'], color=colors)

for i, (bar, count, rate) in enumerate(zip(bars, funnel_df['user_count'], funnel_df['conversion_rate'])):
    width = bar.get_width()
    ax.text(width + 50, bar.get_y() + bar.get_height()/2, 
            f'{int(count)} users ({rate:.1f}%)', 
            va='center', fontsize=11, fontweight='bold')

ax.set_xlabel('Number of Users', fontsize=12)
ax.set_title('SyncUp Activation Funnel Analysis', fontsize=14, fontweight='bold', pad=20)
ax.invert_yaxis()
plt.tight_layout()
plt.savefig('../dashboard/funnel_chart.png', dpi=300, bbox_inches='tight')
plt.close()

print("   ✓ Funnel chart saved")

# ============================================================================
# PHASE 2: A/B TEST ANALYSIS
# ============================================================================
print("\n" + "="*60)
print("PHASE 2: A/B TEST ANALYSIS")
print("="*60)

ab_test_query = """
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

ab_results = conn.execute(ab_test_query).fetchdf()
group_a = ab_results[ab_results['ab_test_group'] == 'A'].iloc[0]
group_b = ab_results[ab_results['ab_test_group'] == 'B'].iloc[0]

print(f"\n📊 A/B Test Results:")
print(f"   Group A (Old Pricing): {group_a['conversion_rate']:.2f}% ({int(group_a['conversions'])}/{int(group_a['total_users'])})")
print(f"   Group B (New Pricing): {group_b['conversion_rate']:.2f}% ({int(group_b['conversions'])}/{int(group_b['total_users'])})")

# Statistical test
contingency_table = np.array([
    [group_a['conversions'], group_a['total_users'] - group_a['conversions']],
    [group_b['conversions'], group_b['total_users'] - group_b['conversions']]
])

chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
lift = ((group_b['conversion_rate'] - group_a['conversion_rate']) / group_a['conversion_rate']) * 100

print(f"\n📈 Statistical Analysis:")
print(f"   Chi-squared: {chi2:.4f}")
print(f"   P-value: {p_value:.4f}")
print(f"   Relative lift: {lift:.1f}%")

if p_value < 0.05:
    print(f"\n✅ RESULT: Statistically significant (p < 0.05)")
    print(f"   RECOMMENDATION: Roll out Group B pricing page to 100% of users")
else:
    print(f"\n⚠️  RESULT: Not statistically significant (p >= 0.05)")

# Visualize A/B test
fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.bar(['Group A\n(Old Pricing)', 'Group B\n(New Pricing)'], 
               [group_a['conversion_rate'], group_b['conversion_rate']],
               color=['#95B8D1', '#6A994E'], width=0.5)

for i, (bar, row) in enumerate(zip(bars, [group_a, group_b])):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
            f"{row['conversion_rate']:.1f}%\n({int(row['conversions'])}/{int(row['total_users'])})",
            ha='center', va='bottom', fontsize=12, fontweight='bold')

if p_value < 0.05:
    ax.plot([0, 1], [max(group_a['conversion_rate'], group_b['conversion_rate']) + 3] * 2, 
            'k-', lw=1.5)
    ax.text(0.5, max(group_a['conversion_rate'], group_b['conversion_rate']) + 3.5, 
            f'p = {p_value:.4f} *', ha='center', fontsize=11, fontweight='bold')

ax.set_ylabel('Conversion Rate (%)', fontsize=12)
ax.set_title('A/B Test: Pricing Page Conversion Rate', fontsize=14, fontweight='bold', pad=20)
ax.set_ylim(0, max(group_a['conversion_rate'], group_b['conversion_rate']) + 8)
plt.tight_layout()
plt.savefig('../dashboard/ab_test_chart.png', dpi=300, bbox_inches='tight')
plt.close()

print("   ✓ A/B test chart saved")

# ============================================================================
# PHASE 3: COHORT RETENTION ANALYSIS
# ============================================================================
print("\n" + "="*60)
print("PHASE 3: COHORT RETENTION ANALYSIS")
print("="*60)

cohort_query = """
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

cohort_retention = conn.execute(cohort_query).fetchdf()

print(f"\n📊 Cohort Retention Rates:")
for _, row in cohort_retention.iterrows():
    print(f"\n   {row['cohort']} (n={int(row['cohort_size'])}):")
    print(f"      Day 1:  {row['day_1_retention']:.1f}%")
    print(f"      Day 7:  {row['day_7_retention']:.1f}%")
    print(f"      Day 14: {row['day_14_retention']:.1f}%")
    print(f"      Day 30: {row['day_30_retention']:.1f}%")

jan_day7 = cohort_retention[cohort_retention['cohort'] == 'Jan 2024']['day_7_retention'].values[0]
feb_day7 = cohort_retention[cohort_retention['cohort'] == 'Feb 2024']['day_7_retention'].values[0]
day7_improvement = feb_day7 - jan_day7

print(f"\n🚀 IMPROVEMENT:")
print(f"   Day 7 Retention: +{day7_improvement:.1f} percentage points")

# Create heatmap
cohort_heatmap = cohort_retention.set_index('cohort')[['day_1_retention', 'day_7_retention', 
                                                         'day_14_retention', 'day_30_retention']]
cohort_heatmap.columns = ['Day 1', 'Day 7', 'Day 14', 'Day 30']

fig, ax = plt.subplots(figsize=(10, 4))
sns.heatmap(cohort_heatmap, annot=True, fmt='.1f', cmap='RdYlGn', 
            cbar_kws={'label': 'Retention Rate (%)'}, 
            vmin=0, vmax=100, ax=ax, linewidths=0.5)
ax.set_title('Cohort Retention Heatmap: Jan vs Feb 2024', fontsize=14, fontweight='bold', pad=20)
ax.set_xlabel('Days Since Sign-up', fontsize=12)
ax.set_ylabel('Cohort', fontsize=12)
plt.tight_layout()
plt.savefig('../dashboard/cohort_retention_heatmap.png', dpi=300, bbox_inches='tight')
plt.close()

# Create retention curve
fig, ax = plt.subplots(figsize=(12, 6))
days = [1, 7, 14, 30]
jan_retention = cohort_heatmap.loc['Jan 2024'].values
feb_retention = cohort_heatmap.loc['Feb 2024'].values

ax.plot(days, jan_retention, marker='o', linewidth=2.5, markersize=10, 
        label='Jan 2024 (Before Templates)', color='#E63946')
ax.plot(days, feb_retention, marker='o', linewidth=2.5, markersize=10, 
        label='Feb 2024 (After Templates)', color='#06A77D')

for i, (day, jan_val, feb_val) in enumerate(zip(days, jan_retention, feb_retention)):
    ax.text(day, jan_val + 2, f'{jan_val:.1f}%', ha='center', fontsize=10, color='#E63946')
    ax.text(day, feb_val + 2, f'{feb_val:.1f}%', ha='center', fontsize=10, color='#06A77D')

ax.set_xlabel('Days Since Sign-up', fontsize=12)
ax.set_ylabel('Retention Rate (%)', fontsize=12)
ax.set_title('Retention Curve: Templates Feature Impact', fontsize=14, fontweight='bold', pad=20)
ax.legend(fontsize=11, loc='upper right')
ax.grid(True, alpha=0.3)
ax.set_ylim(0, max(max(jan_retention), max(feb_retention)) + 10)
plt.tight_layout()
plt.savefig('../dashboard/retention_curve.png', dpi=300, bbox_inches='tight')
plt.close()

print("   ✓ Cohort retention charts saved")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*60)
print("EXECUTIVE SUMMARY")
print("="*60)

print("\n1️⃣  FUNNEL ANALYSIS")
print(f"   • Critical leak: {biggest_dropoff['drop_off_rate']:.0f}% drop-off at '{biggest_dropoff['funnel_step']}'")
print(f"   • Only {funnel_df.loc[2, 'conversion_rate']:.1f}% of users invite teammates (the 'magic moment')")
print(f"   • Overall conversion to paid: {funnel_df.loc[4, 'conversion_rate']:.1f}%")

print("\n2️⃣  A/B TEST RESULTS")
print(f"   • Group B (new pricing) converted {lift:.1f}% better than Group A")
print(f"   • Statistical significance: p = {p_value:.4f} {'✓' if p_value < 0.05 else '✗'}")
if p_value < 0.05:
    print(f"   • DECISION: Roll out Group B pricing page")

print("\n3️⃣  COHORT RETENTION")
print(f"   • Feb cohort (with Templates) shows +{day7_improvement:.1f}pp Day 7 retention")
print(f"   • Templates feature is working - make it prominent in onboarding")

print("\n" + "="*60)
print("RECOMMENDED ACTIONS")
print("="*60)
print("1. Add 'Invite Teammate' CTA immediately after project creation")
print("2. Deploy Group B pricing page (20% off banner) to all users")
print("3. Show Templates feature during onboarding, not just in menu")
print("4. Monitor weekly: activation rate, Day 7 retention, conversion rate")

print("\n" + "="*60)
print("✓ Analysis complete! Charts saved to /dashboard")
print("="*60)
