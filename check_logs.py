
import os
import re
import glob

# Common Supervisor Log Paths
# Tries to find the most recent log file
LOG_PATTERNS = [
    "/var/log/aladdin_master.out.log",
    "/var/log/aladdin_master.err.log",
    "/var/log/supervisor/aladdin-master*.log",
    "/root/aladdin-bot-final/master_tracker.log",
    "/root/aladdin-bot-final/nohup.out"
]

def find_log_files():
    found = []
    for pattern in LOG_PATTERNS:
        matches = glob.glob(pattern)
        found.extend(matches)
    return found

def parse_logs(file_path):
    print(f"📖 Reading log file: {file_path}")
    
    events = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                
                # Check for Signal (Master)
                if "🚀 [QUEUE] SIGNAL" in line or "🚀 BingX Signal:" in line:
                    events.append({"type": "SIGNAL", "text": line})
                
                # Check for User Execution (Worker) - specifically 1778819795
                elif "User 1778819795" in line:
                    events.append({"type": "EXECUTION", "text": line})
                    
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        
    return events

def print_analysis(events):
    print("\n" + "="*60)
    print(f"📊 MASTER VS WORKER TIMELINE (Values in chronological order)")
    print("="*60)
    
    if not events:
        print("ℹ️ No relevant events found in this log.")
        return

    # Print relevant events chronologically
    # Since we read line by line, they are already ordered
    
    signal_count = 0
    exec_count = 0
    
    for e in events:
        if e['type'] == 'SIGNAL':
            signal_count += 1
            print(f"📡 {e['text']}")
        else:
            exec_count += 1
            # Indent execution to make it easier to see relationship
            print(f"    👤 {e['text']}")
            
    print("-" * 60)
    print(f"TOTAL SIGNALS: {signal_count}")
    print(f"TOTAL EXECUTIONS: {exec_count}")
    
    if signal_count > 0 and exec_count == 0:
        print("\n❌ CRITICAL: Signals received but NO trades for user.")
    elif signal_count > exec_count:
        print("\n⚠️ WARNING: More signals than executions. Check for specific missed trades.")
    else:
        print("\n✅ RATIO LOOKS GOOD.")

# --- MAIN ---
log_files = find_log_files()

if log_files:
    for lf in log_files:
        print(f"\n--- Analyzing {lf} ---")
        evs = parse_logs(lf)
        print_analysis(evs)
else:
    print("❌ Could not find Supervisor or local log files.")
    print("Please manually check: /var/log/supervisor/")
