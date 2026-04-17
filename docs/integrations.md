# Integrations

Vision OS can publish structured runtime outputs to external systems without
forcing every workflow through the trigger engine.

## Supported sources

Integration targets can subscribe to:

- `trigger`: deduped trigger firings derived from trigger action records
- `event`: runtime events emitted by the event layer
- `status`: periodic status snapshots from the live runtime state
- `session_summary`: end-of-run analytics summaries

## Supported target types

- `stdout`
- `file_append`
- `log`
- `webhook`
- `mqtt_publish`

Dispatch failures stay non-fatal. The runtime records them as structured dispatch
records and logs instead of aborting the run loop.

## Example config

```yaml
integrations:
  - id: focus-trigger-log
    type: log
    source: trigger
    trigger_ids:
      - sustained-focus-log
    event: integration_dispatch

  - id: distraction-events
    type: file_append
    source: event
    event_types:
      - distraction_started
      - distraction_resolved
    path: out/distraction-events.jsonl

  - id: room-status
    type: webhook
    source: status
    interval_seconds: 10
    method: PATCH
    url: https://example.invalid/room-status

  - id: session-summary
    type: mqtt_publish
    source: session_summary
    host: 127.0.0.1
    port: 1883
    topic: visionos/session-summary
```

## CLI usage

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --trigger-file demo/sample-triggers.yaml \
  --integrations-file demo/sample-integrations.yaml \
  --history-output out/history.jsonl \
  --session-summary-output out/session-summary.json \
  --headless
```

## Saved config usage

Runtime config manifests now support:

```yaml
integrations_file: visionos.integrations.yaml
```

Easy Setup starter bundles create a stub `visionos.integrations.yaml` file next
to the generated config, but leave it disabled in the manifest until you choose
to enable it.
