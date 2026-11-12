#!/usr/bin/env python3
"""Connect MCP tools to the live VoiceVault PCB through KiCad's official IPC API."""
import math
import os
from pathlib import Path
from threading import RLock

from kipy import KiCad
from kipy.geometry import Vector2
from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[2]
BOARD_PATH = Path(os.environ.get('VOICEVAULT_KICAD_BOARD', ROOT / 'hardware/rev-b/voicevault-standalone-b0.kicad_pcb')).resolve()
SOCKET = Path.home() / '.var/app/org.kicad.KiCad/cache/vv-pcb/kicad/api.sock'
server = FastMCP('voicevault-kicad')
write_lock = RLock()


def connected_board():
    client = KiCad(socket_path='ipc://' + str(SOCKET), timeout_ms=3000)
    board = client.get_board()
    actual = (Path(board.document.project.path) / board.name).resolve()
    if actual != BOARD_PATH:
        raise RuntimeError(f'Open PCB is {actual}. Expected {BOARD_PATH}.')
    return client, board


def footprint_info(footprint):
    return dict(reference=footprint.reference_field.text.value,
                value=footprint.value_field.text.value,
                x_mm=footprint.position.x / 1_000_000,
                y_mm=footprint.position.y / 1_000_000,
                rotation_degrees=footprint.orientation.degrees)


@server.tool()
def get_status() -> dict:
    """Check the live KiCad connection and identify the open VoiceVault PCB."""
    client, board = connected_board()
    return dict(connected=True, backend='KiCad IPC', version=str(client.get_version()),
                board=str(BOARD_PATH), footprints=len(board.get_footprints()),
                nets=len([net for net in board.get_nets() if net.name]))


@server.tool()
def list_footprints() -> list[dict]:
    """Read references, values and current positions from the open PCB editor."""
    _, board = connected_board()
    return [footprint_info(footprint) for footprint in board.get_footprints()]


@server.tool()
def list_nets() -> list[dict]:
    """Read the named electrical nets from the open PCB editor."""
    _, board = connected_board()
    return [dict(name=net.name) for net in board.get_nets() if net.name]


@server.tool()
def move_footprint(reference: str, x_mm: float, y_mm: float) -> dict:
    """Move one footprint to an absolute position in millimeters with a KiCad undo commit."""
    if not math.isfinite(x_mm) or not math.isfinite(y_mm):
        raise ValueError('Coordinates must be finite.')
    with write_lock:
        _, board = connected_board()
        matches = [item for item in board.get_footprints() if item.reference_field.text.value == reference]
        if len(matches) != 1:
            raise ValueError('The reference must identify exactly one footprint.')
        footprint = matches[0]
        before = footprint_info(footprint)
        commit = board.begin_commit()
        try:
            footprint.position = Vector2.from_xy_mm(x_mm, y_mm)
            board.update_items(footprint)
            board.push_commit(commit, 'VoiceVault move ' + reference)
        except Exception:
            board.drop_commit(commit)
            raise
        current = next(item for item in board.get_footprints() if item.reference_field.text.value == reference)
        return dict(before=before, after=footprint_info(current))


@server.tool()
def save_board() -> dict:
    """Save the current VoiceVault PCB through the running editor."""
    with write_lock:
        _, board = connected_board()
        board.save()
    return dict(saved=True, board=str(BOARD_PATH))


if __name__ == '__main__':
    server.run(transport='stdio')
