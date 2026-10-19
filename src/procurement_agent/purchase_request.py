"""Turn a chosen offer into a structured procurement request and an email draft.

Nothing is sent or ordered. The request is a draft a human submits for approval
through the normal channel; this module only formats it.
"""

from __future__ import annotations

import secrets
from datetime import datetime

from pydantic import BaseModel, Field

from procurement_agent.comparison import ScoredOffer

PROCUREMENT_INBOX = "procurement@yourcompany.com"


class Requester(BaseModel):
    name: str = ""
    department: str = ""
    cost_center: str = ""


class PurchaseRequest(BaseModel):
    request_id: str
    created_at: datetime
    status: str = "Draft - pending approval"
    requester: Requester

    product_name: str
    supplier: str
    supplier_product_id: str
    manufacturer_part_number: str | None
    quantity: int
    unit_price: float
    total_price: float
    currency: str
    delivery_estimate_days: int | None
    warranty: str | None
    return_policy: str | None

    original_request: str = Field(description="What the employee asked for, in their words")
    justification: str = Field(description="Why this offer was chosen")
    alternatives_considered: list[str] = Field(default_factory=list)


def new_request_id(now: datetime) -> str:
    return f"PR-{now:%Y%m%d}-{secrets.token_hex(2).upper()}"


def build_purchase_request(
    choice: ScoredOffer,
    quantity: int,
    requester: Requester,
    original_request: str,
    justification: str,
    alternatives: list[ScoredOffer] = (),
    now: datetime | None = None,
) -> PurchaseRequest:
    if quantity < max(1, choice.offer.minimum_order_quantity):
        raise ValueError(f"Quantity must be at least {max(1, choice.offer.minimum_order_quantity)}")
    o = choice.offer
    unit = o.effective_price if o.effective_price is not None else o.price
    if unit is None:
        raise ValueError("This offer has no price, so it cannot be requested")
    now = now or datetime.now()
    return PurchaseRequest(
        request_id=new_request_id(now),
        created_at=now.replace(microsecond=0),
        requester=requester,
        product_name=o.product_name,
        supplier=o.supplier,
        supplier_product_id=o.supplier_product_id,
        manufacturer_part_number=o.manufacturer_part_number,
        quantity=quantity,
        unit_price=unit,
        total_price=round(unit * quantity, 2),
        currency=o.currency,
        delivery_estimate_days=o.delivery_estimate_days,
        warranty=o.warranty_information,
        return_policy=o.return_policy,
        original_request=original_request.strip(),
        justification=justification.strip(),
        alternatives_considered=[
            f"{a.offer.product_name} from {a.offer.supplier} at "
            f"${(a.offer.effective_price or a.offer.price or 0):,.2f} per unit"
            for a in alternatives
            if a.offer.supplier_product_id != o.supplier_product_id or a.offer.supplier != o.supplier
        ],
    )


def email_draft(pr: PurchaseRequest, to: str = PROCUREMENT_INBOX) -> str:
    """Plain-text email, ready to paste into a mail client."""
    r = pr.requester
    delivery = f"about {pr.delivery_estimate_days} days" if pr.delivery_estimate_days else "not stated"
    lines = [
        f"To: {to}",
        f"Subject: Purchase request {pr.request_id}: {pr.quantity} x {pr.product_name}",
        "",
        "Hello Procurement team,",
        "",
        "Please review and approve the following purchase request.",
        "",
        "REQUEST",
        f"  Request ID:     {pr.request_id}",
        f"  Date:           {pr.created_at:%Y-%m-%d %H:%M}",
        f"  Status:         {pr.status}",
        f"  Requested by:   {r.name or '(not given)'}",
        f"  Department:     {r.department or '(not given)'}",
        f"  Cost center:    {r.cost_center or '(not given)'}",
        "",
        "ITEM",
        f"  Product:        {pr.product_name}",
        f"  Part number:    {pr.manufacturer_part_number or '-'}",
        f"  Supplier:       {pr.supplier} (item {pr.supplier_product_id})",
        f"  Quantity:       {pr.quantity}",
        f"  Unit price:     ${pr.unit_price:,.2f} {pr.currency}",
        f"  Total:          ${pr.total_price:,.2f} {pr.currency}",
        f"  Delivery:       {delivery}",
        f"  Warranty:       {pr.warranty or '-'}",
        f"  Returns:        {pr.return_policy or '-'}",
        "",
        "WHY THIS ITEM",
        f"  Original request: \"{pr.original_request}\"",
        f"  {pr.justification}",
    ]
    if pr.alternatives_considered:
        lines += ["", "ALTERNATIVES CONSIDERED"] + [f"  - {a}" for a in pr.alternatives_considered]
    lines += [
        "",
        "Prices and availability were taken from supplier data at the time of the request",
        "and should be confirmed before the order is placed.",
        "",
        "Thank you,",
        r.name or "",
    ]
    return "\n".join(lines).rstrip() + "\n"
