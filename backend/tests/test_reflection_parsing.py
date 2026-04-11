from src.agents.reflection import _parse_reflection_payload, _parse_self_critic_payload


def test_parse_reflection_payload_accepts_non_json_key_value_text() -> None:
    raw = """
    score: 0.78
    missing: 终止, 付款
    feedback: 当前分析较完整，但需要补充终止条款。
    should_refine: false
    """

    data = _parse_reflection_payload(raw)

    assert data["score"] == 0.78
    assert data["missing"] == ["终止", "付款"]
    assert data["should_refine"] is False
    assert "补充终止条款" in data["feedback"]


def test_parse_self_critic_payload_accepts_non_json_key_value_text() -> None:
    raw = """
    is_correct: true
    confidence: 0.83
    critique: 风险识别基本可靠。
    fix_plan: 补充终止条款引用。
    """

    data = _parse_self_critic_payload(raw)

    assert data["is_correct"] is True
    assert data["confidence"] == 0.83
    assert "基本可靠" in data["critique"]
    assert "终止条款引用" in data["fix_plan"]
