import subprocess
import sys
import os

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import streamlit
        import plotly
        import pandas
        import duckdb
        print("✓ All dependencies installed")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e.name}")
        print("\nPlease install dependencies:")
        print("  pip install -r requirements.txt")
        return False

def check_data():
    """Check if data files exist"""
    if os.path.exists('data/users.csv') and os.path.exists('data/events.csv'):
        print("✓ Data files found")
        return True
    else:
        print("✗ Data files not found")
        print("\nPlease generate data first:")
        print("  cd scripts && python generate_data.py && cd ..")
        return False

def launch_dashboard():
    """Launch the Streamlit dashboard"""
    print("\n" + "="*60)
    print("🚀 Launching SyncUp Analytics Dashboard...")
    print("="*60)
    print("\nThe dashboard will open in your default browser.")
    print("If it doesn't open automatically, navigate to: http://localhost:8501")
    print("\nPress Ctrl+C to stop the server\n")
    
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])
    except KeyboardInterrupt:
        print("\n\n✓ Dashboard stopped successfully")

if __name__ == "__main__":
    print("="*60)
    print("SyncUp Analytics Dashboard Launcher")
    print("="*60)
    print("\nChecking requirements...")
    
    if not check_dependencies():
        sys.exit(1)
    
    if not check_data():
        sys.exit(1)
    
    launch_dashboard()
