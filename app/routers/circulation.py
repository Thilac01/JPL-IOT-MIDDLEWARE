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
    """Retrieve loan aggregate stats (active loans, checkouts breakdown, returns breakdown, overdue count, system status)."""
    default_stats = {
        "active_loans": 0,
        "overdue": 0,
        "checkout_30_days": 0,
        "checkout_7_days": 0,
        "checkout_today": 0,
        "returns_30_days": 0,
        "returns_7_days": 0,
        "returns_today": 0,
        "past_due_date": 0,
        "due_today": 0,
        "system_status": "Offline"
    }
    if not db.is_healthy():
        return default_stats

    query = """
        SELECT
            (SELECT COUNT(*) FROM issues) as active_loans,
            (SELECT COUNT(*) FROM issues WHERE date_due < NOW()) as overdue,
            (SELECT (SELECT COUNT(*) FROM issues WHERE issuedate >= DATE_SUB(NOW(), INTERVAL 30 DAY)) + 
                    (SELECT COUNT(*) FROM old_issues WHERE issuedate >= DATE_SUB(NOW(), INTERVAL 30 DAY))) as checkout_30_days,
            (SELECT (SELECT COUNT(*) FROM issues WHERE issuedate >= DATE_SUB(NOW(), INTERVAL 7 DAY)) + 
                    (SELECT COUNT(*) FROM old_issues WHERE issuedate >= DATE_SUB(NOW(), INTERVAL 7 DAY))) as checkout_7_days,
            (SELECT (SELECT COUNT(*) FROM issues WHERE DATE(issuedate) = CURDATE()) + 
                    (SELECT COUNT(*) FROM old_issues WHERE DATE(issuedate) = CURDATE())) as checkout_today,
            (SELECT COUNT(*) FROM old_issues WHERE returndate >= DATE_SUB(NOW(), INTERVAL 30 DAY)) as returns_30_days,
            (SELECT COUNT(*) FROM old_issues WHERE returndate >= DATE_SUB(NOW(), INTERVAL 7 DAY)) as returns_7_days,
            (SELECT COUNT(*) FROM old_issues WHERE DATE(returndate) = CURDATE()) as returns_today,
            (SELECT COUNT(*) FROM issues WHERE date_due < NOW()) as past_due_date,
            (SELECT COUNT(*) FROM issues WHERE DATE(date_due) = CURDATE()) as due_today
    """
    try:
        row = await db.fetch_one(query)
        if row:
            return {
                "active_loans": row.get("active_loans", 0) or 0,
                "overdue": row.get("overdue", 0) or 0,
                "checkout_30_days": row.get("checkout_30_days", 0) or 0,
                "checkout_7_days": row.get("checkout_7_days", 0) or 0,
                "checkout_today": row.get("checkout_today", 0) or 0,
                "returns_30_days": row.get("returns_30_days", 0) or 0,
                "returns_7_days": row.get("returns_7_days", 0) or 0,
                "returns_today": row.get("returns_today", 0) or 0,
                "past_due_date": row.get("past_due_date", 0) or 0,
                "due_today": row.get("due_today", 0) or 0,
                "system_status": "Online"
            }
        return {**default_stats, "system_status": "Online"}
    except Exception as e:
        logger.error(f"Stats query error: {e}")
        return {**default_stats, "system_status": "Sync-Error"}

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
