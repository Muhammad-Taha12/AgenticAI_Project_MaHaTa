"""Reworked module for backend.api.events.py"""
from __future__ import annotations
from backend.runtime.ledger import RunLedger
from typing import AsyncIterator
import asyncio
import json

async def emit_job_updates(task_id: str, store: RunLedger) -> AsyncIterator[str]:
    last_stamp = None
    while True:
        snapshot = store.get(task_id)
        if snapshot is None:
            yield 'event: error\ndata: {"message":"Job not found"}\n\n'
            break
        stamp = snapshot.get('updated_at')
        if stamp != last_stamp:
            last_stamp = stamp
            yield f'data: {json.dumps(snapshot)}\n\n'
        if snapshot.get('status') in {'completed', 'failed'}:
            break
        await asyncio.sleep(1)
