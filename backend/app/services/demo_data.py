from datetime import datetime, timezone

def dashboard_snapshot():
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kpis": {"orders_today": 1284, "inventory_value": 18420000, "at_risk_orders": 37, "supplier_risk": 12},
        "trend": [
            {"day": "Mon", "orders": 980, "late": 22},
            {"day": "Tue", "orders": 1120, "late": 19},
            {"day": "Wed", "orders": 1088, "late": 27},
            {"day": "Thu", "orders": 1240, "late": 18},
            {"day": "Fri", "orders": 1284, "late": 31},
        ],
        "data_mode": "illustrative_demo_data",
    }
