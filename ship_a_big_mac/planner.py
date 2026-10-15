"""Deterministic feast planning over normalized, quoted menu data."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


def yuan_to_cents(value: str | int | float | Decimal) -> int:
    amount = Decimal(str(value)) * 100
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_yuan(cents: int) -> str:
    return f"¥{cents / 100:.2f}"


@dataclass(frozen=True)
class MenuItem:
    code: str
    name: str
    price_cents: int
    serves: int = 1
    role: str = "meal"
    tags: tuple[str, ...] = ()
    available: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "MenuItem":
        price = raw.get("price_cents")
        if price is None:
            raise ValueError(f"{raw.get('name', 'menu item')} is missing price_cents")
        tags = raw.get("tags") or []
        return cls(
            code=str(raw.get("code") or raw.get("productCode") or ""),
            name=str(raw.get("name") or "未命名餐品"),
            price_cents=int(price),
            serves=max(1, int(raw.get("serves") or 1)),
            role=str(raw.get("role") or "meal"),
            tags=tuple(str(tag) for tag in tags),
            available=bool(raw.get("available", True)),
        )


@dataclass(frozen=True)
class PlanLine:
    code: str
    name: str
    quantity: int
    unit_price_cents: int
    serves: int
    role: str

    @property
    def subtotal_cents(self) -> int:
        return self.quantity * self.unit_price_cents


@dataclass(frozen=True)
class FeastPlan:
    strategy: str
    people: int
    budget_cents: int
    lines: tuple[PlanLine, ...]
    quote_total_cents: int
    quote_source: str
    quote_id: str | None = None

    @property
    def total_serves(self) -> int:
        return sum(
            line.quantity * line.serves
            for line in self.lines
            if line.role in {"meal", "combo"}
        )

    @property
    def remaining_cents(self) -> int:
        return self.budget_cents - self.quote_total_cents

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "people": self.people,
            "budget_cents": self.budget_cents,
            "quote_total_cents": self.quote_total_cents,
            "quote_source": self.quote_source,
            "quote_id": self.quote_id,
            "total_serves": self.total_serves,
            "remaining_cents": self.remaining_cents,
            "lines": [
                {**asdict(line), "subtotal_cents": line.subtotal_cents}
                for line in self.lines
            ],
        }


def _pick(
    items: list[MenuItem],
    *,
    people: int,
    budget_cents: int,
    strategy: str,
) -> FeastPlan:
    counts: dict[MenuItem, int] = {}
    coverage_items = [item for item in items if item.role in {"meal", "combo"}]
    if not coverage_items:
        raise ValueError("menu has no meal or combo items that can cover a person")
    covered = 0
    spent = 0
    used_roles: set[str] = set()
    used_tags: set[str] = set()
    used_names: set[str] = set()
    max_units = people + 3

    while covered < people and sum(counts.values()) < max_units:
        affordable = [item for item in coverage_items if spent + item.price_cents <= budget_cents]
        if not affordable:
            break

        def score(item: MenuItem) -> tuple[float, float, str]:
            efficiency = item.serves / item.price_cents
            novelty = (item.role not in used_roles) + (item.name not in used_names)
            if strategy == "省预算":
                primary = efficiency * 100_000
            elif strategy == "多样性":
                primary = novelty * 100 + len(set(item.tags) - used_tags) * 10 + efficiency
            else:
                role_bonus = 40 if item.role in {"combo", "meal"} else 10
                primary = efficiency * 50_000 + novelty * 20 + role_bonus
            return primary, -item.price_cents, item.name

        chosen = max(affordable, key=score)
        counts[chosen] = counts.get(chosen, 0) + 1
        covered += chosen.serves
        spent += chosen.price_cents
        used_roles.add(chosen.role)
        used_tags.update(chosen.tags)
        used_names.add(chosen.name)

    extras_by_strategy = {
        "均衡": ("side", "drink"),
        "多样性": ("side", "drink", "dessert"),
        "省预算": (),
    }
    if covered >= people:
        for role in extras_by_strategy[strategy]:
            options = [
                item
                for item in items
                if item.role == role and spent + item.price_cents <= budget_cents
            ]
            if not options:
                continue
            chosen = min(options, key=lambda item: (item.price_cents, item.name))
            counts[chosen] = counts.get(chosen, 0) + 1
            spent += chosen.price_cents

    lines = tuple(
        PlanLine(
            code=item.code,
            name=item.name,
            quantity=quantity,
            unit_price_cents=item.price_cents,
            serves=item.serves,
            role=item.role,
        )
        for item, quantity in sorted(counts.items(), key=lambda pair: pair[0].name)
    )
    return FeastPlan(
        strategy=strategy,
        people=people,
        budget_cents=budget_cents,
        lines=lines,
        quote_total_cents=spent,
        quote_source="MENU_SUM_NOT_MCP_QUOTED",
    )


def plan_feasts(
    menu: Iterable[MenuItem],
    *,
    people: int,
    budget_cents: int,
) -> list[FeastPlan]:
    if not 1 <= people <= 50:
        raise ValueError("people must be between 1 and 50")
    if budget_cents <= 0:
        raise ValueError("budget must be positive")
    items = [item for item in menu if item.available and item.price_cents > 0]
    if not items:
        raise ValueError("no available menu items")
    candidates = [
        _pick(items, people=people, budget_cents=budget_cents, strategy=strategy)
        for strategy in ("均衡", "省预算", "多样性")
    ]
    unique: list[FeastPlan] = []
    seen: set[tuple[tuple[str, int], ...]] = set()
    for plan in candidates:
        if plan.total_serves < people:
            continue
        signature = tuple((line.code, line.quantity) for line in plan.lines)
        if signature not in seen:
            seen.add(signature)
            unique.append(plan)
    if not unique:
        cheapest = min(item.price_cents / item.serves for item in items)
        minimum = int(cheapest * people)
        raise ValueError(f"budget cannot cover {people} people; estimated minimum is {format_yuan(minimum)}")
    return unique


def apply_mcp_quote(
    plan: FeastPlan,
    *,
    total_cents: int,
    quote_id: str | None = None,
) -> FeastPlan:
    if total_cents < 0:
        raise ValueError("quoted total cannot be negative")
    return FeastPlan(
        strategy=plan.strategy,
        people=plan.people,
        budget_cents=plan.budget_cents,
        lines=plan.lines,
        quote_total_cents=total_cents,
        quote_source="MCD_MCP_CALCULATE_PRICE",
        quote_id=quote_id,
    )
