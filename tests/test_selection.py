"""W1.4 selection-chain unit tests (pure logic — no data needed)."""
import pandas as pd

from echo_frb.repro.selection.funnel_literal import _classify, _spikes_ms
from echo_frb.repro.selection.reconcile import divergence_stage
from echo_frb.repro.selection.factorial import attribute


def test_classify_candidate():
    blk = ("[23/340] 处理 FRB20190131D\n"
           "FRB20190131D: 检测到自相关尖峰，尖峰时间 (ms): [np.float64(8.82)]\n"
           "FRB20190131D: 分析完成，已保存图片和报告至 Figures/\n")
    assert _classify(blk) == "CANDIDATE"
    assert _spikes_ms(blk) == [8.82]


def test_classify_no_spike():
    assert _classify("[1/340] 处理 FRBX\nFRBX: 无自相关尖峰，排除透镜候选\n") == "NO_SPIKE"


def test_classify_drift():
    blk = ("检测到自相关尖峰\n  所有匹配峰对均存在严重频率漂移，排除透镜候选\n")
    assert _classify(blk) == "DRIFT"


def test_classify_cuts():
    assert _classify("峰对 (76, 84) 的后峰 SNR=9.62 < 10，排除") == "CUT_PSNR"
    assert _classify("峰对 (73, 80) 的 SNR 顺序错误：前峰...") == "CUT_ORDER"
    assert _classify("匹配到的峰对中没有包含最高SNR的峰，排除") == "CUT_MAXSNR"


def test_classify_no_match():
    assert _classify("检测到自相关尖峰\n  未匹配到峰对，使用检测到的 5 个峰值") == "NO_MATCH"


def test_divergence_stage():
    assert divergence_stage("CANDIDATE", "CANDIDATE") is None      # agree
    assert divergence_stage("CANDIDATE", "NO_SPIKE") == "SPIKE"    # part at spike
    assert divergence_stage("NO_MATCH", "NO_SPIKE") == "SPIKE"
    assert divergence_stage("DRIFT", "CUTS") == "CUTS"
    assert divergence_stage("CANDIDATE", "DRIFT") == "DRIFT"


def _grid(ll, lc, cl, cc):
    return pd.DataFrame([
        dict(frb_name="F", cell="LClit_ACFlit", near_expected=ll),
        dict(frb_name="F", cell="LClit_ACFcr", near_expected=lc),
        dict(frb_name="F", cell="LCcr_ACFlit", near_expected=cl),
        dict(frb_name="F", cell="LCcr_ACFcr", near_expected=cc),
    ])


def test_attribute_algorithm():
    # detector flips (ACFlit True, ACFcr False); LC irrelevant -> ALGORITHM
    assert attribute(_grid(True, False, True, False)).cause.iloc[0] == "ALGORITHM"


def test_attribute_preprocessing():
    # LC flips (LClit True, LCcr False); detector irrelevant -> PREPROCESSING
    assert attribute(_grid(True, True, False, False)).cause.iloc[0] == "PREPROCESSING"


def test_attribute_mixed_and_agree():
    assert attribute(_grid(True, False, False, False)).cause.iloc[0] == "MIXED"
    assert attribute(_grid(True, True, True, True)).cause.iloc[0] == "AGREE"
