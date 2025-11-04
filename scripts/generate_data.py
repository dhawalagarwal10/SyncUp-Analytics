import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Set seed for reproducibility
np.random.seed(42)
random.seed(42)

# Configuration
NUM_USERS = 2000
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2024, 2, 29)

def generate_users(num_users):
    """Generate users.csv with sign-up dates and plan types"""
    users = []
    
    for user_id in range(1, num_users + 1):
        # Random sign-up date between Jan 1 and Feb 29, 2024
        days_offset = random.randint(0, (END_DATE - START_DATE).days)
        sign_up_date = START_DATE + timedelta(days=days_offset)
        
        # Assign A/B test group (50/50 split)
        ab_test_group = random.choice(['A', 'B'])
        
        # Most users start as Free (95%), some start as Paid (5%)
        plan_type = 'Paid' if random.random() < 0.05 else 'Free'
        
        users.append({
            'user_id': user_id,
            'sign_up_date': sign_up_date.strftime('%Y-%m-%d'),
            'plan_type': plan_type,
            'ab_test_group': ab_test_group
        })
    
    return pd.DataFrame(users)

def generate_events(users_df):
    """Generate events.csv based on realistic user behavior patterns"""
    events = []
    event_id = 1
    
    for _, user in users_df.iterrows():
        user_id = user['user_id']
        sign_up_date = datetime.strptime(user['sign_up_date'], '%Y-%m-%d')
        plan_type = user['plan_type']
        ab_group = user['ab_test_group']
        
        # Everyone has a signed_up event
        events.append({
            'event_id': event_id,
            'user_id': user_id,
            'event_timestamp': sign_up_date.strftime('%Y-%m-%d %H:%M:%S'),
            'event_name': 'signed_up'
        })
        event_id += 1
        
        # 75% of users create a project (activation)
        if random.random() < 0.75:
            project_time = sign_up_date + timedelta(minutes=random.randint(5, 120))
            events.append({
                'event_id': event_id,
                'user_id': user_id,
                'event_timestamp': project_time.strftime('%Y-%m-%d %H:%M:%S'),
                'event_name': 'created_project'
            })
            event_id += 1
            
            # Only 25% of those who created project invite a teammate (key drop-off)
            # This is the "magic moment" - users who invite teammates are more likely to convert
            if random.random() < 0.25:
                invite_time = project_time + timedelta(hours=random.randint(1, 48))
                events.append({
                    'event_id': event_id,
                    'user_id': user_id,
                    'event_timestamp': invite_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'event_name': 'invited_teammate'
                })
                event_id += 1
                
                # Users who invited teammates are much more likely to view pricing (60%)
                if random.random() < 0.60:
                    pricing_time = invite_time + timedelta(hours=random.randint(2, 72))
                    events.append({
                        'event_id': event_id,
                        'user_id': user_id,
                        'event_timestamp': pricing_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'event_name': 'viewed_pricing_page'
                    })
                    event_id += 1
                    
                    # Conversion rate depends on A/B test group
                    # Group B (new pricing page) has higher conversion
                    conversion_rate = 0.35 if ab_group == 'B' else 0.25
                    
                    if random.random() < conversion_rate:
                        upgrade_time = pricing_time + timedelta(hours=random.randint(1, 24))
                        events.append({
                            'event_id': event_id,
                            'user_id': user_id,
                            'event_timestamp': upgrade_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'event_name': 'upgraded_plan'
                        })
                        event_id += 1
            else:
                # Users who didn't invite teammates rarely view pricing (10%)
                if random.random() < 0.10:
                    pricing_time = project_time + timedelta(hours=random.randint(2, 72))
                    events.append({
                        'event_id': event_id,
                        'user_id': user_id,
                        'event_timestamp': pricing_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'event_name': 'viewed_pricing_page'
                    })
                    event_id += 1
                    
                    # Very low conversion without teammate invite (5%)
                    if random.random() < 0.05:
                        upgrade_time = pricing_time + timedelta(hours=random.randint(1, 24))
                        events.append({
                            'event_id': event_id,
                            'user_id': user_id,
                            'event_timestamp': upgrade_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'event_name': 'upgraded_plan'
                        })
                        event_id += 1
        
        # Generate retention/activity events (for cohort analysis)
        # Users who signed up in Feb (after Templates feature) have better retention
        is_feb_cohort = sign_up_date.month == 2
        
        # Day 1 activity (70% of all users, 80% for Feb cohort)
        day1_rate = 0.80 if is_feb_cohort else 0.70
        if random.random() < day1_rate:
            day1_time = sign_up_date + timedelta(days=1, hours=random.randint(0, 23))
            if day1_time <= END_DATE:
                events.append({
                    'event_id': event_id,
                    'user_id': user_id,
                    'event_timestamp': day1_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'event_name': 'used_feature_X'
                })
                event_id += 1
        
        # Day 7 activity (30% of all users, 40% for Feb cohort - showing Templates impact)
        day7_rate = 0.40 if is_feb_cohort else 0.30
        if random.random() < day7_rate:
            day7_time = sign_up_date + timedelta(days=7, hours=random.randint(0, 23))
            if day7_time <= END_DATE:
                events.append({
                    'event_id': event_id,
                    'user_id': user_id,
                    'event_timestamp': day7_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'event_name': 'used_feature_X'
                })
                event_id += 1
        
        # Day 14 activity (20% of all users, 28% for Feb cohort)
        day14_rate = 0.28 if is_feb_cohort else 0.20
        if random.random() < day14_rate:
            day14_time = sign_up_date + timedelta(days=14, hours=random.randint(0, 23))
            if day14_time <= END_DATE:
                events.append({
                    'event_id': event_id,
                    'user_id': user_id,
                    'event_timestamp': day14_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'event_name': 'used_feature_X'
                })
                event_id += 1
        
        # Day 30 activity (15% of all users, 22% for Feb cohort)
        day30_rate = 0.22 if is_feb_cohort else 0.15
        if random.random() < day30_rate:
            day30_time = sign_up_date + timedelta(days=30, hours=random.randint(0, 23))
            if day30_time <= END_DATE:
                events.append({
                    'event_id': event_id,
                    'user_id': user_id,
                    'event_timestamp': day30_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'event_name': 'used_feature_X'
                })
                event_id += 1
    
    return pd.DataFrame(events)

def main():
    """Generate and save the datasets"""
    print("Generating SyncUp user and event data...")
    
    # Generate users
    print(f"Creating {NUM_USERS} users...")
    users_df = generate_users(NUM_USERS)
    
    # Generate events
    print("Generating user events...")
    events_df = generate_events(users_df)
    
    # Save to CSV
    users_df.to_csv('../data/users.csv', index=False)
    events_df.to_csv('../data/events.csv', index=False)
    
    print(f"\nData generation complete!")
    print(f"✓ Users: {len(users_df)} records saved to data/users.csv")
    print(f"✓ Events: {len(events_df)} records saved to data/events.csv")
    
    # Print summary statistics
    print("\n--- Summary Statistics ---")
    print(f"Date Range: {START_DATE.date()} to {END_DATE.date()}")
    print(f"Total Users: {len(users_df)}")
    print(f"  - Free Plan: {len(users_df[users_df['plan_type'] == 'Free'])}")
    print(f"  - Paid Plan: {len(users_df[users_df['plan_type'] == 'Paid'])}")
    print(f"  - A/B Group A: {len(users_df[users_df['ab_test_group'] == 'A'])}")
    print(f"  - A/B Group B: {len(users_df[users_df['ab_test_group'] == 'B'])}")
    print(f"\nTotal Events: {len(events_df)}")
    print("\nEvent Breakdown:")
    print(events_df['event_name'].value_counts())

if __name__ == "__main__":
    main()
