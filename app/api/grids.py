import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import GridInstance, Account
from services.grid_service import GridService

logger = logging.getLogger(__name__)
router = APIRouter()
grid_service = GridService()


class GridCreate(BaseModel):
    name: str
    hub_url: str
    novnc_base_url: str = ""
    max_sessions: int = 1
    notes: str = ""


class GridUpdate(BaseModel):
    name: str = None
    hub_url: str = None
    novnc_base_url: str = None
    max_sessions: int = None
    notes: str = None
    status: str = None


@router.get("")
def list_grids(db: Session = Depends(get_db)):
    grids = db.query(GridInstance).order_by(GridInstance.id).all()
    return {"grids": [g.to_dict() for g in grids]}


@router.post("")
def create_grid(data: GridCreate, db: Session = Depends(get_db)):
    existing = db.query(GridInstance).filter(GridInstance.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Grid '{data.name}' already exists")
    grid = GridInstance(
        name=data.name,
        hub_url=data.hub_url,
        novnc_base_url=data.novnc_base_url or None,
        max_sessions=data.max_sessions,
        notes=data.notes,
        status="UNKNOWN",
    )
    db.add(grid)
    db.commit()
    db.refresh(grid)
    logger.info(f"Created grid {grid.id}: {data.name}")
    return {"grid": grid.to_dict()}


@router.get("/{grid_id}")
def get_grid(grid_id: int, db: Session = Depends(get_db)):
    grid = db.query(GridInstance).filter(GridInstance.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")
    return {"grid": grid.to_dict()}


@router.put("/{grid_id}")
def update_grid(grid_id: int, data: GridUpdate, db: Session = Depends(get_db)):
    grid = db.query(GridInstance).filter(GridInstance.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    if data.name is not None:
        existing = db.query(GridInstance).filter(
            GridInstance.name == data.name, GridInstance.id != grid_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Grid name '{data.name}' already exists")
        grid.name = data.name
    if data.hub_url is not None:
        grid.hub_url = data.hub_url
    if data.novnc_base_url is not None:
        grid.novnc_base_url = data.novnc_base_url or None
    if data.max_sessions is not None:
        grid.max_sessions = data.max_sessions
    if data.notes is not None:
        grid.notes = data.notes
    if data.status is not None:
        grid.status = data.status

    db.commit()
    db.refresh(grid)
    return {"grid": grid.to_dict()}


@router.delete("/{grid_id}")
def delete_grid(grid_id: int, db: Session = Depends(get_db)):
    grid = db.query(GridInstance).filter(GridInstance.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    # 不允许删除被账号引用的 grid
    account_count = db.query(Account).filter(Account.grid_id == grid_id).count()
    if account_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete grid: {account_count} account(s) are assigned to it. Reassign them first.",
        )

    db.delete(grid)
    db.commit()
    return {"status": "deleted"}


@router.post("/{grid_id}/check")
def check_grid(grid_id: int, db: Session = Depends(get_db)):
    """探测 Grid 实例可达性和健康状态，并更新 status 字段。"""
    grid = db.query(GridInstance).filter(GridInstance.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")

    result = GridService.probe(grid.hub_url)
    grid.status = result["status"]
    db.commit()

    return {
        "grid_id": grid_id,
        "name": grid.name,
        "hub_url": grid.hub_url,
        "status": grid.status,
        "nodes": result["nodes"],
        "ready": result["ready"],
    }


@router.post("/{grid_id}/capacity")
def check_grid_capacity(grid_id: int, db: Session = Depends(get_db)):
    """检查 Grid 容量：当前会话数 / 最大会话数。"""
    grid = db.query(GridInstance).filter(GridInstance.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")
    from api.sessions_v2 import _live_drivers
    cap = grid_service.check_capacity(grid, _live_drivers)
    return {"grid_id": grid_id, "name": grid.name, **cap}


@router.get("/{grid_id}/heartbeat")
def get_grid_heartbeat(grid_id: int, db: Session = Depends(get_db)):
    """获取节点心跳详情（含连续失败计数）。"""
    grid = db.query(GridInstance).filter(GridInstance.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")
    from services.node_heartbeat import heartbeat
    health = heartbeat.get_node_health(grid_id)
    if health is None:
        raise HTTPException(status_code=404, detail="Node health info not available")
    return health


@router.post("/{grid_id}/force-cleanup")
def force_cleanup_grid(grid_id: int, db: Session = Depends(get_db)):
    """紧急清理：强制删除 Grid 节点上所有活跃 session（仅管理员使用）。"""
    grid = db.query(GridInstance).filter(GridInstance.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grid not found")
    removed = GridService.force_cleanup_node(grid.hub_url)
    logger.warning(f"Force cleanup of grid '{grid.name}': removed {removed} session(s)")
    return {"grid_id": grid_id, "name": grid.name, "removed_sessions": removed}