from src.services.prompt_builder_service import RetrievedContext, build_analysis_user_prompt
from src.services.prompt_service import get_perspective_prompt
from src.models.analysis import PerspectiveType


def test_prompt_builder_keeps_literal_json_braces() -> None:
    template = get_perspective_prompt(PerspectiveType.PARTY_A)

    prompt = build_analysis_user_prompt(
        system_prompt_template=template,
        contract_text="这是合同正文",
        retrieved_contexts=None,
    )

    assert "这是合同正文" in prompt
    assert '"risks"' in prompt


def test_prompt_builder_includes_rag_context_without_formatting_error() -> None:
    template = get_perspective_prompt(PerspectiveType.PARTY_B)

    prompt = build_analysis_user_prompt(
        system_prompt_template=template,
        contract_text="合同全文",
        retrieved_contexts=[
            RetrievedContext(chunk_id="chunk-1", content="付款条款应在30日内支付", score=0.81),
        ],
    )

    assert "chunk-1" in prompt
    assert "付款条款应在30日内支付" in prompt
    assert '"risks"' in prompt
