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


def _minimum_cover(
    items: list[MenuItem], people: int
) -> tuple[list[int], list[MenuItem | None]]:
    """Find exact menu costs for covering each remaining number of people.

    Quantities are unlimited, and a final item may serve more people than remain.
    Sides and drinks must be excluded by the caller.
    """
    costs = [0]
    choices: list[MenuItem | None] = [None]
    for remaining in range(1, people + 1):
        chosen = min(
            items,
            key=lambda item: (
                item.price_cents + costs[max(0, remaining - item.serves)],
                item.price_cents,
                item.name,
                item.code,
            ),
        )
        costs.append(chosen.price_cents + costs[max(0, remaining - chosen.serves)])
        choices.append(chosen)
    return costs, choices


def _pick(
    items: list[MenuItem],
    *,
    people: int,
    budget_cents: int,
    strategy: str,
    minimum_costs: list[int],
    minimum_choices: list[MenuItem | None],
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
    while covered < people:
        # Reserve enough budget to finish the meal before rewarding variety.
        # Looking only at this item's price can leave a feasible plan stranded.
        affordable = [
            item
            for item in coverage_items
            if spent + item.price_cents
            + minimum_costs[max(0, people - covered - item.serves)] <= budget_cents
        ]

        def score(item: MenuItem) -> tuple[float, float, str]:
            efficiency = item.serves / item.price_cents
            novelty = (item.role not in used_roles) + (item.name not in used_names)
            if strategy == "多样性":
                primary = novelty * 100 + len(set(item.tags) - used_tags) * 10 + efficiency
            else:
                role_bonus = 40 if item.role in {"combo", "meal"} else 10
                primary = efficiency * 50_000 + novelty * 20 + role_bonus
            return primary, -item.price_cents, item.name

        if strategy == "省预算":
            chosen = minimum_choices[people - covered]
            assert chosen is not None
        else:
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
    coverage_items = [item for item in items if item.role in {"meal", "combo"}]
    if not coverage_items:
        raise ValueError("menu has no meal or combo items that can cover a person")
    if any(item.serves < 1 for item in coverage_items):
        raise ValueError("meal and combo items must serve at least one person")
    minimum_costs, minimum_choices = _minimum_cover(coverage_items, people)
    if minimum_costs[people] > budget_cents:
        raise ValueError(
            f"budget cannot cover {people} people; "
            f"minimum menu total is {format_yuan(minimum_costs[people])}"
        )
    candidates = [
        _pick(
            items,
            people=people,
            budget_cents=budget_cents,
            strategy=strategy,
            minimum_costs=minimum_costs,
            minimum_choices=minimum_choices,
        )
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
    return unique


def apply_mcp_quote(
    plan: FeastPlan,
    *,
    total_cents: int,
    quote_id: str | None = None,
) -> FeastPlan:
    if total_cents < 0:
        raise ValueError("quoted total cannot be negative")
    if total_cents > plan.budget_cents:
        raise ValueError(
            f"quoted total {format_yuan(total_cents)} exceeds budget "
            f"{format_yuan(plan.budget_cents)}; revise the plan and request a new quote"
        )
    return FeastPlan(
        strategy=plan.strategy,
        people=plan.people,
        budget_cents=plan.budget_cents,
        lines=plan.lines,
        quote_total_cents=total_cents,
        quote_source="MCD_MCP_CALCULATE_PRICE",
        quote_id=quote_id,
    )
