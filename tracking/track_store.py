"""Storage for live tracks and ID allocation."""

from __future__ import annotations

from common.models import Track
from common.policy import TrackingPolicy


class TrackStore:
    """Keep active tracks small, explicit, and easy to prune."""

    def __init__(self, policy: TrackingPolicy) -> None:
        self.policy = policy
        self._next_track_id = 1
        self._tracks: dict[int, Track] = {}

    def active_tracks(self, timestamp: float) -> list[Track]:
        self.prune(timestamp)
        return list(self._tracks.values())

    def prune(self, timestamp: float) -> list[int]:
        expired = [
            track_id
            for track_id, track in self._tracks.items()
            if timestamp - track.last_seen_timestamp > self.policy.max_idle_seconds
        ]
        for track_id in expired:
            self._tracks.pop(track_id, None)
        return expired

    def create(self, label: str, bbox, confidence: float, timestamp: float) -> Track:
        track = Track(
            track_id=self._next_track_id,
            label=label,
            bbox=bbox,
            confidence=confidence,
            first_seen_timestamp=timestamp,
            last_seen_timestamp=timestamp,
        )
        self._tracks[track.track_id] = track
        self._next_track_id += 1
        return track

    def upsert(self, track_id: int, label: str, bbox, confidence: float, timestamp: float) -> Track:
        existing = self._tracks.get(track_id)
        track = Track(
            track_id=track_id,
            label=label,
            bbox=bbox,
            confidence=confidence,
            first_seen_timestamp=existing.first_seen_timestamp if existing else timestamp,
            last_seen_timestamp=timestamp,
        )
        self._tracks[track_id] = track
        self._next_track_id = max(self._next_track_id, track_id + 1)
        return track
