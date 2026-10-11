"""EvidenceRAG runtime defaults, established before native libraries are imported."""
import os

# FAISS and PyTorch can load separate OpenMP runtimes on macOS. The default
# multithreaded combination crashed in validation; a single thread passed the
# same reproduction. Also appropriate for this small, serial local workload.
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
