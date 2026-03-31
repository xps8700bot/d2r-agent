import pytest
from d2r_agent.orchestrator import answer

def test_mechanics_countess():
    query = "女伯爵 掉落 符文"
    result_text, _ = answer(query)
    assert "Countess" in result_text or "女伯爵" in result_text
    assert "Lo" in result_text or "Ist" in result_text
    assert "Rune" in result_text or "符文" in result_text

def test_mechanics_andariel():
    query = "安达利尔 弱点"
    result_text, _ = answer(query)
    assert "Andariel" in result_text or "安达利尔" in result_text
    assert "Fire" in result_text or "火" in result_text
    assert "-50%" in result_text

def test_mechanics_mephisto():
    query = "墨菲斯托 卡位"
    result_text, _ = answer(query)
    assert "Mephisto" in result_text or "墨菲斯托" in result_text
    assert "Moat Trick" in result_text or "卡位" in result_text

def test_mechanics_baal_exp():
    query = "90级 巴尔 经验"
    result_text, _ = answer(query)
    assert "Baal" in result_text or "巴尔" in result_text
    assert "90" in result_text or "experience" in result_text or "经验" in result_text

def test_mechanics_nihlathak_ce():
    query = "尼拉萨克 尸体爆炸"
    result_text, _ = answer(query)
    assert "Nihlathak" in result_text or "尼拉萨克" in result_text
    assert "Corpse Explosion" in result_text or "尸体爆炸" in result_text
    assert "50% physical" in result_text or "物理" in result_text

def test_mechanics_pindleskin_drops():
    query = "皮叔 掉落 等级"
    result_text, _ = answer(query)
    assert "Pindleskin" in result_text or "皮叔" in result_text
    assert "TC87" in result_text or "87" in result_text
    assert "Arachnid Mesh" in result_text or "Azurewrath" in result_text or "Tyrael's Might" in result_text

def test_mechanics_cow_king_portal():
    query = "杀了 奶牛王 还能开红门吗"
    result_text, _ = answer(query)
    assert "Cow King" in result_text or "奶牛王" in result_text
    assert "D2R" in result_text or "no longer prevents" in result_text or "不再" in result_text

def test_mechanics_shenk_death():
    query = "山克 死亡 投石车"
    result_text, _ = answer(query)
    assert "Shenk" in result_text or "山克" in result_text
    assert "catapult" in result_text or "投石车" in result_text or "bombardment" in result_text
