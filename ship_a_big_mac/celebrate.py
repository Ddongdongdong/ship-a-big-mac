"""One guided release-to-feast workflow; demo is offline and live pickup is read-only."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
import webbrowser
from collections import defaultdict

from .actions import require_success, validate_arguments
from .git_release import ReleaseContext, analyze_repository
from .mcp import MCPClient, MCPError
from .planner import FeastPlan, MenuItem, PlanLine, format_yuan, plan_feasts, yuan_to_cents
from .quote import bind_quote_context, quote_plan
from .render import write_achievement, write_celebration_html, write_receipt
from .themes import THEMES, get_theme


def _ask(label: str, default: str, interactive: bool) -> str:
    if not interactive:
        return default
    try:
        return input(f"{label} [{default}]: ").strip() or default
    except EOFError:
        raise ValueError("input ended; supply options with --non-interactive") from None


def _choose(label: str, count: int, interactive: bool, default: int = 1) -> int:
    while True:
        answer = _ask(label, str(default), interactive)
        try:
            index = int(answer) - 1
            if 0 <= index < count:
                return index
        except ValueError:
            pass
        if not interactive:
            raise ValueError("choice is out of range")
        print(f"请输入 1–{count}。")


def _recommended_scene(context: ReleaseContext) -> str:
    """Map an observed release intensity to a suggested celebration scene.

    This is a recommendation only. An explicit ``--scene`` always wins and
    the mapping never changes the user's people count or budget.
    """
    if context.intensity == "hotfix":
        return "hotfix"
    if context.intensity == "major":
        return "major"
    return "sprint"


class LivePickup:
    """Inspect current schemas, and only call the small query set used by this flow."""

    def __init__(self, client: MCPClient):
        self.client = client
        self.schemas = {tool["name"]: tool.get("inputSchema", {}) for tool in client.list_tools()}
        if "calculate-price" not in self.schemas:
            raise MCPError("required live tool unavailable: calculate-price")

    def call(self, name: str, arguments: dict) -> object:
        if name not in self.schemas:
            raise MCPError(f"required live tool unavailable: {name}")
        validate_arguments(arguments, self.schemas[name])
        result = require_success(self.client.call_tool(name, arguments), name)
        body = result.get("structuredContent")
        if not isinstance(body, dict) or body.get("success") is not True or body.get("code") != 200:
            raise MCPError(f"{name} did not return a successful structured response")
        return body.get("data")

    def stores(self, city: str, keyword: str) -> list[dict]:
        raw = self.call("query-nearby-stores", {"beType": 1, "searchType": 2, "city": city, "keyword": keyword})
        if not isinstance(raw, list):
            raise MCPError("nearby stores response is not a list")
        return [s for s in raw if isinstance(s, dict) and s.get("storeCode") and s.get("businessStatus")]

    @staticmethod
    def default_rounds(detail: dict) -> list[dict]:
        rounds = detail.get("rounds")
        if not isinstance(rounds, list) or not rounds:
            raise ValueError("combo has no verifiable default rounds")
        result = []
        for group in rounds:
            if not isinstance(group, dict) or group.get("id") is None:
                raise ValueError("invalid combo round")
            choices = group.get("choices")
            if not isinstance(choices, list):
                raise ValueError("invalid combo choices")
            defaults = [c for c in choices if isinstance(c, dict) and c.get("isDefault") == 1]
            if not defaults:
                raise ValueError("combo requires manual option selection")
            selected = []
            for choice in defaults:
                if not isinstance(choice.get("code"), str) or type(choice.get("quantity")) is not int or choice["quantity"] <= 0:
                    raise ValueError("invalid default combo item")
                selected.append({"code": choice["code"], "quantity": choice["quantity"]})
            result.append({"round": str(group["id"]), "comboItemList": selected})
        return result

    @staticmethod
    def _category_hints(raw: dict) -> dict[str, set[str]]:
        """Collect category and tag hints for each product code.

        ``query-meals`` exposes product metadata in two places: the ``meals``
        map contains the price and display name, while ``categories`` carries
        the category name and product tags.  The API has changed the shape of
        the latter a few times, so malformed entries are ignored rather than
        making the whole menu unusable.
        """
        hints: dict[str, set[str]] = defaultdict(set)
        categories = raw.get("categories") if isinstance(raw, dict) else None
        if not isinstance(categories, list):
            return hints
        for category in categories:
            if not isinstance(category, dict):
                continue
            category_name = category.get("name")
            products = category.get("meals")
            if not isinstance(products, list):
                continue
            for product in products:
                if not isinstance(product, dict) or product.get("code") is None:
                    continue
                code = str(product["code"])
                if isinstance(category_name, str):
                    hints[code].add(category_name)
                tags = product.get("tags")
                if isinstance(tags, (list, tuple, set)):
                    hints[code].update(str(tag) for tag in tags if tag is not None)
        return hints

    @staticmethod
    def _is_coverage_item(item: dict, hints: set[str]) -> bool:
        """Return whether a live product can represent one person's main meal.

        The planner must not turn a drink, dessert or side into a person's
        meal.  There is no stable product-type field in every MCP response, so
        we use explicit API metadata when present and conservative category/
        name tags as a fallback.  A valid ``rounds`` payload is checked
        separately by :meth:`default_rounds` and is what makes the item
        orderable in this workflow.
        """
        for key in ("role", "type", "productType", "mealType", "category"):
            value = item.get(key)
            if isinstance(value, str) and value.lower() in {"side", "drink", "dessert", "beverage", "snack"}:
                return False
        text = " ".join(
            str(value).strip().lower()
            for value in [
                item.get("name"),
                item.get("role"),
                item.get("type"),
                item.get("productType"),
                item.get("mealType"),
                item.get("category"),
                *sorted(hints),
            ]
            if value is not None
        )
        # Keep this list deliberately conservative.  Unknown/new product
        # names remain eligible once their default combo rounds are verified.
        non_meal_terms = (
            "饮料", "饮品", "可乐", "雪碧", "果汁", "咖啡", "奶茶", "茶饮", "汽水",
            "纯牛奶", "苏打水", "矿泉水", "drink", "beverage", "coffee", "juice", "tea",
            "甜品", "甜点", "甜筒", "冰淇淋", "麦旋风", "圣代", "蛋挞", "派", "dessert", "ice cream",
            "小食", "配餐", "薯条", "鸡块", "玉米杯", "沙拉", "snack", "side",
        )
        return not any(term in text for term in non_meal_terms)

    def menu(self, shared: dict) -> tuple[list[MenuItem], dict[str, list[dict]], int]:
        raw = self.call("query-meals", shared)
        meals = raw.get("meals") if isinstance(raw, dict) else None
        if not isinstance(meals, dict):
            raise MCPError("menu response has no meals map")
        # Product names are display data, not a compatibility contract.  Use
        # the live category/tags metadata and verify each product's default
        # rounds instead of maintaining a hard-coded list of meal names.
        hints_by_code = self._category_hints(raw)
        candidates = []
        for code, item in meals.items():
            if not isinstance(item, dict) or not code:
                continue
            if item.get("canWithOrder") in (False, 0, "0", "false", "False"):
                continue
            if any(item.get(key) in (False, 0, "0", "false", "False") for key in ("available", "isAvailable")):
                continue
            if not isinstance(item.get("name"), str) or not item["name"].strip():
                continue
            if not self._is_coverage_item(item, hints_by_code.get(str(code), set())):
                continue
            candidates.append((str(code), item))
        # Preserve the menu's order (usually the restaurant's merchandising
        # order) so the resulting suggestions remain stable and understandable.
        menu, options = [], {}
        for code, item in candidates:
            try:
                price = yuan_to_cents(item["currentPrice"])
                if price <= 0:
                    continue
                detail = self.call("query-meal-detail", {**shared, "code": code})
                if not isinstance(detail, dict):
                    raise ValueError("meal detail does not match menu product")
                detail_code = detail.get("code") or detail.get("productCode")
                if detail_code is not None and str(detail_code) != code:
                    raise ValueError("meal detail does not match menu product")
                rounds = self.default_rounds(detail)
            except (ValueError, KeyError, TypeError, ArithmeticError, MCPError):
                print(f"  跳过无法验证默认组成的餐品：{item['name']}")
                continue
            menu.append(MenuItem(code, item["name"], price, serves=1, role="combo", tags=(item["name"],)))
            options[code] = rounds
        if not menu:
            raise ValueError("当前门店没有可验证默认组成的支持套餐；请换门店，或使用 Skill 自选餐品。")
        return menu, options, len(meals)

    @staticmethod
    def _coupon_candidates(raw: object, shared: dict, schema: dict) -> list[tuple[str, dict, str, str | None]]:
        """Return coupons that can be bound to the live quote schema safely.

        The server has used several names for the coupon collection and ID.
        Unknown shapes are deliberately ignored instead of sending guessed
        fields to ``calculate-price``.
        """
        if isinstance(raw, dict):
            values = raw.get("coupons") or raw.get("couponList") or raw.get("list")
        else:
            values = raw
        if not isinstance(values, list):
            return []
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        item_schema = properties.get("items", {}) if isinstance(properties.get("items"), dict) else {}
        item_schema = item_schema.get("items", {}) if isinstance(item_schema, dict) else {}
        item_properties = item_schema.get("properties", {}) if isinstance(item_schema, dict) else {}
        result = []
        for coupon in values:
            if not isinstance(coupon, dict) or coupon.get("canUse") is False or coupon.get("available") is False:
                continue
            identifier = next((coupon.get(key) for key in ("couponId", "couponCode", "id", "code") if isinstance(coupon.get(key), str) and coupon.get(key)), None)
            if not identifier:
                continue
            stores = coupon.get("storeCodes") or coupon.get("stores")
            if isinstance(stores, list) and str(shared.get("storeCode")) not in {str(value) for value in stores}:
                continue
            if isinstance(coupon.get("storeCode"), str) and coupon["storeCode"] != str(shared.get("storeCode")):
                continue
            bound = dict(shared)
            item_key = None
            if "couponId" in properties:
                bound["couponId"] = identifier
            elif "couponCode" in properties:
                bound["couponCode"] = identifier
            elif "couponId" in item_properties:
                item_key = "couponId"
            elif "couponCode" in item_properties:
                item_key = "couponCode"
            else:
                continue
            label = str(coupon.get("name") or identifier)
            result.append((label, bound, str(identifier), item_key))
        return result

    def candidates(self, shared: dict, people: int, budget: int) -> list[FeastPlan]:
        menu, options, count = self.menu(shared)
        print(f"菜单共 {count} 项，本次从 {len(menu)} 款单人套餐生成候选（默认组成）。")
        coupon_options = []
        try:
            coupon_raw = self.call("query-store-coupons", shared)
            coupon_options = self._coupon_candidates(coupon_raw, shared, self.schemas.get("calculate-price", {}))
            print(f"已查询门店优惠；当前返回中有 {len(coupon_options)} 张可验证券，逐一比较核价。")
        except MCPError:
            print("门店优惠查询暂不可用，继续核价无券候选。")
        candidates = plan_feasts(menu, people=people, budget_cents=budget)
        # Single-combo alternatives survive cases where a multi-item offer does
        # not apply to the complete order. Each still requires official quoting.
        for item in menu:
            if item.price_cents * people <= budget:
                candidates.append(FeastPlan("单品备选", people, budget, (PlanLine(item.code, item.name, people, item.price_cents, 1, "combo"),), item.price_cents * people, "MENU_SUM_NOT_MCP_QUOTED"))
        verified, seen = [], set()
        quote_variants = [(plan, None) for plan in candidates]
        for label, bound, identifier, item_key in coupon_options:
            for plan in candidates:
                quote_variants.append((plan, (label, bound, identifier, item_key)))
        for plan, coupon in quote_variants:
            coupon_label = coupon[0] if coupon else ""
            signature = tuple(sorted((line.code, line.quantity) for line in plan.lines)) + ((coupon_label,),)
            if signature in seen:
                continue
            seen.add(signature)
            arguments = {**(coupon[1] if coupon else shared), "items": [{"productCode": line.code, "quantity": line.quantity, "roundList": options[line.code]} for line in plan.lines]}
            if coupon and coupon[3] in {"couponId", "couponCode"}:
                for item in arguments["items"]:
                    item[coupon[3]] = coupon[2]
            if coupon:
                quoted_plan = replace(plan, strategy=f"{coupon_label} · {plan.strategy}")
            else:
                quoted_plan = plan
            validate_arguments(arguments, self.schemas.get("calculate-price", {}))
            bound = bind_quote_context(quoted_plan, arguments, self.client.url)
            try:
                quoted = quote_plan(self.client, bound, arguments)
            except MCPError as error:
                print(f"  候选已淘汰：{error}")
                continue
            verified.append(quoted)
        if not verified:
            raise ValueError("没有候选通过本次官方核价与预算检查；请增加预算或更换门店。")
        return verified


def _show_plans(plans: list[FeastPlan]) -> None:
    for index, plan in enumerate(plans, 1):
        print(f"\n  {index}. {plan.strategy} · {format_yuan(plan.quote_total_cents)} · {plan.total_serves} 名义人份")
        for line in plan.lines:
            print(f"     {line.name} × {line.quantity}")


def cmd_celebrate(args) -> int:
    interactive = sys.stdin.isatty() and not args.non_interactive
    print("\nSHIP A BIG MAC · 代码已上线，汉堡安排上。\n")
    context = analyze_repository(
        args.repo,
        since_days=args.days,
        from_tag=args.from_tag,
        to_ref=args.to_ref,
    )
    if args.version:
        context = replace(context, version=args.version)
    print(f"本地 Release：{context.repository} / {context.version}")
    print(f"{context.commit_count} commits · {context.files_changed} files · {context.contributor_count} makers\n")
    scene = args.scene
    if not scene:
        keys = list(THEMES)
        recommended = _recommended_scene(context)
        for i, key in enumerate(keys, 1):
            marker = " · Git Release 建议" if key == recommended else ""
            print(f"  {i}. {THEMES[key]['name']} ({key}){marker}")
        if interactive:
            scene = keys[_choose("选择庆祝主题", len(keys), interactive, keys.index(recommended) + 1)]
        else:
            scene = recommended
    theme = get_theme(scene)
    people = args.people if args.people is not None else int(_ask("这顿几个人", "5" if args.demo else str(max(1, context.contributor_count)), interactive))
    budget = yuan_to_cents(args.budget if args.budget is not None else _ask("总预算 / 元", str(people * 36), interactive))
    if not 1 <= people <= 50 or budget <= 0:
        raise ValueError("人数须为 1–50，预算须大于 0。")
    print(f"\n{theme['name']} · {people} 人 · 预算 {format_yuan(budget)}")
    if args.demo:
        raw = json.loads((Path(__file__).parent / "data/demo-menu.synthetic.json").read_text(encoding="utf-8"))
        plans = plan_feasts([MenuItem.from_dict(item) for item in raw["items"]], people=people, budget_cents=budget)
        print("离线演示 · 虚构菜单和价格 · 未连接账户")
    else:
        city = args.city or _ask("取餐城市", "", interactive)
        keyword = args.keyword or _ask("附近地标 / 关键词", "", interactive)
        if not city or not keyword:
            raise ValueError("真实模式需要城市和地标；脚本运行请传 --city 和 --keyword。")
        with MCPClient(url=args.url) as client:
            live = LivePickup(client)
            stores = live.stores(city, keyword)
            if not stores:
                raise ValueError("没有查询到营业中的到店取餐门店，请更换地标。")
            for index, store in enumerate(stores, 1):
                print(f"  {index}. {store.get('storeName', store['storeCode'])}")
            if args.store_code:
                store = next((s for s in stores if str(s["storeCode"]) == args.store_code), None)
                if store is None:
                    raise ValueError("指定门店不在本次附近门店结果中。")
            else:
                store = stores[_choose("选择取餐门店", len(stores), interactive)]
            print(f"取餐门店：{store.get('storeName', store['storeCode'])} · 到店取餐")
            plans = live.candidates({"storeCode": str(store["storeCode"]), "beType": 1, "orderType": 1}, people, budget)
    _show_plans(plans)
    selected = args.select - 1 if args.select is not None else _choose("选择庆功餐方案", len(plans), interactive)
    if not 0 <= selected < len(plans):
        raise ValueError("--select is out of range")
    plan = plans[selected]
    folder = Path(args.output_dir).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    write_receipt(folder / "release-receipt.svg", context, plan)
    write_achievement(folder / "release-achievement.svg", context, plan, scene)
    preview = write_celebration_html(folder / "celebration.html", context, plan, scene)
    # Only shareable aggregate context and meal data; never persist MCP payloads.
    (folder / "celebration.json").write_text(json.dumps({"scene": scene, "context": {key: value for key, value in context.to_dict().items() if key not in {"contributors", "branch"}}, "plan": plan.to_dict()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n成就卡、小票与预览已生成：{folder.resolve()}")
    print(f"打开 {preview.name}，即可保存 PNG 成就卡。")
    print("示意金额 · 非实时报价" if args.demo else "本次官方核价 · 未下单 · 再次点餐需重新核价")
    if args.open:
        webbrowser.open(preview.as_uri())
    return 0


def add_celebrate_parser(sub) -> None:
    parser = sub.add_parser("celebrate", help="one guided release, meal and achievement-card workflow")
    parser.add_argument("--demo", action="store_true", help="use synthetic menu prices without network access")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--from-tag", help="analyze the release range after this tag")
    parser.add_argument("--to-ref", help="release endpoint ref (tag, branch, or commit)")
    parser.add_argument("--version", help="release label displayed on the card")
    parser.add_argument("--scene", choices=list(THEMES))
    parser.add_argument("--people", type=int)
    parser.add_argument("--budget", help="total budget in yuan")
    parser.add_argument("--city")
    parser.add_argument("--keyword", help="public landmark for nearby pickup stores")
    parser.add_argument("--store-code", help="choose a store from the current nearby-store result")
    parser.add_argument("--select", type=int, help="candidate number, starting at 1")
    parser.add_argument("--non-interactive", action="store_true", help="use provided options and defaults without prompts")
    parser.add_argument("--output-dir", default="celebration")
    parser.add_argument("--open", action="store_true", help="open the local preview in your browser")
    parser.add_argument("--url", default="https://mcp.mcd.cn")
    parser.set_defaults(func=cmd_celebrate)
