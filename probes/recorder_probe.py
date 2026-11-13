import json, statistics, time
from pvrecorder import PvRecorder

print("devices:", PvRecorder.get_available_devices())
runs = []
for _ in range(5):
    rec = PvRecorder(frame_length=1280, device_index=-1)
    rec.start()
    time.sleep(1.5)
    durs = []
    for _ in range(40):
        t0 = time.perf_counter()
        rec.read()
        durs.append((time.perf_counter() - t0) * 1000)
    
    rec.stop(); rec.delete()
    runs.append(durs)
    print([round(d) for d in durs])

backlog = [d for r in runs for d in r[:12]]
live = [d for r in runs for d in r[-12:]]

result = {
    "backlog_max_ms": round(max(backlog), 1),
    "live_min_ms": round(min(live), 1),
    "suggested_caught_up_ms": round((max(backlog) + min(live)) / 2, 1),
}
print(result)
json.dump(result, open("probes/results/recorder.json", "w"), indent=2)