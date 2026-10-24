"""
Real Operational Risk Intelligence Engine.
Computes explainable, deterministic risk scores and categories from live database records:
- Low-stock and stockout risk (inventory vs safety stock and reorder point)
- Supplier SLA and lead-time vulnerability
- Order delay and fulfillment bottlenecks
- Inter-facility inventory imbalances
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.inventory import Inventory
from app.models.order import Order
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.warehouse import Warehouse
from app.schemas.risk import RiskItem


async def detect_operational_risks(session: AsyncSession) -> list[RiskItem]:
    """
    Evaluates real operational database state across inventory, orders, and suppliers.
    Returns prioritized explainable risk signals.
    """
    now = datetime.now(timezone.utc)
    risks: list[RiskItem] = []

    # 1. Stockout & Low-Stock Risk per Inventory Balance
    inv_stmt = (
        select(Inventory)
        .join(Product, Inventory.product_id == Product.id)
        .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
        .options(selectinload(Inventory.product), selectinload(Inventory.warehouse))
        .where(Product.is_active == True, Warehouse.is_active == True)
    )
    inv_results = (await session.execute(inv_stmt)).scalars().all()

    # Group inventories by product for multi-facility imbalance detection
    product_inv_map: dict[uuid.UUID, list[Inventory]] = {}
    for inv in inv_results:
        product_inv_map.setdefault(inv.product_id, []).append(inv)

        prod = inv.product
        wh = inv.warehouse
        avail = inv.available_quantity
        safety = prod.safety_stock if prod else 5
        reorder = inv.reorder_quantity

        if avail <= 0:
            score = 100
            severity = "CRITICAL"
            explanation = (
                f"Stockout detected for '{prod.name}' ({prod.sku}) at facility {wh.code} ({wh.name}). "
                f"Available stock is {avail} (on-hand: {inv.quantity_on_hand}, reserved: {inv.quantity_reserved})."
            )
            suggested_action = (
                f"Immediately issue purchase order or execute emergency inventory transfer to {wh.code}."
            )
            rules = [f"available_stock ({avail}) <= 0", "complete_fulfillment_blockage"]
            risks.append(
                RiskItem(
                    id=f"RISK-STOCKOUT-{prod.id}-{wh.id}",
                    category="STOCKOUT_RISK",
                    severity=severity,
                    score=score,
                    entity_type="product",
                    entity_id=str(prod.id),
                    entity_name=f"{prod.sku} ({prod.name}) @ {wh.code}",
                    rules_triggered=rules,
                    metrics={
                        "product_id": str(prod.id),
                        "warehouse_id": str(wh.id),
                        "available_quantity": avail,
                        "quantity_on_hand": inv.quantity_on_hand,
                        "quantity_reserved": inv.quantity_reserved,
                        "safety_stock": safety,
                        "reorder_threshold": reorder,
                    },
                    explanation=explanation,
                    suggested_action=suggested_action,
                    calculated_at=now,
                    source="deterministic_rules",
                )
            )
        elif avail <= safety:
            score = 85
            severity = "CRITICAL"
            explanation = (
                f"Safety buffer breached for '{prod.name}' ({prod.sku}) at facility {wh.code}. "
                f"Available inventory ({avail} units) is at or below safety stock threshold ({safety} units)."
            )
            suggested_action = f"Expedite inbound replenishment to {wh.code} and restrict non-essential allocations."
            rules = [f"available_stock ({avail}) <= safety_stock ({safety})", "buffer_exhaustion"]
            risks.append(
                RiskItem(
                    id=f"RISK-SAFETY-{prod.id}-{wh.id}",
                    category="STOCKOUT_RISK",
                    severity=severity,
                    score=score,
                    entity_type="product",
                    entity_id=str(prod.id),
                    entity_name=f"{prod.sku} ({prod.name}) @ {wh.code}",
                    rules_triggered=rules,
                    metrics={
                        "product_id": str(prod.id),
                        "warehouse_id": str(wh.id),
                        "available_quantity": avail,
                        "safety_stock": safety,
                        "reorder_threshold": reorder,
                    },
                    explanation=explanation,
                    suggested_action=suggested_action,
                    calculated_at=now,
                    source="deterministic_rules",
                )
            )
        elif avail <= reorder:
            deficit_pct = max(0.0, 1.0 - (avail / max(reorder, 1)))
            score = min(80, int(60 + deficit_pct * 20))
            severity = "HIGH"
            explanation = (
                f"Inventory reorder threshold crossed for '{prod.name}' ({prod.sku}) at facility {wh.code}. "
                f"Available inventory ({avail} units) is below configured reorder point ({reorder} units)."
            )
            suggested_action = f"Initiate replenishment purchase order for '{prod.name}'."
            rules = [f"available_stock ({avail}) <= reorder_level ({reorder})"]
            risks.append(
                RiskItem(
                    id=f"RISK-REORDER-{prod.id}-{wh.id}",
                    category="STOCKOUT_RISK",
                    severity=severity,
                    score=score,
                    entity_type="product",
                    entity_id=str(prod.id),
                    entity_name=f"{prod.sku} ({prod.name}) @ {wh.code}",
                    rules_triggered=rules,
                    metrics={
                        "product_id": str(prod.id),
                        "warehouse_id": str(wh.id),
                        "available_quantity": avail,
                        "reorder_threshold": reorder,
                    },
                    explanation=explanation,
                    suggested_action=suggested_action,
                    calculated_at=now,
                    source="deterministic_rules",
                )
            )

    # 2. Inter-Facility Inventory Imbalance
    for prod_id, inv_list in product_inv_map.items():
        if len(inv_list) >= 2:
            depleted = [i for i in inv_list if i.available_quantity <= 0]
            surplus = [i for i in inv_list if i.available_quantity >= max(i.reorder_quantity * 2, 40)]
            if depleted and surplus:
                wh_depleted = depleted[0].warehouse
                wh_surplus = surplus[0].warehouse
                p = depleted[0].product
                score = 65
                risks.append(
                    RiskItem(
                        id=f"RISK-IMBALANCE-{prod_id}-{wh_depleted.id}",
                        category="INVENTORY_IMBALANCE",
                        severity="HIGH",
                        score=score,
                        entity_type="inventory",
                        entity_id=str(depleted[0].id),
                        entity_name=f"{p.sku} ({wh_depleted.code} vs {wh_surplus.code})",
                        rules_triggered=["inter_warehouse_stock_disparity"],
                        metrics={
                            "depleted_warehouse": wh_depleted.code,
                            "depleted_avail": depleted[0].available_quantity,
                            "surplus_warehouse": wh_surplus.code,
                            "surplus_avail": surplus[0].available_quantity,
                        },
                        explanation=(
                            f"Regional stock disparity for '{p.name}' ({p.sku}): facility {wh_depleted.code} has 0 available units, "
                            f"while facility {wh_surplus.code} holds surplus stock ({surplus[0].available_quantity} available)."
                        ),
                        suggested_action=f"Dispatch inter-facility transfer from {wh_surplus.code} to {wh_depleted.code}.",
                        calculated_at=now,
                        source="deterministic_rules",
                    )
                )

    # 3. Supplier Reliability & SLA Risks
    sup_stmt = select(Supplier).where(Supplier.is_active == True)
    suppliers = (await session.execute(sup_stmt)).scalars().all()
    for sup in suppliers:
        rel = sup.reliability_score
        lead = sup.lead_time_days

        if rel < Decimal("0.85"):
            rel_score_pct = float(rel) * 100.0
            deficit = 0.85 - float(rel)
            score = min(95, max(60, int(60 + deficit * 150)))
            severity = "CRITICAL" if score >= 80 else "HIGH"
            risks.append(
                RiskItem(
                    id=f"RISK-SUPPLIER-{sup.id}",
                    category="SUPPLIER_RISK",
                    severity=severity,
                    score=score,
                    entity_type="supplier",
                    entity_id=str(sup.id),
                    entity_name=f"{sup.code} ({sup.name})",
                    rules_triggered=[f"reliability_score ({rel_score_pct:.1f}%) < 85.0%"],
                    metrics={
                        "supplier_code": sup.code,
                        "reliability_score": float(rel),
                        "lead_time_days": lead,
                    },
                    explanation=(
                        f"Supplier '{sup.name}' ({sup.code}) reliability rating is {rel_score_pct:.1f}%, "
                        f"falling below corporate SLA benchmark (85.0%). Average lead time is {lead} days."
                    ),
                    suggested_action=f"Conduct SLA compliance audit for {sup.name} and review alternate fulfillment sources.",
                    calculated_at=now,
                    source="deterministic_rules",
                )
            )
        elif lead >= 21:
            score = min(75, 50 + (lead - 21) * 2)
            risks.append(
                RiskItem(
                    id=f"RISK-LEADTIME-{sup.id}",
                    category="SUPPLIER_RISK",
                    severity="MEDIUM",
                    score=score,
                    entity_type="supplier",
                    entity_id=str(sup.id),
                    entity_name=f"{sup.code} ({sup.name})",
                    rules_triggered=[f"lead_time_days ({lead}) >= 21"],
                    metrics={"supplier_code": sup.code, "lead_time_days": lead},
                    explanation=(
                        f"Long replenishment lead time ({lead} days) for supplier '{sup.name}' ({sup.code}) "
                        f"increases supply shock vulnerability."
                    ),
                    suggested_action=f"Increase minimum buffer stock targets for all catalog items sourced from {sup.code}.",
                    calculated_at=now,
                    source="deterministic_rules",
                )
            )

    # 4. Order Fulfillment & Delay Risks
    order_stmt = (
        select(Order)
        .options(selectinload(Order.warehouse))
        .where(Order.status.in_(["PENDING", "PROCESSING"]))
    )
    orders = (await session.execute(order_stmt)).scalars().all()
    for ord in orders:
        wh_code = ord.warehouse.code if ord.warehouse else "GLOBAL"

        # Overdue check
        if ord.expected_delivery_date:
            exp_date = ord.expected_delivery_date
            if exp_date.tzinfo is None:
                exp_date = exp_date.replace(tzinfo=timezone.utc)
            if now > exp_date:
                days_overdue = max(1, (now - exp_date).days)
                score = min(100, 75 + days_overdue * 5)
                risks.append(
                    RiskItem(
                        id=f"RISK-ORDER-OVERDUE-{ord.id}",
                        category="FULFILLMENT_RISK",
                        severity="CRITICAL",
                        score=score,
                        entity_type="order",
                        entity_id=str(ord.id),
                        entity_name=f"{ord.order_number} ({ord.customer_name})",
                        rules_triggered=[f"current_time > expected_delivery_date ({days_overdue} days overdue)"],
                        metrics={
                            "order_number": ord.order_number,
                            "customer_name": ord.customer_name,
                            "days_overdue": days_overdue,
                            "status": ord.status,
                            "priority": ord.priority,
                            "total_amount": str(ord.total_amount),
                        },
                        explanation=(
                            f"Order {ord.order_number} for customer '{ord.customer_name}' is {days_overdue} day(s) overdue. "
                            f"Current status is {ord.status} with {ord.priority} priority."
                        ),
                        suggested_action="Expedite warehouse packing and carrier dispatch immediately.",
                        calculated_at=now,
                        source="deterministic_rules",
                    )
                )
                continue

        # Critical priority stalled in PENDING state
        if ord.priority == "CRITICAL" and ord.status == "PENDING":
            created = ord.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            hours_pending = (now - created).total_seconds() / 3600.0
            if hours_pending >= 6.0:
                score = min(85, int(65 + (hours_pending / 12.0) * 5))
                risks.append(
                    RiskItem(
                        id=f"RISK-ORDER-STALLED-{ord.id}",
                        category="FULFILLMENT_RISK",
                        severity="HIGH",
                        score=score,
                        entity_type="order",
                        entity_id=str(ord.id),
                        entity_name=f"{ord.order_number} ({ord.customer_name})",
                        rules_triggered=["priority == 'CRITICAL'", f"pending_hours ({hours_pending:.1f}) >= 6"],
                        metrics={
                            "order_number": ord.order_number,
                            "hours_pending": round(hours_pending, 1),
                            "priority": ord.priority,
                        },
                        explanation=(
                            f"CRITICAL customer order {ord.order_number} has remained in PENDING status for {hours_pending:.1f} hours "
                            f"without advancing to PROCESSING."
                        ),
                        suggested_action="Advance order to PROCESSING and allocate fulfillment resources.",
                        calculated_at=now,
                        source="deterministic_rules",
                    )
                )

    # Sort descending by risk score
    return sorted(risks, key=lambda r: r.score, reverse=True)


# Synchronous legacy compatibility wrapper for Phase 1 code/tests
def detect_risks() -> list[dict]:
    """Legacy compatibility helper returning structured risk dictionaries."""
    from statistics import mean

    DEMO_ORDERS = [
        {"id": "ORD-1048", "supplier": "Northstar Components", "delay_days": 6, "value": 420000},
        {"id": "ORD-1051", "supplier": "Vertex Supply", "delay_days": 1, "value": 180000},
        {"id": "ORD-1057", "supplier": "Northstar Components", "delay_days": 9, "value": 720000},
        {"id": "ORD-1062", "supplier": "Atlas Industrial", "delay_days": 4, "value": 250000},
    ]
    baseline = mean(order["delay_days"] for order in DEMO_ORDERS)
    risks = []
    for order in DEMO_ORDERS:
        score = min(100, int(order["delay_days"] * 8 + order["value"] / 100000))
        if order["delay_days"] > baseline + 1.5:
            risks.append({
                "id": order["id"],
                "type": "DELIVERY_DELAY",
                "severity": "critical" if score >= 80 else "high",
                "score": score,
                "supplier": order["supplier"],
                "delay_days": order["delay_days"],
                "message": f"Delivery is {order['delay_days']} days late, above the sample baseline of {baseline:.1f} days.",
            })
    return sorted(risks, key=lambda risk: risk["score"], reverse=True)
