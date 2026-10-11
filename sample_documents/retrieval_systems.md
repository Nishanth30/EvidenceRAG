# Retrieval Systems

## Embeddings

Normalized embeddings have unit length, so their inner product equals cosine similarity.

A text encoder maps queries and passages to numerical vectors in the same embedding space. Similar meaning can be retrieved even when the wording differs. Semantic similarity is not a calibrated probability that a proposed answer is correct. Model choice, domain vocabulary and input truncation all influence retrieval quality.

## Chunking

Chunk overlap preserves nearby context at boundaries but increases storage and duplicate retrieval.

Small chunks can focus on one fact while omitting information needed to interpret it. Larger chunks offer more context but may dilute a specific topic and exceed the encoder input length. Paragraph-aware splitting attempts to preserve logical boundaries. Measure both retrieval quality and the resulting number of chunks rather than assuming one size is always superior.

## Recall

Recall at k is the fraction of labeled relevant evidence units found among the first k retrieved results.

If a question requires two independent pieces of evidence and only one is retrieved, its evidence recall is one half. Average per-question recall over answerable questions and state the relevance definition. Hit rate asks only whether any relevant result appears; it is a different measure for questions with several evidence units. Unanswerable questions require a separate rejection measure.

## Reciprocal rank

Reciprocal rank is one divided by the rank of the first relevant result, or zero when none is retrieved.

Mean reciprocal rank averages this quantity across questions. A relevant passage in position one contributes one; a first hit in position four contributes one quarter. A cutoff must be stated when retrieval is truncated. Retrieval evaluation diagnoses the evidence selection stage separately from answer generation, whose faithfulness needs additional assessment.

