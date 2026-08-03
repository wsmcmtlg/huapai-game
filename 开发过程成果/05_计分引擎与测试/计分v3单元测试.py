"""
tests/test_scoring.py — 胡数计算与计分单元测试 (v3 查表法版)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scoring import ScoreCalculator, Meld
from core.card import Card
from core.melds import (
    CharType, Color, JingSubType, MeldType,
    RED_JING_CHARS, BLACK_JING_CHARS, JING_CHARS,
    CHAR_TYPE_MAP, CHAR_COLOR_MAP, CHAR_IS_JING,
)

def make_card(char, jing_sub_type=JingSubType.NONE, is_wild=False, card_id=0):
    if is_wild:
        return Card(id=card_id, char="赖", char_type=CharType.LAI, color=Color.RED,
                    is_jin=False, is_wild=True, is_flower=False)
    is_jin = CHAR_IS_JING.get(char, False)
    is_flower = (jing_sub_type == JingSubType.FLOWER)
    return Card(id=card_id, char=char, char_type=CHAR_TYPE_MAP[char],
                color=CHAR_COLOR_MAP[char], is_jin=is_jin, is_wild=False, is_flower=is_flower)

def make_jing_cards(char, hua_count=0, pi_count=0, wild_count=0):
    cards = []
    cid = 0
    for _ in range(hua_count):
        cards.append(make_card(char, JingSubType.FLOWER, card_id=cid)); cid += 1
    for _ in range(pi_count):
        cards.append(make_card(char, JingSubType.SKIN, card_id=cid)); cid += 1
    for _ in range(wild_count):
        cards.append(make_card("赖", is_wild=True, card_id=cid)); cid += 1
    return tuple(cards)

def make_meld(cards, meld_type):
    return Meld(meld_type=meld_type, cards=tuple(cards))

class TestMeldData:
    def test_meld_creation(self):
        cards = (make_card("上", card_id=0), make_card("大", card_id=1), make_card("人", card_id=2))
        meld = Meld(meld_type=MeldType.SEQUENCE, cards=cards)
        assert meld.meld_type == MeldType.SEQUENCE
        assert len(meld.cards) == 3
        assert meld.char == "上"

    def test_meld_all_chars(self):
        cards = (make_card("三", card_id=0), make_card("三", card_id=1), make_card("三", card_id=2))
        meld = Meld(meld_type=MeldType.KAN, cards=cards)
        assert meld.all_chars == ["三", "三", "三"]

class TestSequenceHu:
    def test_red_sequence_base_1(self):
        cards = (make_card("上", 0), make_card("大", 1), make_card("人", 2))
        chars = tuple(c.char for c in cards)
        assert ScoreCalculator().calc_sequence_hu(cards, chars) == 1

    def test_non_red_sequence_base_0(self):
        cards = (make_card("化", 0), make_card("三", 1), make_card("千", 2))
        chars = tuple(c.char for c in cards)
        assert ScoreCalculator().calc_sequence_hu(cards, chars) == 0

    def test_number_sequence_base_0(self):
        cards = (make_card("二", 0), make_card("三", 1), make_card("四", 2))
        chars = tuple(c.char for c in cards)
        assert ScoreCalculator().calc_sequence_hu(cards, chars) == 0

class TestPairHu:
    def test_non_jing_pair_0(self):
        assert ScoreCalculator().calc_pair_hu((make_card("上",0), make_card("上",1))) == 0
    def test_black_non_jing_pair_0(self):
        assert ScoreCalculator().calc_pair_hu((make_card("化",0), make_card("化",1))) == 0
    def test_red_jing_pair_2hua(self):
        assert ScoreCalculator().calc_pair_hu(make_jing_cards("三", hua_count=2)) == 4
    def test_red_jing_pair_1hua_1pi(self):
        assert ScoreCalculator().calc_pair_hu(make_jing_cards("三", hua_count=1, pi_count=1)) == 3
    def test_red_jing_pair_2pi(self):
        assert ScoreCalculator().calc_pair_hu(make_jing_cards("三", pi_count=2)) == 2
    def test_black_jing_pair_2hua(self):
        assert ScoreCalculator().calc_pair_hu(make_jing_cards("乙", hua_count=2)) == 2
    def test_black_jing_pair_1hua_1pi(self):
        assert ScoreCalculator().calc_pair_hu(make_jing_cards("乙", hua_count=1, pi_count=1)) == 1
    def test_black_jing_pair_2pi(self):
        assert ScoreCalculator().calc_pair_hu(make_jing_cards("乙", pi_count=2)) == 0
    def test_main_jin_pair_double(self):
        assert ScoreCalculator().calc_pair_hu(make_jing_cards("三", hua_count=2), is_main_jin=True) == 8

class TestKanHu:
    def test_red_non_jing_kan(self):
        assert ScoreCalculator().calc_kan_hu(tuple(make_card("上", i) for i in range(3))) == 2
    def test_black_non_jing_kan(self):
        assert ScoreCalculator().calc_kan_hu(tuple(make_card("化", i) for i in range(3))) == 1
    def test_red_jing_kan_3pi(self):
        assert ScoreCalculator().calc_kan_hu(make_jing_cards("三", pi_count=3)) == 5
    def test_red_jing_kan_2pi_1hua(self):
        assert ScoreCalculator().calc_kan_hu(make_jing_cards("三", hua_count=1, pi_count=2)) == 6
    def test_red_jing_kan_1pi_2hua(self):
        assert ScoreCalculator().calc_kan_hu(make_jing_cards("三", hua_count=2, pi_count=1)) == 7
    def test_black_jing_kan_3pi(self):
        assert ScoreCalculator().calc_kan_hu(make_jing_cards("乙", pi_count=3)) == 1
    def test_black_jing_kan_2pi_1hua(self):
        assert ScoreCalculator().calc_kan_hu(make_jing_cards("乙", hua_count=1, pi_count=2)) == 2
    def test_red_jing_kan_with_wild(self):
        assert ScoreCalculator().calc_kan_hu(make_jing_cards("三", hua_count=1, wild_count=2)) == 12
    def test_red_jing_kan_main_jin_double(self):
        assert ScoreCalculator().calc_kan_hu(make_jing_cards("三", hua_count=2, pi_count=1), is_main_jin=True) == 14

class TestZhaoHu:
    def test_red_jing_zhao_3pi_1hua(self):
        assert ScoreCalculator().calc_zhao_hu(make_jing_cards("三", hua_count=1, pi_count=3)) == 12
    def test_red_jing_zhao_2pi_2hua(self):
        assert ScoreCalculator().calc_zhao_hu(make_jing_cards("三", hua_count=2, pi_count=2)) == 14
    def test_red_non_jing_zhao(self):
        assert ScoreCalculator().calc_zhao_hu(tuple(make_card("上", i) for i in range(4))) == 4
    def test_black_jing_zhao_3pi_1hua(self):
        assert ScoreCalculator().calc_zhao_hu(make_jing_cards("乙", hua_count=1, pi_count=3)) == 3

class TestZhaHu:
    def test_red_non_jing_zha(self):
        assert ScoreCalculator().calc_zha_hu(tuple(make_card("上", i) for i in range(4))) == 4
    def test_black_non_jing_zha(self):
        assert ScoreCalculator().calc_zha_hu(tuple(make_card("化", i) for i in range(4))) == 2
    def test_red_jing_zha_3pi_1hua(self):
        assert ScoreCalculator().calc_zha_hu(make_jing_cards("三", hua_count=1, pi_count=3)) == 12
    def test_red_jing_zha_2pi_2hua(self):
        assert ScoreCalculator().calc_zha_hu(make_jing_cards("三", hua_count=2, pi_count=2)) == 14

class TestChuanFanHu:
    def test_red_non_jing_chuan(self):
        assert ScoreCalculator().calc_chuan_hu(tuple(make_card("上", i) for i in range(5))) == 5
    def test_black_non_jing_chuan(self):
        assert ScoreCalculator().calc_chuan_hu(tuple(make_card("化", i) for i in range(5))) == 3
    def test_red_jing_fan(self):
        assert ScoreCalculator().calc_fan_hu(make_jing_cards("三", hua_count=2, pi_count=3)) == 28
    def test_black_jing_fan(self):
        assert ScoreCalculator().calc_fan_hu(make_jing_cards("乙", hua_count=2, pi_count=3)) == 6
    def test_red_jing_chuan_with_wild(self):
        assert ScoreCalculator().calc_chuan_hu(make_jing_cards("七", hua_count=2, pi_count=1, wild_count=2)) == 48
    def test_red_jing_chuan_main_jin_double(self):
        assert ScoreCalculator().calc_chuan_hu(make_jing_cards("七", hua_count=2, pi_count=1, wild_count=2), is_main_jin=True) == 96

class TestPenHu:
    def test_red_pen(self):
        assert ScoreCalculator().calc_pen_hu(tuple(make_card("上", i) for i in range(3))) == 1
    def test_black_pen(self):
        assert ScoreCalculator().calc_pen_hu(tuple(make_card("化", i) for i in range(3))) == 0
    def test_pen_with_jing_bonus(self):
        cards = (make_card("可", 0), make_card("可", 1), make_card("三", JingSubType.FLOWER, 2))
        assert ScoreCalculator().calc_pen_hu(cards) == 2

class TestMainJinDouble:
    def test_main_jin_doubles_pair(self):
        cards = make_jing_cards("三", hua_count=2)
        assert ScoreCalculator().calc_pair_hu(cards, is_main_jin=True) == ScoreCalculator().calc_pair_hu(cards) * 2
    def test_main_jin_doubles_kan(self):
        cards = make_jing_cards("五", hua_count=2, pi_count=1)
        assert ScoreCalculator().calc_kan_hu(cards, is_main_jin=True) == ScoreCalculator().calc_kan_hu(cards) * 2
    def test_main_jin_doubles_chuan(self):
        cards = make_jing_cards("七", hua_count=2, pi_count=1, wild_count=2)
        assert ScoreCalculator().calc_chuan_hu(cards, is_main_jin=True) == ScoreCalculator().calc_chuan_hu(cards) * 2

class TestWildCard:
    def test_wild_as_red_skin_in_kan(self):
        cards = (make_card("三", JingSubType.SKIN, 0), make_card("三", JingSubType.SKIN, 1), make_card("赖", is_wild=True, card_id=2))
        assert ScoreCalculator().calc_kan_hu(cards) == 5
    def test_wild_pair(self):
        assert ScoreCalculator().calc_pair_hu((make_card("赖", is_wild=True, 0), make_card("赖", is_wild=True, 1))) == 4
    def test_wild_pair_main_jin(self):
        assert ScoreCalculator().calc_pair_hu((make_card("赖", is_wild=True, 0), make_card("赖", is_wild=True, 1)), is_main_jin=True) == 8

class TestCalculateHandHu:
    def test_multiple_melds(self):
        scorer = ScoreCalculator()
        cid = [0]
        def mc(char):
            c = make_card(char, card_id=cid[0]); cid[0] += 1; return c
        melds = [
            make_meld([mc("上"), mc("大"), mc("人")], MeldType.SEQUENCE),
            make_meld([mc("可"), mc("知"), mc("礼")], MeldType.SEQUENCE),
            make_meld([mc("化"), mc("三"), mc("千")], MeldType.SEQUENCE),
            make_meld([mc("孔"), mc("乙"), mc("已")], MeldType.SEQUENCE),
            make_meld([mc("二"), mc("三"), mc("四")], MeldType.SEQUENCE),
            make_meld([mc("上"), mc("上")], MeldType.PAIR),
        ]
        total = scorer.calculate_hand_hu(melds)
        assert total == 2, f"expected 2, got {total}"

class TestRealHand2:
    def test_hand2(self):
        cid = [0]
        def mk(char, flower=False):
            c = make_card(char, JingSubType.FLOWER if flower else JingSubType.NONE, card_id=cid[0]); cid[0] += 1; return c
        scorer = ScoreCalculator()
        melds = [
            Meld(MeldType.ZHA, (mk("上"), mk("上"), mk("上"), mk("上"))),
            Meld(MeldType.PEN, (mk("可"), mk("可"), mk("可"))),
            Meld(MeldType.CHUAN, (mk("七"), mk("七", True), mk("七", True), mk("赖"), mk("赖"))),
            Meld(MeldType.PAIR, (mk("三"), mk("三", True))),
            Meld(MeldType.PAIR, (mk("乙"), mk("乙", True))),
        ]
        total = scorer.calculate_hand_hu(melds, main_jin="七")
        assert total == 105, f"expected 105, got {total}"

class TestRealHand3:
    def test_hand3(self):
        cid = [0]
        def mk(char, flower=False):
            c = make_card(char, JingSubType.FLOWER if flower else JingSubType.NONE, card_id=cid[0]); cid[0] += 1; return c
        scorer = ScoreCalculator()
        melds = [
            Meld(MeldType.CHUAN, (mk("乙"), mk("乙"), mk("乙", True), mk("乙", True), mk("乙"))),
            Meld(MeldType.ZHAO, (mk("可"), mk("可"), mk("可"), mk("可"))),
            Meld(MeldType.SEQUENCE, (mk("上"), mk("大"), mk("人"))),
            Meld(MeldType.SEQUENCE, (mk("化"), mk("三", True), mk("千"))),
            Meld(MeldType.SEQUENCE, (mk("孔"), mk("乙"), mk("已"))),
            Meld(MeldType.KAN, (mk("五", True), mk("五", True), mk("赖"))),
            Meld(MeldType.SEQUENCE, (mk("六"), mk("七"), mk("八"))),
            Meld(MeldType.SEQUENCE, (mk("八"), mk("九", True), mk("子"))),
        ]
        total = scorer.calculate_hand_hu(melds, main_jin="五")
        assert total == 33, f"expected 33, got {total}"

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
