# Benchmark Output

Vision OS can emit benchmark results to a JSON file with `--benchmark-output`.

## Fields

- `frames_processed`: number of inference steps completed
- `fps`: average processed frames per second over the run
- `average_inference_ms`: mean detector-plus-reasoning latency
- `dropped_frames`: frames discarded by the live webcam queue
- `decision_switch_rate`: label switches per second across the run

## Example

```json
{
  "frames_processed": 180,
  "fps": 14.2,
  "average_inference_ms": 61.4,
  "dropped_frames": 7,
  "decision_switch_rate": 0.18
}
```
