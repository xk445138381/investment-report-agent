"""Template management API endpoints."""

import json
from uuid import uuid4
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["template"])

_templates: dict = {}


@router.get("/template")
async def list_templates():
    return {"templates": list(_templates.values()), "count": len(_templates)}


@router.post("/template", status_code=201)
async def create_template(template: dict):
    tid = str(uuid4())
    _templates[tid] = {"id": tid, **template}
    return {"template_id": tid}


@router.get("/template/{template_id}")
async def get_template(template_id: str):
    t = _templates.get(template_id)
    if not t:
        raise HTTPException(404, "Template not found")
    return t


@router.delete("/template/{template_id}")
async def delete_template(template_id: str):
    if template_id not in _templates:
        raise HTTPException(404, "Template not found")
    del _templates[template_id]
    return {"deleted": True}
