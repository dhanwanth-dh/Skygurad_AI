"""Verify SkyGuard Historical & Continuous Training API Endpoints."""

import urllib.request
import json
import time

BASE_URL = "http://localhost:8000"

def test_endpoint(name, url, method="GET", payload=None):
    print(f"\n--- Testing: {name} ({method} {url}) ---")
    try:
        req = urllib.request.Request(url, method=method)
        if payload:
            req.add_header("Content-Type", "application/json")
            data = json.dumps(payload).encode("utf-8")
        else:
            data = None
        
        with urllib.request.urlopen(req, data=data, timeout=15) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                body = json.loads(resp.read().decode("utf-8"))
                print(f"[SUCCESS] Status {status} | JSON response:")
                print(json.dumps(body, indent=2)[:500] + ("..." if len(str(body)) > 500 else ""))
                return body
            else:
                raw = resp.read()
                print(f"[SUCCESS] Status {status} | Content-Type: {content_type} | Bytes: {len(raw):,}")
                return raw
    except Exception as e:
        print(f"[FAILED] {e}")
        return None

if __name__ == "__main__":
    print("Verifying SkyGuard Historical & Continuous Training Platform...")
    
    # 1. Historical DB Status
    st = test_endpoint("Historical DB Status", f"{BASE_URL}/historical/status")
    
    # 2. Stations (1,152 IMD Stations)
    stations_data = test_endpoint("Stations List", f"{BASE_URL}/stations")
    if stations_data and stations_data.get("stations"):
        sample_id = stations_data["stations"][0]["station_id"]
        sample_name = stations_data["stations"][0].get("station_name", sample_id)
        print(f"\nSample station: {sample_name} ({sample_id})")
        
        # 3. Adaptive History for Sample Station
        test_endpoint(f"Adaptive History for {sample_id}", f"{BASE_URL}/historical/stations/{sample_id}?max_points=50")
    
    # 4. Historical Export (XLSX)
    test_endpoint("Export Historical Excel", f"{BASE_URL}/historical/export?format=xlsx")
    
    # 5. Historical Export (CSV)
    test_endpoint("Export Historical CSV", f"{BASE_URL}/historical/export?format=csv")
    
    # 6. Continuous Training Status
    test_endpoint("Training Status", f"{BASE_URL}/training/status")
    
    # 7. Trigger Continuous Training
    t_start = test_endpoint("Trigger Training", f"{BASE_URL}/training/start", method="POST", payload={"train_ratio": 0.70, "val_ratio": 0.15})
    if t_start and "training_id" in t_start:
        tid = t_start["training_id"]
        print(f"\nPolling Training Status for Job: {tid}...")
        for _ in range(5):
            time.sleep(2)
            t_stat = test_endpoint("Poll Training Job", f"{BASE_URL}/training/status?training_id={tid}")
            if t_stat and t_stat.get("status") in ["COMPLETED", "FAILED"]:
                break
