"""Configuration for Contract Review Tool."""
 
import os
from functools import lru_cache
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)


class Config:
    """Application configuration loaded from environment or config file."""

    # Ollama settings
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3:8b"

    # LLM parameters
    LLM_TEMPERATURE: float = 0.1
    LLM_NUM_CTX: int = 4096
    LLM_NUM_PREDICT: int = 2048
    LLM_REASONING: bool = False

    # Legacy upload limit fields kept only for backward compatibility.
    MAX_PDF_SIZE: int = 2 * 1024 * 1024
    MAX_DOCX_SIZE: int = 5 * 1024 * 1024
    MAX_PDF_PAGES: int = 20

    # Logging
    LOG_LEVEL: str = "DEBUG"

    # Local persistence
    DOCUMENT_STORE_PATH: str = str(Path(__file__).resolve().parents[1] / "data" / "documents.json")

    # RAG - Postgres/pgvector
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/contract_rag"
    VECTOR_DIM: int = 1024  # bge-large-zh-v1.5 default dim; keep configurable

    # RAG - Embedding model
    EMBEDDING_MODEL: str = "BAAI/bge-large-zh-v1.5"

    # RAG - Chunking
    CHUNK_SIZE_CHARS: int = 900
    CHUNK_OVERLAP_CHARS: int = 150
    RETRIEVER_TOP_K: int = 8
    HYBRID_RRF_K: int = 60
    COARSE_RECALL_MULT: int = 6
    COARSE_RECALL_MAX_PER_QUERY: int = 24
    RETRIEVAL_FILTER_MIN_CHARS: int = 80

    # RAG — cross-encoder rerank
    RERANK_MODEL: str = "BAAI/bge-reranker-base"
    RERANK_BATCH_SIZE: int = 8
    RERANK_POOL_MULT: int = 4

    # Agent guardrails thresholds
    AGENT_GUARD_MIN_CONFIDENCE: float = 0.12
    AGENT_GUARD_MAX_TOOL_INPUT_CHARS: int = 12000
    AGENT_MAX_TOOL_CALLS: int = 64

    # Agent loop limits
    AGENT_MAX_RETRIEVAL_ROUNDS: int = 4
    AGENT_MAX_REFINE_ROUNDS: int = 2
    AGENT_MAX_GENERATION_RETRIES: int = 2
    AGENT_MAX_LOOP_STEPS: int = 28
    AGENT_MAX_REPLAN_ROUNDS: int = 2
    AGENT_MIN_DECIDER_CONFIDENCE: float = 0.35
    AGENT_MAX_IDENTICAL_ACTION_REPEATS: int = 3

    # Agent reflection thresholds
    AGENT_REFLECTION_SCORE_THRESHOLD: float = 0.55
    AGENT_SELF_CORRECTION_MAX: int = 2

    # Agent v5 step-failure replan threshold
    AGENT_V5_STEP_FAIL_REPLAN_THRESHOLD: int = 3

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls()

        if os.getenv("OLLAMA_HOST"):
            config.OLLAMA_HOST = os.getenv("OLLAMA_HOST")
        if os.getenv("OLLAMA_MODEL"):
            config.OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
        if os.getenv("LLM_TEMPERATURE"):
            config.LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE"))
        if os.getenv("LLM_NUM_CTX"):
            config.LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX"))
        if os.getenv("LLM_NUM_PREDICT"):
            config.LLM_NUM_PREDICT = int(os.getenv("LLM_NUM_PREDICT"))
        if os.getenv("LLM_REASONING"):
            config.LLM_REASONING = os.getenv("LLM_REASONING").lower() in ("true", "1", "yes")
        if os.getenv("LOG_LEVEL"):
            config.LOG_LEVEL = os.getenv("LOG_LEVEL")
        if os.getenv("DOCUMENT_STORE_PATH"):
            config.DOCUMENT_STORE_PATH = os.getenv("DOCUMENT_STORE_PATH")

        if os.getenv("DATABASE_URL"):
            config.DATABASE_URL = os.getenv("DATABASE_URL")
        if os.getenv("VECTOR_DIM"):
            config.VECTOR_DIM = int(os.getenv("VECTOR_DIM"))

        if os.getenv("EMBEDDING_MODEL"):
            config.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

        if os.getenv("CHUNK_SIZE_CHARS"):
            config.CHUNK_SIZE_CHARS = int(os.getenv("CHUNK_SIZE_CHARS"))
        if os.getenv("CHUNK_OVERLAP_CHARS"):
            config.CHUNK_OVERLAP_CHARS = int(os.getenv("CHUNK_OVERLAP_CHARS"))
        if os.getenv("RETRIEVER_TOP_K"):
            config.RETRIEVER_TOP_K = int(os.getenv("RETRIEVER_TOP_K"))
        if os.getenv("HYBRID_RRF_K"):
            config.HYBRID_RRF_K = int(os.getenv("HYBRID_RRF_K"))
        if os.getenv("COARSE_RECALL_MULT"):
            config.COARSE_RECALL_MULT = int(os.getenv("COARSE_RECALL_MULT"))
        if os.getenv("COARSE_RECALL_MAX_PER_QUERY"):
            config.COARSE_RECALL_MAX_PER_QUERY = int(os.getenv("COARSE_RECALL_MAX_PER_QUERY"))
        if os.getenv("RETRIEVAL_FILTER_MIN_CHARS"):
            config.RETRIEVAL_FILTER_MIN_CHARS = int(os.getenv("RETRIEVAL_FILTER_MIN_CHARS"))

        if os.getenv("RERANK_MODEL"):
            config.RERANK_MODEL = os.getenv("RERANK_MODEL", "").strip()
        if os.getenv("RERANK_BATCH_SIZE"):
            config.RERANK_BATCH_SIZE = int(os.getenv("RERANK_BATCH_SIZE"))
        if os.getenv("RERANK_POOL_MULT"):
            config.RERANK_POOL_MULT = int(os.getenv("RERANK_POOL_MULT"))

        if os.getenv("AGENT_GUARD_MIN_CONFIDENCE"):
            config.AGENT_GUARD_MIN_CONFIDENCE = float(os.getenv("AGENT_GUARD_MIN_CONFIDENCE"))
        if os.getenv("AGENT_GUARD_MAX_TOOL_INPUT_CHARS"):
            config.AGENT_GUARD_MAX_TOOL_INPUT_CHARS = int(os.getenv("AGENT_GUARD_MAX_TOOL_INPUT_CHARS"))
        if os.getenv("AGENT_MAX_TOOL_CALLS"):
            config.AGENT_MAX_TOOL_CALLS = int(os.getenv("AGENT_MAX_TOOL_CALLS"))

        if os.getenv("AGENT_MAX_RETRIEVAL_ROUNDS"):
            config.AGENT_MAX_RETRIEVAL_ROUNDS = int(os.getenv("AGENT_MAX_RETRIEVAL_ROUNDS"))
        if os.getenv("AGENT_MAX_REFINE_ROUNDS"):
            config.AGENT_MAX_REFINE_ROUNDS = int(os.getenv("AGENT_MAX_REFINE_ROUNDS"))
        if os.getenv("AGENT_MAX_GENERATION_RETRIES"):
            config.AGENT_MAX_GENERATION_RETRIES = int(os.getenv("AGENT_MAX_GENERATION_RETRIES"))
        if os.getenv("AGENT_MAX_LOOP_STEPS"):
            config.AGENT_MAX_LOOP_STEPS = int(os.getenv("AGENT_MAX_LOOP_STEPS"))
        if os.getenv("AGENT_MAX_REPLAN_ROUNDS"):
            config.AGENT_MAX_REPLAN_ROUNDS = int(os.getenv("AGENT_MAX_REPLAN_ROUNDS"))
        if os.getenv("AGENT_MIN_DECIDER_CONFIDENCE"):
            config.AGENT_MIN_DECIDER_CONFIDENCE = float(os.getenv("AGENT_MIN_DECIDER_CONFIDENCE"))
        if os.getenv("AGENT_MAX_IDENTICAL_ACTION_REPEATS"):
            config.AGENT_MAX_IDENTICAL_ACTION_REPEATS = int(os.getenv("AGENT_MAX_IDENTICAL_ACTION_REPEATS"))
        if os.getenv("AGENT_REFLECTION_SCORE_THRESHOLD"):
            config.AGENT_REFLECTION_SCORE_THRESHOLD = float(os.getenv("AGENT_REFLECTION_SCORE_THRESHOLD"))
        if os.getenv("AGENT_SELF_CORRECTION_MAX"):
            config.AGENT_SELF_CORRECTION_MAX = int(os.getenv("AGENT_SELF_CORRECTION_MAX"))
        if os.getenv("AGENT_V5_STEP_FAIL_REPLAN_THRESHOLD"):
            config.AGENT_V5_STEP_FAIL_REPLAN_THRESHOLD = int(os.getenv("AGENT_V5_STEP_FAIL_REPLAN_THRESHOLD"))

        return config


@lru_cache()
def get_config() -> Config:
    """Get cached configuration instance."""
    return Config.load()


# Convenience accessors
def get_ollama_host() -> str:
    return get_config().OLLAMA_HOST


def get_ollama_model() -> str:
    return get_config().OLLAMA_MODEL


def get_llm_temperature() -> float:
    return get_config().LLM_TEMPERATURE


def get_llm_num_ctx() -> int:
    return get_config().LLM_NUM_CTX


def get_llm_num_predict() -> int:
    return get_config().LLM_NUM_PREDICT


def get_llm_reasoning() -> bool:
    return get_config().LLM_REASONING


def get_log_level() -> str:
    return get_config().LOG_LEVEL


def get_document_store_path() -> Path:
    return Path(get_config().DOCUMENT_STORE_PATH)


def get_database_url() -> str:
    return get_config().DATABASE_URL


def get_vector_dim() -> int:
    return get_config().VECTOR_DIM


def get_embedding_model() -> str:
    return get_config().EMBEDDING_MODEL


def get_chunk_size_chars() -> int:
    return get_config().CHUNK_SIZE_CHARS


def get_chunk_overlap_chars() -> int:
    return get_config().CHUNK_OVERLAP_CHARS


def get_retriever_top_k() -> int:
    return get_config().RETRIEVER_TOP_K


def get_hybrid_rrf_k() -> int:
    return get_config().HYBRID_RRF_K


def get_coarse_recall_mult() -> int:
    return get_config().COARSE_RECALL_MULT


def get_coarse_recall_max_per_query() -> int:
    return get_config().COARSE_RECALL_MAX_PER_QUERY


def get_retrieval_filter_min_chars() -> int:
    return get_config().RETRIEVAL_FILTER_MIN_CHARS


def get_rerank_model() -> str:
    return get_config().RERANK_MODEL


def get_rerank_batch_size() -> int:
    return get_config().RERANK_BATCH_SIZE


def get_rerank_pool_mult() -> int:
    return get_config().RERANK_POOL_MULT


def get_agent_guard_min_confidence() -> float:
    return get_config().AGENT_GUARD_MIN_CONFIDENCE


def get_agent_guard_max_tool_input_chars() -> int:
    return get_config().AGENT_GUARD_MAX_TOOL_INPUT_CHARS


def get_agent_max_tool_calls() -> int:
    return get_config().AGENT_MAX_TOOL_CALLS


def get_agent_max_retrieval_rounds() -> int:
    return get_config().AGENT_MAX_RETRIEVAL_ROUNDS


def get_agent_max_refine_rounds() -> int:
    return get_config().AGENT_MAX_REFINE_ROUNDS


def get_agent_max_generation_retries() -> int:
    return get_config().AGENT_MAX_GENERATION_RETRIES


def get_agent_max_loop_steps() -> int:
    return get_config().AGENT_MAX_LOOP_STEPS


def get_agent_max_replan_rounds() -> int:
    return get_config().AGENT_MAX_REPLAN_ROUNDS


def get_agent_min_decider_confidence() -> float:
    return get_config().AGENT_MIN_DECIDER_CONFIDENCE


def get_agent_max_identical_action_repeats() -> int:
    return get_config().AGENT_MAX_IDENTICAL_ACTION_REPEATS


def get_agent_reflection_score_threshold() -> float:
    return get_config().AGENT_REFLECTION_SCORE_THRESHOLD


def get_agent_self_correction_max() -> int:
    return get_config().AGENT_SELF_CORRECTION_MAX


def get_agent_v5_step_fail_replan_threshold() -> int:
    return get_config().AGENT_V5_STEP_FAIL_REPLAN_THRESHOLD
