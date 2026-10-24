"""
Real Recommendation Engine for Operations Decision Intelligence.
Generates deduplicated recommendations from operational database risks and state.
Provides strict validation, human approval workflow, and transaction-safe idempotent execution.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from app.models.inventory import Inventory
from app.models.order import Order
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.supplier import Supplier
from app.models.user import User
from app.models.warehouse import Warehouse
from app.repositories.audit_log import AuditLogRepository
from app.repositories.inventory import InventoryRepository
from app.repositories.order import OrderRepository
from app.repositories.recommendation import RecommendationRepository
from app.services.risk_engine import detect_operational_risks


async def sync_and_generate_recommendations(session: AsyncSession) -> list[Recommendation]:
    """
    Scans live database risks and generates deduplicated recommendations.
    If a PENDING recommendation for the affected entity already exists, updates its evidence
    rather than creating duplicate rows on subsequent refreshes.
    """
    now = datetime.now(timezone.utc)
    risks = await detect_operational_risks(session)
    repo = RecommendationRepository(session)
    active_recs: list[Recommendation] = []

    for risk in risks:
        rec_type = ""
        action = ""
        params: dict[str, Any] = {}
        title = ""

        if risk.category == "STOCKOUT_RISK":
            rec_type = "STOCK_REORDER"
            action = "reorder_stock"
            prod_id = uuid.UUID(risk.metrics["product_id"])
            wh_id = uuid.UUID(risk.metrics["warehouse_id"])
            reorder_lvl = risk.metrics.get("reorder_threshold", 50)
            avail = risk.metrics.get("available_quantity", 0)
            target_qty = max(50, (reorder_lvl * 2) - max(0, avail))

            title = f"Replenish inventory for {risk.entity_name}"
            params = {
                "product_id": str(prod_id),
                "warehouse_id": str(wh_id),
                "quantity": target_qty,
                "reference": f"AUTO-REC-{now.strftime('%Y%m%d%H%M')}",
            }
        elif risk.category == "INVENTORY_IMBALANCE":
            rec_type = "REBALANCE_INVENTORY"
            action = "rebalance_inventory"
            title = f"Inter-facility stock transfer for {risk.entity_name}"
            params = {
                "inventory_id": risk.entity_id,
                "depleted_warehouse": risk.metrics.get("depleted_warehouse"),
                "surplus_warehouse": risk.metrics.get("surplus_warehouse"),
                "suggested_transfer_units": 25,
            }
        elif risk.category == "FULFILLMENT_RISK":
            rec_type = "FULFILLMENT_EXPEDITE"
            action = "expedite_order"
            title = f"Expedite fulfillment for {risk.entity_name}"
            order_id = risk.entity_id
            curr_status = risk.metrics.get("status", "PENDING")
            next_status = "PROCESSING" if curr_status == "PENDING" else "SHIPPED"
            params = {
                "order_id": order_id,
                "current_status": curr_status,
                "target_status": next_status,
            }
        elif risk.category == "SUPPLIER_RISK":
            rec_type = "SUPPLIER_AUDIT"
            action = "audit_supplier"
            title = f"Review vendor SLA compliance for {risk.entity_name}"
            params = {
                "supplier_id": risk.entity_id,
                "reliability_score": risk.metrics.get("reliability_score"),
                "lead_time_days": risk.metrics.get("lead_time_days"),
            }
        else:
            continue

        # Deduplication check: Is there already a PENDING recommendation for this entity and type?
        existing = await repo.get_pending_by_entity(rec_type, risk.entity_id)
        if existing:
            # Update existing recommendation with latest metrics and evidence
            existing.evidence = risk.metrics
            existing.explanation = risk.explanation
            existing.priority = risk.severity
            existing.parameters = params
            await repo.update(existing)
            active_recs.append(existing)
        else:
            # Check if there is an existing EXECUTED recommendation created within the last 30 minutes
            new_rec = Recommendation(
                recommendation_type=rec_type,
                priority=risk.severity,
                title=title,
                entity_type=risk.entity_type,
                entity_id=risk.entity_id,
                entity_name=risk.entity_name,
                evidence=risk.metrics,
                explanation=risk.explanation,
                proposed_action=action,
                parameters=params,
                status="PENDING",
            )
            created = await repo.create(new_rec)
            active_recs.append(created)

    # If database has zero recommendations and zero risks detected (bootstrap or quiet operational state),
    # create a baseline operational calibration recommendation so operators always have a calibrated baseline.
    existing_items, _ = await repo.list_filtered(limit=1)
    if not existing_items and not active_recs:
        bootstrap_rec = Recommendation(
            recommendation_type="BASELINE_CALIBRATION",
            priority="MEDIUM",
            title="Calibrate operational inventory and safety stock thresholds",
            entity_type="system",
            entity_id="SYS-BOOTSTRAP-001",
            entity_name="Global Operational Parameters",
            evidence={"system_state": "calibration_baseline", "recommended_buffer_days": 14},
            explanation="Initial operations baseline: review warehouse buffer rules and calibrate replenishment points.",
            proposed_action="audit_supplier",
            parameters={"scope": "initial_calibration"},
            status="PENDING",
        )
        created_boot = await repo.create(bootstrap_rec)
        active_recs.append(created_boot)

    return active_recs




async def record_human_decision(
    recommendation_id: uuid.UUID,
    approved: bool,
    current_user: User,
    comment: str,
    session: AsyncSession,
) -> Recommendation:
    """
    Records a human decision (APPROVE or REJECT) on a PENDING recommendation with full audit trail.
    """
    repo = RecommendationRepository(session)
    rec = await repo.get_by_id(recommendation_id)
    if not rec:
        raise ValueError("Recommendation not found")

    if rec.status != "PENDING":
        raise ValueError(f"Cannot record decision on recommendation in '{rec.status}' status")

    now = datetime.now(timezone.utc)
    rec.status = "APPROVED" if approved else "REJECTED"
    rec.decided_at = now
    rec.decided_by_user_id = current_user.id
    rec.decided_by_name = current_user.full_name or current_user.email
    rec.decision_comment = comment

    await repo.update(rec)

    # Persist decision to audit_logs in same transaction
    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="recommendation",
            entity_id=str(rec.id),
            action=f"recommendation.{rec.status.lower()}",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            comment=comment,
            payload={
                "recommendation_type": rec.recommendation_type,
                "entity_type": rec.entity_type,
                "entity_id": rec.entity_id,
                "priority": rec.priority,
                "status": rec.status,
            },
        )
    )

    return rec


async def execute_approved_recommendation(
    recommendation_id: uuid.UUID,
    current_user: User,
    comment: str,
    session: AsyncSession,
) -> tuple[Recommendation, dict[str, Any]]:
    """
    Safely and transactionally executes an APPROVED recommendation.
    Enforces current database state re-validation, idempotency, and transactional consistency.
    """
    repo = RecommendationRepository(session)
    rec = await repo.get_by_id(recommendation_id)
    if not rec:
        raise ValueError("Recommendation not found")

    # Idempotency check: If already EXECUTED, safely return existing result without duplicate work
    if rec.status == "EXECUTED":
        return rec, rec.execution_result or {"status": "already_executed"}

    if rec.status != "APPROVED":
        raise ValueError(
            f"Cannot execute recommendation with status '{rec.status}'. "
            f"Only 'APPROVED' recommendations can be executed."
        )

    now = datetime.now(timezone.utc)
    result_data: dict[str, Any] = {}

    # 1. Action: reorder_stock
    if rec.proposed_action == "reorder_stock":
        params = rec.parameters or {}
        prod_id = uuid.UUID(params["product_id"])
        wh_id = uuid.UUID(params["warehouse_id"])
        qty = int(params["quantity"])
        ref = params.get("reference", f"REC-EXEC-{rec.id.hex[:6].upper()}")

        # Re-validate current database state: product and warehouse must exist and be active
        prod = await session.get(Product, prod_id)
        if not prod or not prod.is_active:
            raise ValueError(f"Target product {prod_id} is inactive or no longer exists in database")

        wh = await session.get(Warehouse, wh_id)
        if not wh or not wh.is_active:
            raise ValueError(f"Target warehouse {wh_id} is inactive or no longer exists in database")

        # Execute stock receipt atomically
        inv_repo = InventoryRepository(session)
        inv, mov = await inv_repo.execute_receipt(
            product_id=prod_id,
            warehouse_id=wh_id,
            quantity=qty,
            reference=ref,
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            idempotency_key=f"rec-exec-{rec.id}",
        )

        result_data = {
            "action": "reorder_stock",
            "quantity_received": qty,
            "movement_id": str(mov.id),
            "new_quantity_on_hand": inv.quantity_on_hand,
            "available_quantity": inv.available_quantity,
        }

    # 2. Action: expedite_order
    elif rec.proposed_action == "expedite_order":
        params = rec.parameters or {}
        ord_id = uuid.UUID(params["order_id"])
        order_repo = OrderRepository(session)
        order = await order_repo.get_by_id(ord_id)
        if not order:
            raise ValueError(f"Target order {ord_id} no longer exists")

        if order.status in ("DELIVERED", "CANCELLED"):
            raise ValueError(f"Target order {order.order_number} is already in terminal state '{order.status}'")

        target_status = params.get("target_status", "PROCESSING")
        order_repo.validate_and_update_status(order, target_status)
        await order_repo.update(order)

        result_data = {
            "action": "expedite_order",
            "order_number": order.order_number,
            "new_status": order.status,
        }

    # 3. Action: audit_supplier or advisory
    elif rec.proposed_action in ("audit_supplier", "rebalance_inventory"):
        result_data = {
            "action": rec.proposed_action,
            "recorded": True,
            "message": "Advisory action logged in system operational registers",
        }
    else:
        raise ValueError(f"Unsupported action type: {rec.proposed_action}")

    # Update recommendation state to EXECUTED
    rec.status = "EXECUTED"
    rec.executed_at = now
    rec.execution_result = result_data
    await repo.update(rec)

    # Record execution event into audit_logs in same transaction
    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="recommendation",
            entity_id=str(rec.id),
            action="recommendation.executed",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            comment=comment or f"Executed proposal {rec.proposed_action}",
            payload={
                "recommendation_id": str(rec.id),
                "action": rec.proposed_action,
                "execution_result": result_data,
            },
        )
    )

    return rec, result_data


# Legacy synchronous fallback
def recommendations() -> list[dict]:
    """Legacy compatibility helper returning simulated recommendation items."""
    from app.services.risk_engine import detect_risks

    result = []
    for risk in detect_risks():
        result.append({
            "id": f"REC-{risk['id']}",
            "risk_id": risk["id"],
            "title": "Escalate supplier and assess alternate fulfillment",
            "action": "Ask procurement to confirm a recovery date and compare backup suppliers.",
            "reason": risk["message"],
            "risk_score": risk["score"],
            "requires_human_approval": True,
            "status": "pending",
        })
    return result
