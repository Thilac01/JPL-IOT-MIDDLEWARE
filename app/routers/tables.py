import logging
from typing import Any, Dict, List, Union
from fastapi import APIRouter, HTTPException, Query, status
from app.core.config import settings
from app.db.session import db

logger = logging.getLogger("routers.tables")

router = APIRouter(tags=["Data Tables Discovery"])

@router.get("/api/tables", summary="List Database Tables")
async def get_tables_list() -> List[str]:
    """Retrieve list of all tables in the database with dynamic key detection."""
    if not db.is_healthy():
        if settings.SIMULATION_MODE or settings.AUTO_FALLBACK_SIMULATION:
            return ["biblio", "borrowers", "items", "issues", "old_issues", "action_logs", "branches"]
        return []

    try:
        results = await db.fetch_all("SHOW TABLES")
        if not results:
            return []

        sample_row = results[0]
        key = next((k for k in sample_row.keys() if k.startswith('Tables_in')), None)

        if key:
            return [row[key] for row in results]
        else:
            return [list(row.values())[0] for row in results]
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        return ["biblio", "borrowers", "items", "issues", "old_issues"]

@router.get("/api/table-data/{table_name}", summary="Fetch Table Data")
async def get_table_data(
    table_name: str,
    limit: int = Query(default=100, ge=1, le=500, description="Max rows to fetch"),
    offset: int = Query(default=0, ge=0, description="Row offset")
) -> Union[List[Dict[str, Any]], Dict[str, str]]:
    """Fetch paginated records from a specific table with SQL injection protection."""
    # Strict SQL identifier validation
    if not table_name.isidentifier() or ";" in table_name or "--" in table_name or " " in table_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid table identifier format"
        )

    if not db.is_healthy():
        if settings.SIMULATION_MODE or settings.AUTO_FALLBACK_SIMULATION:
            # Return mock records for simulated views
            if table_name == "biblio":
                return [
                    {"biblionumber": 1, "title": "Introduction to Algorithms, 4th Ed.", "author": "Thomas H. Cormen", "isbn": "9780262046305"},
                    {"biblionumber": 2, "title": "Design Patterns: Elements of Reusable Object-Oriented Software", "author": "Erich Gamma", "isbn": "9780201633610"}
                ]
            elif table_name == "borrowers":
                return [
                    {"borrowernumber": 1042, "cardnumber": "LIB-1042", "firstname": "Alice", "surname": "Walker", "categorycode": "STUDENT"},
                    {"borrowernumber": 1089, "cardnumber": "LIB-1089", "firstname": "Marcus", "surname": "Vance", "categorycode": "FACULTY"}
                ]
            elif table_name == "items":
                return [
                    {"itemnumber": 501, "biblionumber": 1, "barcode": "300184920", "holdingbranch": "MAIN"},
                    {"itemnumber": 502, "biblionumber": 2, "barcode": "300294101", "holdingbranch": "MAIN"}
                ]
        return []

    # Safe parameterized limit/offset query with backticked table name
    query = f"SELECT * FROM `{table_name}` LIMIT %s OFFSET %s"

    try:
        results = await db.fetch_all(query, (limit, offset))
        return results if results else []
    except Exception as e:
        logger.error(f"Error fetching data for table {table_name}: {e}")
        return []
