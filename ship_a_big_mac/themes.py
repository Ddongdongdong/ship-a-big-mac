"""Celebration scenes are chosen by people, never earned by commit count."""

THEMES = {
    "major": {"name": "巨无霸胜利宴", "eyebrow": "RELEASE UNLOCKED", "tagline": "代码已上线，汉堡安排上。", "color": "#c63028"},
    "hotfix": {"name": "紧急回血套餐", "eyebrow": "HOTFIX HERO", "tagline": "问题已解决，先给自己回个血。", "color": "#b94d24"},
    "sprint": {"name": "团队能量补给", "eyebrow": "SPRINT COMPLETE", "tagline": "这一程辛苦了，一起补充能量。", "color": "#466343"},
    "comeback": {"name": "绝地反击庆功餐", "eyebrow": "BACK TO GREEN", "tagline": "终于全绿了，这一口值得庆祝。", "color": "#28675b"},
}


def get_theme(scene: str) -> dict[str, str]:
    if scene not in THEMES:
        raise ValueError("unknown celebration scene; choose major, hotfix, sprint or comeback")
    return THEMES[scene]
