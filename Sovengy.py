import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import differential_entropy
import datetime
import warnings
import os
import sys

warnings.filterwarnings("ignore")

# ==============================================================================
# LOGGER: DUAL-STREAM OUTPUT
# ==============================================================================
class Logger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

# ==============================================================================
# CORE ENGINE: SOVE PRECISION (DECAY VELOCITY EDITION)
# ==============================================================================
class SOVE_Precision_Engine:
    def __init__(self):
        # 2026 Market Calibration Constants
        self.k = 13.4850
        self.alpha = 0.99
        self.vol_lookback = 20
        self.decay_limit = 1.15  # 15% increase in entropy = Structural Failure
        
        self.action_priority = {
            "BUY: GROWING": 0,
            "SELL: TANKING RISK": 1,
            "HOLD: NEUTRAL": 2,
            "DNA DECAY: TERMINAL": 3,
            "IGNORE": 4 
        }

    def auto_discover(self):
        return {
            "NVDA": "TECH", "AAPL": "TECH", "MSFT": "TECH", "AVGO": "TECH", 
            "ORCL": "TECH", "AMD": "TECH", "CRM": "TECH", "ADBE": "TECH", 
            "QCOM": "TECH", "IBM": "TECH", "MU": "TECH", "INTC": "TECH", 
            "NOW": "TECH", "ASML": "TECH", "PANW": "TECH", "SNPS": "TECH",
            "PLTR": "TECH", "CDNS": "TECH", "KLAC": "TECH", "AMAT": "TECH",
            "GOOGL": "COMM", "META": "COMM", "NFLX": "COMM", "DIS": "COMM", 
            "TMUS": "COMM", "VZ": "COMM", "T": "COMM", "CMCSA": "COMM",
            "BRK-B": "FIN", "JPM": "FIN", "V": "FIN", "MA": "FIN", 
            "BAC": "FIN", "MS": "FIN", "GS": "FIN", "WFC": "FIN", 
            "AXP": "FIN", "BLK": "FIN", "C": "FIN", "SCHW": "FIN",
            "LLY": "HLTH", "JNJ": "HLTH", "ABBV": "HLTH", "MRK": "HLTH", 
            "UNH": "HLTH", "AMGN": "HLTH", "ABT": "HLTH", "PFE": "HLTH", 
            "GILD": "HLTH", "SYK": "HLTH", "ISRG": "HLTH", "BMY": "HLTH",
            "AMZN": "CONS", "TSLA": "CONS", "WMT": "CONS", "COST": "CONS", 
            "PG": "CONS", "KO": "CONS", "PEP": "CONS", "HD": "CONS", 
            "LOW": "CONS", "MCD": "CONS", "NKE": "CONS", "SBUX": "CONS",
            "XOM": "ENER", "CVX": "ENER", "GE": "IND", "CAT": "IND", 
            "RTX": "IND", "HON": "IND", "LMT": "IND", "UPS": "IND"
        }

    def get_action_rank(self, action_str):
        if "IGNORE" in action_str: return 4
        if "DNA DECAY" in action_str: return 3
        return self.action_priority.get(action_str, 5)

    def run(self):
        print(f"[*] SOVE PRECISION START: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
        discovery_map = self.auto_discover()
        tickers = list(discovery_map.keys())
        
        # Download 1y for DNA baseline
        data = yf.download(tickers, period="1y", interval="1d", progress=False, threads=True)
        prices = data['Close']
        valid_tickers = [t for t in tickers if t in prices and not prices[t].isnull().all()]
        
        results = []
        for t in valid_tickers:
            p = prices[t].dropna()
            if len(p) < 60: continue # Need enough for 40d slice vs 1y baseline
            
            # 1. Calculate Baselines
            rets_full = np.log(p / p.shift(1)).dropna()
            rets_recent = rets_full.iloc[-40:] # 40-day DNA window
            
            dna_baseline = abs(differential_entropy(rets_full))
            dna_recent = abs(differential_entropy(rets_recent))
            
            # 2. THE DECAY RATE (Velocity of Chaos)
            decay_rate = dna_recent / dna_baseline if dna_baseline != 0 else 1.0
            
            # 3. Target Calibration
            target = p.min() + ((p.max() - p.min()) * self.alpha * (self.k / 100))
            asym = ((p.iloc[-1] - target) / target) * 100
            
            # 4. State Determination
            is_failing = decay_rate > self.decay_limit
            is_sovereign = dna_baseline < 1.0 # Absolute entropy threshold
            
            if is_failing:
                action = "DNA DECAY: TERMINAL"
                state = "FAIL"
            elif decay_rate < 0.90 and asym < 0:
                action = "BUY: GROWING"
                state = "SOV"
            elif asym > 50:
                action = "SELL: TANKING RISK"
                state = "RISK"
            elif decay_rate > 1.05:
                action = "IGNORE: UNSTABLE"
                state = "CON"
            else:
                action = "HOLD: NEUTRAL"
                state = "NEUT"

            results.append({
                "SECTOR": discovery_map[t],
                "TICKER": t,
                "ACTION": action,
                "STATE": state,
                "DECAY_RATE": round(decay_rate, 4),
                "ASYM_%": round(asym, 2),
                "PRICE": round(p.iloc[-1], 2),
                "DNA_BASE": round(dna_baseline, 4),
                "RANK": self.get_action_rank(action)
            })

        df = pd.DataFrame(results)
        
        print("=" * 90)
        for sector in sorted(df['SECTOR'].unique()):
            print(f"\n[ {sector} ]")
            sector_df = df[df['SECTOR'] == sector].sort_values(by=["RANK", "DECAY_RATE"])
            
            output_cols = ["TICKER", "ACTION", "STATE", "DECAY_RATE", "DNA_BASE", "ASYM_%", "PRICE"]
            print(sector_df[output_cols].to_string(index=False))

        print(f"\n[*] ANALYSIS COMPLETE: {len(results)} NODES PROCESSED.")

# ==============================================================================
# EXECUTION LAYER
# ==============================================================================
if __name__ == "__main__":
    if not os.path.exists("logs"): os.makedirs("logs")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file_path = f"logs/SOVE_Decay_Run_{timestamp}.log"

    sys.stdout = Logger(log_file_path)

    try:
        engine = SOVE_Precision_Engine()
        engine.run()
    except Exception as e:
        print(f"\n[!] CRITICAL ERROR: {str(e)}")
    finally:
        print("\n" + "="*90)
        print(f"[*] Log saved: {log_file_path}")
        input("[*] Press Enter to close...")
