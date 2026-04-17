# Session History and Analytics

Vision OS can export two history-oriented artifacts:

- `--history-output PATH` writes one JSONL record per stable runtime result
- `--session-summary-output PATH` writes one JSON summary for the whole run

These files are meant to complement replay artifacts:

- replay JSONL is best when you want to re-run reasoning without live capture
- history JSONL is best when you want analytics-friendly records
- session summary JSON is best when you want one compact report per run

## History record fields

Each line in the history JSONL contains a `HistoryRecord` object.

Core fields:

- `frame_index`
- `timestamp`
- `scene_label`
- `confidence`
- `action`
- `risk_flags`

Analytics-friendly metrics:

- `focus_score`
- `distraction_score`
- `collaboration_score`
- `stability_score`
- `focus_duration_seconds`
- `decision_switch_rate`
- `average_inference_ms`
- `fps`
- `dropped_frames`

Timeline helpers:

- `event_types`
- `trigger_ids`
- `zone_labels`
- `stage_timings`

Example:

```json
{
  "frame_index": 7,
  "timestamp": 0.583,
  "scene_label": "Casual Use",
  "confidence": 0.5,
  "action": "Stay in passive observation mode",
  "event_types": [],
  "zone_labels": {
    "desk_a": "empty",
    "desk_b": "empty"
  }
}
```

## Session summary fields

The session summary is a `SessionAnalyticsSummary` object.

Key fields:

- `started_at`
- `ended_at`
- `duration_seconds`
- `frames_processed`
- `fps`
- `average_inference_ms`
- `dropped_frames`
- `dominant_scene_label`
- `decision_switch_count`
- `decision_switch_rate`
- `average_stability_score`
- `focus_duration_seconds`
- `group_activity_duration_seconds`
- `casual_use_duration_seconds`
- `event_counts`
- `label_durations`
- `stage_timings`

## Recommended uses

Use history JSONL when you need:

- post-run dashboards
- label transition inspection
- event-count rollups
- replay-adjacent analytics with lower storage cost than raw frames

Use the session summary JSON when you need:

- one artifact per CI smoke run
- one report per recorded session
- quick comparisons across policies, profiles, or camera placements
