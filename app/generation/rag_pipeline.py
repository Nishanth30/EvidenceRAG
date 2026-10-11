import json
import re
from pydantic import BaseModel, ConfigDict, ValidationError
from typing import Literal
from app.errors import AppError
from app.generation.prompt_builder import build_context
from app.schemas.responses import AnswerResponse


class ModelAnswer(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')
    status: Literal['answered', 'insufficient_evidence']
    answer: str
    citations: list[str]


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate response key')
        result[key] = value
    return result


class RAGPipeline:
    def __init__(self, retriever, llm, settings):
        self.retriever, self.llm, self.settings = retriever, llm, settings

    def ask(self, question, top_k=None):
        retrieval = self.retriever.search(question, top_k)
        passages = [p for p in retrieval.results if p.score >= self.settings.similarity_threshold]
        messages, sources = build_context(question, passages, self.settings.max_context_chars)

        def abstain():
            return AnswerResponse(answer='The available documents do not provide sufficient evidence to answer this question.',
                                  status='insufficient_evidence', sources=sources)

        def error(code, message):
            return AnswerResponse(answer=message, status='error', error_code=code, sources=sources)

        if not sources:
            return abstain()
        if not self.llm.configured:
            return error('llm_unavailable', 'Answer generation is unavailable. Configure an LLM provider; semantic search is ready.')
        try:
            raw = self.llm.generate(messages)
        except AppError:
            return error('llm_unavailable', 'The LLM request failed. Please check the provider and try again.')
        try:
            result = ModelAnswer.model_validate(json.loads(raw, object_pairs_hook=unique_object))
            if result.status == 'insufficient_evidence':
                # Contradictory text or citations must not be silently accepted.
                if result.answer != '' or result.citations:
                    raise ValueError('Ambiguous abstention')
                return abstain()
            if not result.answer.strip():
                raise ValueError('Empty answer')
        except (ValueError, TypeError, ValidationError):
            return error('invalid_model_response', 'The model response was withheld because it did not follow the response contract.')
        answer = result.answer
        cited = list(dict.fromkeys(re.findall(r'\[(S\d+)\]', answer)))
        allowed = {s.source_id for s in sources}
        brackets = re.findall(r'\[([^\[\]\n]*)\]', answer)
        malformed = any(re.search(r'\bS\d+', item) and item not in allowed for item in brackets)
        if (malformed or not result.citations or not set(result.citations).issubset(allowed)
                or (cited and set(cited) != set(result.citations))
                or len(result.citations) != len(set(result.citations))):
            return error('invalid_citations', 'The model response was withheld because it did not contain valid source citations.')
        return AnswerResponse(answer=answer, status='answered', sources=sources, cited_source_ids=result.citations,
                              warning='Citations identify retrieved passages; factual support is not automatically verified.')
