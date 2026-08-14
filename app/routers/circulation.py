import logging
from typing import Any, Dict, List
from fastapi import APIRouter, Query
from app.db.session import db

logger = logging.getLogger("routers.circulation")

router = APIRouter(tags=["Circulation & Loans"])

@router.get("/api/active-loans", summary="Get Active Loans")
async def get_active_loans(
    limit: int = Query(default=100, ge=1, le=500, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Record offset")
) -> List[Dict[str, Any]]:
    """Retrieve currently active loans (books checked out) from Koha issues table."""
    if not db.is_healthy():
        return []

    query = """
        SELECT i.issue_id, it.barcode, b.title, 
               COALESCE(bi.publicationyear, b.copyrightdate) as publication_year,
               p.firstname, p.surname, i.issuedate, i.date_due
        FROM issues i
        JOIN items it ON i.itemnumber = it.itemnumber
        JOIN biblio b ON it.biblionumber = b.biblionumber
        LEFT JOIN biblioitems bi ON b.biblionumber = bi.biblionumber
        JOIN borrowers p ON i.borrowernumber = p.borrowernumber
        ORDER BY i.issuedate DESC
        LIMIT %s OFFSET %s
    """
    try:
        results = await db.fetch_all(query, (limit, offset))
        return results if results else []
    except Exception as e:
        logger.error(f"Error fetching active loans: {e}")
        return []

@router.get("/api/recent-returns", summary="Get Recent Returns")
async def get_recent_returns(
    limit: int = Query(default=50, ge=1, le=500, description="Max returns to return")
) -> List[Dict[str, Any]]:
    """Retrieve recently returned books from Koha old_issues."""
    if not db.is_healthy():
        return []

    query = """
        SELECT oi.issue_id, it.barcode, b.title, 
               COALESCE(bi.publicationyear, b.copyrightdate) as publication_year,
               p.firstname, p.surname, oi.returndate
        FROM old_issues oi
        JOIN items it ON oi.itemnumber = it.itemnumber
        JOIN biblio b ON it.biblionumber = b.biblionumber
        LEFT JOIN biblioitems bi ON b.biblionumber = bi.biblionumber
        JOIN borrowers p ON oi.borrowernumber = p.borrowernumber
        ORDER BY oi.returndate DESC
        LIMIT %s
    """
    try:
        results = await db.fetch_all(query, (limit,))
        return results if results else []
    except Exception as e:
        logger.error(f"Error fetching recent returns: {e}")
        return []

@router.get("/api/stats", summary="System Stats")
async def get_stats() -> Dict[str, Any]:
    """Retrieve loan aggregate stats (active loans count, overdue count, system status)."""
    if not db.is_healthy():
        return {"active_loans": 0, "overdue": 0, "system_status": "Offline"}

    try:
        loans_count = await db.fetch_one("SELECT COUNT(*) as count FROM issues")
        overdue_count = await db.fetch_one("SELECT COUNT(*) as count FROM issues WHERE date_due < NOW()")
        return {
            "active_loans": loans_count['count'] if loans_count else 0,
            "overdue": overdue_count['count'] if overdue_count else 0,
            "system_status": "Online"
        }
    except Exception as e:
        logger.error(f"Stats query error: {e}")
        return {"active_loans": 0, "overdue": 0, "system_status": "Sync-Error"}

@router.get("/api/audit-logs", summary="Get Koha Action Logs")
async def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=200, description="Max audit logs")
) -> List[Dict[str, Any]]:
    """Retrieve Koha audit trail action logs from action_logs table."""
    if not db.is_healthy():
        return []

    query = """
        SELECT al.timestamp, 
               CONCAT(COALESCE(b.firstname, ''), ' ', COALESCE(b.surname, '')) as user_name,
               CASE 
                 WHEN b.categorycode = 'STAFF' THEN 'STAFF'
                 WHEN b.categorycode = 'S' THEN 'SUPER-USER'
                 ELSE 'STAFF' 
               END as user_type,
               al.action as type,
               al.info as action,
               al.module, al.object as object_id
        FROM action_logs al
        LEFT JOIN borrowers b ON al.user = b.borrowernumber
        ORDER BY al.timestamp DESC
        LIMIT %s
    """
    try:
        results = await db.fetch_all(query, (limit,))
        return results if results else []
    except Exception as e:
        logger.error(f"Audit Log Error: {e}")
        return []
