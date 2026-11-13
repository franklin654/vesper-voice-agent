import argparse, asyncio, base64, json, re, statistics, time
from pathlib import Path
import jiwer, soundfile as sf
from sarvamai import AsyncSarvamAI
from sarvamai.types import (RealtimeAudioInput, 
                            RealtimePing, 
                            RealtimeTranscriptFinal, 
                            RealtimeError)
from vesper.secrets import get_secret

FRAME, SAMPLE_RATE = 1280, 16000.0
norm = lambda s: re.sub(r"[^\w\s]", "", (s or "").lower()).strip()
b64 = lambda pcm: base64.b64encode(pcm).decode("utf-8")

def open_stream(client:AsyncSarvamAI):
    return client.speech_to_text_realtime_streaming.connect(
        language_code="auto", mode="translate",
        encoding="linear16", sample_rate=str(SAMPLE_RATE), silence_duration_ms="500"
    )

async def transcribe(client: AsyncSarvamAI, wav):
    audio, sr = sf.read(wav, dtype="int16")
    assert sr == SAMPLE_RATE
    marks, events = {}, []
    async with open_stream(client) as ws:
        t0 = time.perf_counter()

        async def sender():
            for i in range(0, len(audio), FRAME):
                await ws.send_realtime_audio_input(
                    RealtimeAudioInput(audio=b64(audio[i:i+FRAME].tobytes())))
                await asyncio.sleep(FRAME / SAMPLE_RATE)
            marks["audio_end"] = time.perf_counter()
            silence = b64(b"\x00\x00" * FRAME)
            for _ in range(25):
                await ws.send_realtime_audio_input(RealtimeAudioInput(audio=silence))
                await asyncio.sleep(FRAME / SAMPLE_RATE)

        async def pinger():
            while True:
                await asyncio.sleep(5)
                await ws.send_realtime_ping(RealtimePing())

        async def receiver():
            async for ev in ws:
                now = time.perf_counter()
                events.append((ev.event, round((now - t0) * 1000)))
                if ev.event == "vad.speech_start":
                    marks.setdefault("speech_start", now)
                elif ev.event == "vad.speech_end":
                    marks["speech_end"] = now
                elif ev.event == "transcript.final":
                    marks["final"] = now
                    return ev.text
            return None

        tasks = [asyncio.create_task(sender()), asyncio.create_task(pinger())]
        recv = asyncio.create_task(receiver())
        try:
            text = await asyncio.wait_for(recv, timeout=30)
        except asyncio.TimeoutError:
            text = None
        finally:
            for t in [*tasks, recv]:
                t.cancel()
            await asyncio.gather(*tasks, recv, return_exceptions=True)

    names = [e for e, _ in events]
    return {
        "text": text, "events": events,
        "order_ok": ("vad.speech_start" in names and "transcript.final" in names
                     and names.index("vad.speech_start") < names.index("transcript.final")),
        "final_after_speech_end_ms": round((marks["final"] - marks["speech_end"]) * 1000)
            if "final" in marks and "speech_end" in marks else None,
        "final_after_audio_end_ms": round((marks["final"] - marks["audio_end"]) * 1000)
            if "final" in marks and "audio_end" in marks else None,
    }

async def idle_test(client: AsyncSarvamAI, ping_every, limit_s=150):
    """How does an idle connection end? ping_every=None sends no ping"""
    async with open_stream(client) as ws:
        t0 = time.perf_counter()
        async def pinger():
            while ping_every:
                await asyncio.sleep(ping_every)
                await ws.send_realtime_ping(RealtimePing())
        ptask = asyncio.create_task(pinger())
        async def consume():
            async for _ in ws:
                pass
        try:
            await asyncio.wait_for(consume(), timeout=limit_s)
            ended = "stream ended"
        except asyncio.TimeoutError:
            ended = f"still open after {limit_s} s"
        except Exception as e:
            ended = repr(e)
        finally:
            ptask.cancel()
        return {"ping_every_s": ping_every, 
                "elapsed_s": round(time.perf_counter() - t0), 
                "ended": ended}

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default="thomas")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--idle-test", action="store_true")
    args = ap.parse_args()
    client = AsyncSarvamAI(api_subscription_key=get_secret("sarvam"))

    if args.idle_test:
        out = [await idle_test(client, None), await idle_test(client, 5)]
        Path("probes/results/sarvam_idle.json").write_text(json.dumps(out, indent=2))
        print(out)
        return

    rows = [json.loads(l) for l in Path("fixtures/manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = [r for r in rows if r["speaker"] == args.speaker][: args.limit]
    results = []
    for r in rows:                                                 # one connection per utterance, as in the design
        res = await transcribe(client, Path("fixtures") / r["file"])
        ref = r.get("expected_en") or r["text"]
        res.update(id=r["id"], lang=r["lang"], reference=ref,
                   wer=round(jiwer.wer(norm(ref), norm(res["text"])), 3) if res["text"] else None)
        results.append(res)

    def pct(vals, q):
        vals = sorted(v for v in vals if v is not None)
        return vals[min(len(vals) - 1, int(q * len(vals)))] if vals else None
    summary = {
        "n": len(results),
        "no_final": sum(r["text"] is None for r in results),
        "order_ok_rate": round(sum(r["order_ok"] for r in results) / len(results), 3),
        "final_after_speech_end_ms": {"p50": pct([r["final_after_speech_end_ms"] for r in results], .5),
                                      "p95": pct([r["final_after_speech_end_ms"] for r in results], .95)},
        "wer_en_median": statistics.median([r["wer"] for r in results if r["lang"] == "en" and r["wer"] is not None] or [0]),
        "wer_mixed_median": statistics.median([r["wer"] for r in results if r["lang"] != "en" and r["wer"] is not None] or [0]),
    }
    Path("probes/results/sarvam.json").write_text(json.dumps({"summary": summary, "rows": results}, ensure_ascii=False, indent=2))
    print(json.dumps(summary, indent=2))

asyncio.run(main())