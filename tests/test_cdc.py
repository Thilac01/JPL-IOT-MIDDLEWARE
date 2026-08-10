import decimal
import datetime
from app.services.cdc_engine import CDCEngine

def test_cdc_serialization():
    cdc = CDCEngine(broadcast_callback=lambda x: None)
    
    raw_data = {
        "issue_id": 1001,
        "price": decimal.Decimal("24.95"),
        "created_at": datetime.datetime(2026, 8, 10, 14, 30, 0),
        "due_date": datetime.date(2026, 8, 24),
        "raw_bytes": b"RFID_PAYLOAD",
        "tags": {"fiction", "bestseller"},
        "none_val": None
    }
    
    serialized = cdc._serialize_data(raw_data)
    assert serialized["issue_id"] == 1001
    assert serialized["price"] == 24.95
    assert serialized["created_at"] == "2026-08-10T14:30:00"
    assert serialized["due_date"] == "2026-08-24"
    assert serialized["raw_bytes"] == "RFID_PAYLOAD"
    assert isinstance(serialized["tags"], list)
    assert serialized["none_val"] is None

def test_cdc_alert_builder_checkout():
    cdc = CDCEngine(broadcast_callback=lambda x: None)
    alert = cdc._build_circulation_alert(
        table="issues",
        event_type="INSERT",
        data={"barcode": "300184920", "borrowernumber": 1042, "date_due": "2026-08-24"}
    )
    assert alert is not None
    assert alert["level"] == "success"
    assert "Checked Out" in alert["title"]
    assert "300184920" in alert["msg"]

def test_cdc_alert_builder_return():
    cdc = CDCEngine(broadcast_callback=lambda x: None)
    alert = cdc._build_circulation_alert(
        table="old_issues",
        event_type="INSERT",
        data={"barcode": "300184920", "borrowernumber": 1042}
    )
    assert alert is not None
    assert alert["level"] == "info"
    assert "Returned" in alert["title"]
