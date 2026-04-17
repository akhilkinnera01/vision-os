"""Minimal MQTT publishing support for narrow trigger outputs."""

from __future__ import annotations

import socket


def publish_json(host: str, port: int, topic: str, payload: bytes, *, client_id: str = "vision-os") -> None:
    """Publish one QoS0 JSON payload to an MQTT broker without extra dependencies."""
    with socket.create_connection((host, port), timeout=2.0) as connection:
        connection.sendall(_connect_packet(client_id))
        connection.recv(4)
        connection.sendall(_publish_packet(topic, payload))
        connection.sendall(b"\xe0\x00")


def _connect_packet(client_id: str) -> bytes:
    client_bytes = client_id.encode("utf-8")
    variable_header = (
        b"\x00\x04MQTT"
        b"\x04"
        b"\x02"
        b"\x00\x3c"
    )
    payload = len(client_bytes).to_bytes(2, "big") + client_bytes
    remaining_length = len(variable_header) + len(payload)
    return b"\x10" + _encode_remaining_length(remaining_length) + variable_header + payload


def _publish_packet(topic: str, payload: bytes) -> bytes:
    topic_bytes = topic.encode("utf-8")
    variable_header = len(topic_bytes).to_bytes(2, "big") + topic_bytes
    remaining_length = len(variable_header) + len(payload)
    return b"\x30" + _encode_remaining_length(remaining_length) + variable_header + payload


def _encode_remaining_length(value: int) -> bytes:
    encoded = bytearray()
    while True:
        digit = value % 128
        value //= 128
        if value > 0:
            digit |= 0x80
        encoded.append(digit)
        if value == 0:
            break
    return bytes(encoded)
