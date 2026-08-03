"""
core/rules.py — 花牌游戏规则配置中心
====================================
所有规则参数集中管理，方便后续调整和扩展。
基于《花牌游戏开发架构文档v2.1》中已确认的规则。

核心设定：
- 22种字面 × 5张 = 110张 + 2张赖子 = 112张
- 3人游戏：庄家26张，旁家25张，发牌后余36张
- 精牌（三/五/七/乙/九）每种5张中2花精+3皮精
- 赖子只能通配三、五、七（红精），胡数计算中按红皮精处理
- 主精翻倍：在三/五/七中选使胡数最大的字面，胡数×2
- 计分：17胡-21胡得3分，再每多5胡加1分
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .melds import (
    DEALER_HAND_COUNT, INIT_HAND_COUNT, MIN_HU_SCORE,
    PLAYER_COUNT, TOTAL_CARD_COUNT, WILD_COUNT,
    WILD_USABLE_CHARS, WILD_CHAR,
    BASE_SCORE, HIGH_HU_THRESHOLD, SCORE_STEP_HU, SCORE_STEP_VALUE,
    ACTION_TIMEOUT, HU_TIMEOUT,
)


class JokerUsage(Enum):
    """赖子使用方式"""
    WILD_357 = "wild_357"  # 只能通配三、五、七


@dataclass
class GameRules:
    """游戏规则配置

    集中管理所有可调规则参数。
    默认值均与架构文档v2.1一致。
    """

    # ==================== 基本设置 ====================
    total_cards: int = TOTAL_CARD_COUNT         # 112张
    player_count: int = PLAYER_COUNT            # 3人
    init_hand_count: int = INIT_HAND_COUNT      # 旁家25张
    dealer_hand_count: int = DEALER_HAND_COUNT  # 庄家26张
    remaining_after_deal: int = 36              # 发牌后余牌池36张

    # ==================== 胡牌与计分 ====================
    min_hu_for_win: int = MIN_HU_SCORE          # 最小胡数17胡
    base_score_threshold: int = 17              # 起算胡数
    high_score_threshold: int = HIGH_HU_THRESHOLD  # 3分段上限21胡
    base_score: int = BASE_SCORE                # 17-21胡 → 3分
    score_step_hu: int = SCORE_STEP_HU          # 每多5胡加1分
    score_step_value: int = SCORE_STEP_VALUE    # 加分步长

    # ==================== 赖子规则 ====================
    wild_count: int = WILD_COUNT                # 赖子张数(2)
    wild_usable_chars: List[str] = field(
        default_factory=lambda: sorted(WILD_USABLE_CHARS)
    )  # ["三", "五", "七"]

    # ==================== 精牌规则 ====================
    main_jin_multiplier: int = 2                # 主精翻倍倍数
    main_jin_candidates: List[str] = field(
        default_factory=lambda: list(WILD_USABLE_CHARS)
    )  # 主精候选字面（三/五/七）

    # ==================== 操作规则 ====================
    action_timeout: int = ACTION_TIMEOUT        # 操作时限（秒）
    hu_timeout: int = HU_TIMEOUT                # 胡牌判定时限（秒）

    # ==================== 庄家规则 ====================
    dealer_first_discard: bool = True           # 庄家先出牌

    # ==================== 方法 ====================

    def can_use_wild_as(self, target_char: str) -> bool:
        """判断赖子是否可以替代目标字面

        规则：赖子只能通配三、五、七
        """
        return target_char in self.wild_usable_chars

    def is_valid_hu(self, total_hu: int) -> bool:
        """判断胡数是否满足胡牌条件（>=17胡）"""
        return total_hu >= self.min_hu_for_win

    def calc_total_score(self, total_hu: int) -> int:
        """根据总胡数计算得分

        17-21胡 → 3分，之后每多5胡加1分
        """
        if total_hu < self.base_score_threshold:
            return 0
        if total_hu <= self.high_score_threshold:
            return self.base_score
        extra_hu = total_hu - self.high_score_threshold
        return self.base_score + (extra_hu // self.score_step_hu) * self.score_step_value

    def apply_main_jin_multiplier(self, total_hu: int, has_main_jin: bool) -> int:
        """应用主精翻倍

        如果牌型中包含主精，胡数×2
        """
        if has_main_jin and total_hu > 0:
            return total_hu * self.main_jin_multiplier
        return total_hu

    def get_score_table(self) -> Dict[str, str]:
        """返回计分公式说明（用于UI展示）"""
        return {
            "formula": "17-21胡=3分，每多5胡加1分",
            "min_hu": str(self.min_hu_for_win),
            "base": f"{self.base_score_threshold}-{self.high_score_threshold}胡→{self.base_score}分",
            "step": f"每{self.score_step_hu}胡加{self.score_step_value}分",
            "jin_multiplier": f"主精翻{self.main_jin_multiplier}倍",
            "wild_rule": f"赖子通配{'+'.join(self.wild_usable_chars)}",
        }

    def validate_config(self) -> List[str]:
        """验证规则配置的合法性

        Returns:
            错误信息列表，空列表表示配置合法
        """
        errors = []

        if self.total_cards != 112:
            errors.append(f"牌总数应为112，当前{self.total_cards}")
        if self.player_count != 3:
            errors.append(f"玩家数应为3，当前{self.player_count}")
        if self.init_hand_count != 25:
            errors.append(f"旁家手牌应为25张，当前{self.init_hand_count}")
        if self.dealer_hand_count != 26:
            errors.append(f"庄家手牌应为26张，当前{self.dealer_hand_count}")
        if self.min_hu_for_win < 17:
            errors.append(f"最小胡数应>=17，当前{self.min_hu_for_win}")
        if self.wild_count != 2:
            errors.append(f"赖子数应为2，当前{self.wild_count}")
        if set(self.wild_usable_chars) != {"三", "五", "七"}:
            errors.append(f"赖子通配范围应为三/五/七，当前{self.wild_usable_chars}")
        if self.main_jin_multiplier < 2:
            errors.append(f"主精倍数应>=2，当前{self.main_jin_multiplier}")

        return errors


# ==================== 全局规则实例 ====================

DEFAULT_RULES = GameRules()


def load_rules_from_config(config_path: str) -> GameRules:
    """从JSON配置文件加载规则（预留接口）"""
    import json
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    rules = GameRules()
    for key, value in config.items():
        if hasattr(rules, key):
            setattr(rules, key, value)
    return rules


def save_rules_to_config(rules: GameRules, config_path: str) -> None:
    """将当前规则配置保存为JSON文件"""
    import json
    from dataclasses import asdict
    config = asdict(rules)
    for k, v in config.items():
        if isinstance(v, Enum):
            config[k] = v.value
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
