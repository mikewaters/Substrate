import hashlib
import re
import uuid
from collections import Counter

from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from sqlalchemy import select

from ontologizer.relational.models import Topic as TopicORM
from ontologizer.relational.repository.classifier import TopicSuggestionRepository
from ontologizer.schema.classifier import (
    TopicSuggestionRequest,
    TopicSuggestionResponse,
    TopicSuggestionResult,
)

# Constants for this classifier backend
TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
MODEL_NAME = "simple-keyword-matcher"
MODEL_VERSION = "0.1.0"


class TopicSuggestionService(SQLAlchemyAsyncRepositoryService[TopicORM]):
    """Provide lightweight topic suggestions based on keyword overlap."""

    repository_type = TopicSuggestionRepository

    # @dual_mode
    async def suggest_topics(
        self, request: TopicSuggestionRequest
    ) -> TopicSuggestionResponse:
        """Suggest topics for the provided text input.

        1. Tokenize the input topic proposal to be classified
        2. Retrieve corpus of all active topics in the given taxonomy, tokenize and cache them
        3. Score each topic in the corpus for matching input topic proposal
        4. Filter list by threshold confidence

        Enhanced features:
        - Phrase matching (bi-grams and tri-grams)
        - Title-specific boosting
        - Matched phrase extraction for highlighting
        """

        normalized_text = request.text.strip()
        if not normalized_text:
            raise ValueError("Input text cannot be empty.")

        input_tokens = self._tokenize(normalized_text)
        if not input_tokens:
            # No tokens after normalization -> return empty suggestions
            return TopicSuggestionResponse(
                input_text=request.text,
                suggestions=[],
                model_name=MODEL_NAME,
                model_version=MODEL_VERSION,
            )

        stmt = (
            select(TopicORM)
            .where(
                TopicORM.taxonomy_id == request.taxonomy_id, TopicORM.status == "active"
            )
            .order_by(TopicORM.title.asc())
        )

        topics = (await self.repository.session.execute(stmt)).scalars().all()

        if not topics:
            return TopicSuggestionResponse(
                input_text=request.text,
                suggestions=[],
                model_name=MODEL_NAME,
                model_version=MODEL_VERSION,
            )

        # Generate bi-grams and tri-grams from input for phrase matching
        input_bigrams = self._generate_ngrams(input_tokens, 2)
        input_trigrams = self._generate_ngrams(input_tokens, 3)

        input_counts = Counter(input_tokens)
        input_total = sum(input_counts.values())

        scored = []
        token_cache: dict[uuid.UUID, Counter[str]] = {}
        phrase_cache: dict[uuid.UUID, tuple[list[str], list[str]]] = {}

        for topic in topics:
            topic_tokens = self._topic_tokens(topic)
            if not topic_tokens:
                continue

            # Generate topic phrases
            topic_bigrams = self._generate_ngrams(topic_tokens, 2)
            topic_trigrams = self._generate_ngrams(topic_tokens, 3)
            phrase_cache[topic.id] = (topic_bigrams, topic_trigrams)

            topic_counts = Counter(topic_tokens)
            token_cache[topic.id] = topic_counts

            # Calculate token overlap
            token_overlap = sum((input_counts & topic_counts).values())

            # Calculate phrase overlap (weighted more heavily)
            bigram_matches = len(set(input_bigrams) & set(topic_bigrams))
            trigram_matches = len(set(input_trigrams) & set(topic_trigrams))

            # Combined score with phrase weighting
            phrase_score = bigram_matches * 2 + trigram_matches * 3
            total_score = token_overlap + phrase_score

            if total_score == 0:
                continue

            # Calculate precision and recall
            topic_total = sum(topic_counts.values())
            precision = (
                total_score / (input_total + len(input_bigrams) + len(input_trigrams))
                if (input_total + len(input_bigrams) + len(input_trigrams))
                else 0.0
            )
            recall = (
                total_score / (topic_total + len(topic_bigrams) + len(topic_trigrams))
                if (topic_total + len(topic_bigrams) + len(topic_trigrams))
                else 0.0
            )

            # Title boost: if input text matches topic title closely, boost confidence
            title_tokens = self._tokenize(topic.title)
            title_overlap = sum((input_counts & Counter(title_tokens)).values())
            title_boost = (
                min(0.2, title_overlap / len(title_tokens)) if title_tokens else 0.0
            )

            score = self._harmonic_mean(precision, recall) + title_boost
            score = min(1.0, score)  # Cap at 1.0

            scored.append((topic, score, bigram_matches, trigram_matches))

        if not scored:
            return TopicSuggestionResponse(
                input_text=request.text,
                suggestions=[],
                model_name=MODEL_NAME,
                model_version=MODEL_VERSION,
            )

        scored.sort(key=lambda item: item[1], reverse=True)

        filtered = [item for item in scored if item[1] >= request.min_confidence]
        limited = filtered[: request.limit]

        suggestions: list[TopicSuggestionResult] = []
        input_hash = hashlib.sha256(normalized_text.lower().encode("utf-8")).hexdigest()

        for rank, (topic, score, bigram_matches, trigram_matches) in enumerate(
            limited, start=1
        ):
            topic_counts = token_cache.get(topic.id)
            if topic_counts is None:
                topic_counts = Counter(self._topic_tokens(topic))

            # Extract matched tokens
            matched_tokens = list((input_counts & topic_counts).elements())

            # Extract matched phrases
            topic_bigrams, topic_trigrams = phrase_cache.get(topic.id, ([], []))
            matched_bigrams = list(set(input_bigrams) & set(topic_bigrams))
            matched_trigrams = list(set(input_trigrams) & set(topic_trigrams))

            metadata = {
                "matched_terms": sorted(set(matched_tokens)),
                "matched_phrases": sorted(matched_bigrams + matched_trigrams),
            }

            data = dict(
                input_text=normalized_text,
                input_hash=input_hash,
                taxonomy_id=request.taxonomy_id,
                topic_id=topic.id,
                confidence=score,
                rank=rank,
                metadata=metadata,
                model_name=MODEL_NAME,
                model_version=MODEL_VERSION,
            )

            instance, _ = await self.repository.get_or_upsert(
                match_fields=["input_hash", "topic_id", "model_name", "model_version"],
                **data,
            )

            suggestions.append(
                TopicSuggestionResult(
                    topic_id=instance.topic_id,
                    taxonomy_id=instance.taxonomy_id,
                    title=topic.title,
                    slug=topic.slug,
                    confidence=instance.confidence,
                    rank=instance.rank,
                    metadata=instance.metadata,
                )
            )

        return TopicSuggestionResponse(
            input_text=request.text,
            suggestions=suggestions,
            model_name=MODEL_NAME,
            model_version=MODEL_VERSION,
        )

    # ==================== Internal Helpers ====================

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return TOKEN_PATTERN.findall(text.lower())

    def _topic_tokens(self, topic: TopicORM) -> list[str]:
        """Tokenize an entire topic instance, using the following
        properties:
            - title
            - description
            - aliases
        """
        fields: list[str] = [topic.title]
        if topic.description:
            fields.append(topic.description)
        if topic.aliases:
            fields.extend(topic.aliases)

        tokens: list[str] = []
        for value in fields:
            tokens.extend(self._tokenize(value))
        return tokens

    @staticmethod
    def _harmonic_mean(precision: float, recall: float) -> float:
        if precision == 0.0 or recall == 0.0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    @staticmethod
    def _generate_ngrams(tokens: list[str], n: int) -> list[str]:
        """Generate n-grams from a list of tokens.

        Args:
            tokens: List of tokens
            n: N-gram size (2 for bigrams, 3 for trigrams, etc.)

        Returns:
            List of n-grams as space-joined strings
        """
        if len(tokens) < n:
            return []
        return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
