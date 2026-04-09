"""Dashboard and analytics routes.

This module supports an optional MongoDB-backed store. If a `MONGODB_URI`
is configured (see backend `.env`), statistics and scan history will be
persisted to a `scans` collection. When no DB is configured the code falls
back to the original in-memory implementation to remain operational.
"""
from fastapi import APIRouter
import logging
from datetime import datetime
from uuid import uuid4
from models.schemas import DashboardStats
from services.mongo import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# In-memory stats storage (fallback when no DB configured)
_stats = {
    "total_scans": 0,
    "genuine_count": 0,
    "suspicious_count": 0,
    "fake_count": 0,
    "invalid_count": 0,
    "scan_history": [],
}


async def update_scan_stat(verdict: str, medicine_name: str, confidence: float):
    """Update statistics after a scan.

    If a MongoDB database is available, persist the scan document to the
    `scans` collection. Otherwise update the in-memory `_stats` structure.
    """
    try:
        db = get_db()
        verdict_value = (verdict or "INVALID").upper()
        valid_verdicts = {"GENUINE", "SUSPICIOUS", "FAKE", "INVALID"}
        if verdict_value not in valid_verdicts:
            verdict_value = "INVALID"

        if db is not None:
            scan_id = f"scan_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{uuid4().hex[:8]}"
            entry = {
                "scanId": scan_id,
                "medicine_name": medicine_name,
                "verdict": verdict_value,
                "confidence": float(confidence),
                "timestamp": datetime.utcnow(),
            }
            try:
                await db.scans.insert_one(entry)
                logger.debug("Recorded scan in MongoDB scans collection")
                return
            except Exception as e:
                logger.error(f"Failed to write scan to DB: {e}")

        # Fallback to in-memory
        _stats["total_scans"] += 1

        if verdict_value == "GENUINE":
            _stats["genuine_count"] += 1
        elif verdict_value == "SUSPICIOUS":
            _stats["suspicious_count"] += 1
        elif verdict_value == "FAKE":
            _stats["fake_count"] += 1
        elif verdict_value == "INVALID":
            _stats["invalid_count"] += 1

        _stats["scan_history"].append({
            "medicine_name": medicine_name,
            "verdict": verdict_value,
            "confidence": float(confidence),
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Keep last 100 scans
        if len(_stats["scan_history"]) > 100:
            _stats["scan_history"] = _stats["scan_history"][-100:]

    except Exception as e:
        logger.error(f"update_scan_stat error: {e}")


@router.get("/stats")
async def get_stats():
    """Get dashboard statistics.

    Returns counts and average confidence. When MongoDB is configured the
    values are derived from the `scans` collection; otherwise they are from
    the in-memory store.
    """
    try:
        db = get_db()
        if db is not None:
            valid_filter = {"verdict": {"$in": ["GENUINE", "SUSPICIOUS", "FAKE", "INVALID"]}}
            total = await db.scans.count_documents(valid_filter)
            genuine_count = await db.scans.count_documents({"verdict": "GENUINE"})
            suspicious_count = await db.scans.count_documents({"verdict": "SUSPICIOUS"})
            fake_count = await db.scans.count_documents({"verdict": "FAKE"})
            invalid_count = await db.scans.count_documents({"verdict": "INVALID"})

            pipeline = [
                {"$match": valid_filter},
                {"$group": {"_id": None, "avg": {"$avg": "$confidence"}}}
            ]
            res = await db.scans.aggregate(pipeline).to_list(length=1)
            avg_confidence = float(res[0]["avg"]) if res else 0.0

            stats = DashboardStats(
                total_scans=total,
                genuine_count=genuine_count,
                suspicious_count=suspicious_count,
                fake_count=fake_count,
                invalid_count=invalid_count,
                average_confidence=avg_confidence,
            )

            logger.info(f"Dashboard stats (db) retrieved. Total scans: {total}")
            return stats.dict()

        # Fallback to in-memory
        total = _stats["total_scans"]
        avg_confidence = 0
        if _stats["scan_history"]:
            avg_confidence = sum(s["confidence"] for s in _stats["scan_history"]) / len(_stats["scan_history"])

        stats = DashboardStats(
            total_scans=total,
            genuine_count=_stats["genuine_count"],
            suspicious_count=_stats["suspicious_count"],
            fake_count=_stats["fake_count"],
            invalid_count=_stats["invalid_count"],
            average_confidence=avg_confidence,
        )

        logger.info(f"Dashboard stats (memory) retrieved. Total scans: {total}")
        return stats.dict()

    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        return {
            "total_scans": 0,
            "genuine_count": 0,
            "suspicious_count": 0,
            "fake_count": 0,
            "invalid_count": 0,
            "average_confidence": 0.0,
        }


@router.get("/history")
async def get_scan_history(limit: int = 20):
    """Get recent scan history. Returns newest entries first."""
    try:
        db = get_db()
        if db is not None:
            valid_filter = {"verdict": {"$in": ["GENUINE", "SUSPICIOUS", "FAKE", "INVALID"]}}
            total = await db.scans.count_documents(valid_filter)
            rows = await db.scans.find(valid_filter).sort("timestamp", -1).to_list(length=limit)
            recent = []
            for r in rows:
                timestamp = r.get("timestamp")
                recent.append({
                    "medicine_name": r.get("medicine_name"),
                    "verdict": r.get("verdict"),
                    "confidence": float(r.get("confidence", 0)),
                    "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp) if timestamp is not None else None,
                })
            return {"total": total, "recent": recent}

        # Fallback to in-memory
        history = _stats["scan_history"][-limit:]
        return {"total": len(_stats["scan_history"]), "recent": history[::-1]}

    except Exception as e:
        logger.error(f"History retrieval error: {e}")
        return {"total": 0, "recent": []}


@router.post("/record-scan")
async def record_scan(verdict: str, medicine_name: str, confidence: float):
    """Record a new scan for statistics. This is also used internally."""
    try:
        await update_scan_stat(verdict, medicine_name, confidence)
        logger.info(f"Scan recorded: {medicine_name} -> {verdict}")
        return {"status": "recorded"}

    except Exception as e:
        logger.error(f"Record scan error: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/verdict-breakdown")
async def get_verdict_breakdown():
    """Get breakdown of scans by verdict (percentages)."""
    try:
        db = get_db()
        if db is not None:
            valid_filter = {"verdict": {"$in": ["GENUINE", "SUSPICIOUS", "FAKE", "INVALID"]}}
            total = await db.scans.count_documents(valid_filter)
            if total == 0:
                return {"genuine_percent": 0, "suspicious_percent": 0, "fake_percent": 0, "invalid_percent": 0}

            genuine = await db.scans.count_documents({"verdict": "GENUINE"})
            suspicious = await db.scans.count_documents({"verdict": "SUSPICIOUS"})
            fake = await db.scans.count_documents({"verdict": "FAKE"})
            invalid = await db.scans.count_documents({"verdict": "INVALID"})

            return {
                "genuine_percent": round((genuine / total) * 100, 1),
                "suspicious_percent": round((suspicious / total) * 100, 1),
                "fake_percent": round((fake / total) * 100, 1),
                "invalid_percent": round((invalid / total) * 100, 1),
                "total_scans": total,
            }

        # Fallback to in-memory
        total = _stats["total_scans"]
        if total == 0:
            return {"genuine_percent": 0, "suspicious_percent": 0, "fake_percent": 0, "invalid_percent": 0}

        return {
            "genuine_percent": round((_stats["genuine_count"] / total) * 100, 1),
            "suspicious_percent": round((_stats["suspicious_count"] / total) * 100, 1),
            "fake_percent": round((_stats["fake_count"] / total) * 100, 1),
            "invalid_percent": round((_stats["invalid_count"] / total) * 100, 1),
            "total_scans": total,
        }

    except Exception as e:
        logger.error(f"Verdict breakdown error: {e}")
        return {"error": str(e)}
