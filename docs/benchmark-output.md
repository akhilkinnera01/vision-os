# Benchmark Output

Vision OS can emit benchmark results to a JSON file with `--benchmark-output`.

If you also need the semantic timeline and session-level rollups, see
[`session-history.md`](session-history.md).

## Fields

- `frames_processed`: number of inference steps completed
- `fps`: average processed frames per second over the run
- `average_inference_ms`: mean detector-plus-reasoning latency
- `dropped_frames`: frames discarded by the live webcam queue
- `decision_switch_rate`: label switches per second across the run
- `scene_stability_score`: last computed stability score from the temporal model
- `stage_timings`: per-stage average milliseconds across the run

## Example

```json
{
  "frames_processed": 180,
  "fps": 14.2,
  "average_inference_ms": 61.4,
  "dropped_frames": 7,
  "decision_switch_rate": 0.18,
  "scene_stability_score": 0.81,
  "stage_timings": {
    "detect": 41.7,
    "track": 1.4,
    "feature": 0.8,
    "actor_state": 0.4,
    "temporal": 0.3,
    "context": 0.2,
    "decision": 0.1,
    "event": 0.1,
    "explain": 0.4
  }
}
```
