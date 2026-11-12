#!/usr/bin/env python3
"""Connect MCP tools to the live VoiceVault PCB through KiCad's official IPC API."""
import math
import os
import hashlib
import json
import shutil
import uuid
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
    client = KiCad(socket_path='ipc://' + str(SOCKET), timeout_ms=30000)
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


@server.tool()
def accept_qualified_copper(qualification_path: str) -> dict:
    """Accept a hash-bound native-checked copper-only candidate and reload KiCad.

    Requires qualify_routing_candidate.py output inside the local study cache.
    Any unsaved editor change invalidates the source hash and aborts acceptance.
    Rules, footprints and net assignments are supplied by the qualifier's source
    board; this tool never imports a raw autorouter output or changes rules.
    """
    path=Path(qualification_path).resolve()
    path.relative_to((ROOT/'.lab-cache/hardware').resolve())
    assert path.name=='qualification.json','Expected native qualification record'
    record=json.loads(path.read_text())
    candidate=path.parent/BOARD_PATH.name
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert record['native_layout_violations']==0 and record['added_copper_items']>0
    assert record['laser_geometry_violations']==0,'Supplemental laser-via check required'
    assert record['accepted_net_groups'],'No accepted copper'
    assert not json.loads((path.parent/'drc.json').read_text())['violations']
    assert not json.loads((path.parent/'laser-geometry.json').read_text())['violations']
    assert digest(candidate)==record['candidate_sha256'],'Candidate changed'
    with write_lock:
        client,board=connected_board()
        board.save()
        assert digest(BOARD_PATH)==record['source_sha256'],'Source/editor changed; requalify'
        before=len(board.get_tracks())+len(board.get_vias())
        assert before+record['added_copper_items']==record['total_copper_items']
        backup=ROOT/'.lab-cache/hardware/rev-b-backups'/('copper-'+uuid.uuid4().hex)
        backup.mkdir(parents=True)
        shutil.copy2(BOARD_PATH,backup/BOARD_PATH.name)
        try:
            shutil.copy2(candidate,BOARD_PATH)
            board.revert()
            board=client.get_board()
            after=len(board.get_tracks())+len(board.get_vias())
            assert after==record['total_copper_items'],'Reload/count mismatch'
            assert digest(BOARD_PATH)==record['candidate_sha256']
        except BaseException:
            shutil.copy2(backup/BOARD_PATH.name,BOARD_PATH)
            client.get_board().revert()
            raise
    return dict(accepted=True,board=str(BOARD_PATH),before=before,after=after,
                source_sha256=record['source_sha256'],candidate_sha256=record['candidate_sha256'],
                accepted_net_groups=record['accepted_net_groups'],manufacturing_ready=False)


if __name__ == '__main__':
    server.run(transport='stdio')
