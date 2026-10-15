"""Official MCP capabilities verified against the live tool list on 2026-10-15."""

READ_ONLY_MCP_TOOLS = frozenset({
    "now-time-info", "list-nutrition-foods", "campaign-calendar",
    "query-nearby-stores", "query-meals", "query-meal-detail", "calculate-price",
    "query-store-coupons", "available-coupons", "query-my-coupons",
    "query-my-account", "mall-points-products", "mall-product-detail",
    "delivery-query-addresses", "delivery-query-stores", "query-meal-assistance",
    "query-order", "order-list", "mall-order-list", "mall-order-detail",
    "query-lottery-info", "query-my-prizes", "query-party-city", "query-party-store",
    "query-party-store-date", "query-party-store-session", "query-promotions",
    "query-survey-coupon",
})

WRITE_MCP_TOOLS = {
    "auto-bind-coupons": "领取账户当前所有可领麦麦省优惠券",
    "delivery-create-address": "将收件人信息与配送地址保存至麦当劳账户",
    "create-order": "创建真实餐品订单并返回支付信息；不自动支付",
    "cancel-order": "取消指定的真实餐品订单",
    "mall-create-order": "创建商城兑换订单，可能扣除积分或占用商品库存",
    "draw-lottery": "进行一次真实抽奖，可能消耗积分或抽奖次数",
    "party-order-create": "创建真实主题活动预约订单",
}

CAPABILITY_GROUPS = {
    "营养与活动": ("list-nutrition-foods", "campaign-calendar", "now-time-info"),
    "门店与配餐": ("query-nearby-stores", "query-meals", "query-meal-detail", "calculate-price", "query-meal-assistance", "query-promotions"),
    "优惠券": ("available-coupons", "query-my-coupons", "query-store-coupons", "auto-bind-coupons"),
    "积分与商城": ("query-my-account", "mall-points-products", "mall-product-detail", "mall-create-order", "mall-order-list", "mall-order-detail"),
    "外送地址": ("delivery-query-addresses", "delivery-query-stores", "delivery-create-address"),
    "点餐与订单": ("create-order", "order-list", "query-order", "cancel-order", "query-survey-coupon"),
    "抽奖": ("query-lottery-info", "query-my-prizes", "draw-lottery"),
    "主题活动": ("query-party-city", "query-party-store", "query-party-store-date", "query-party-store-session", "party-order-create"),
}
