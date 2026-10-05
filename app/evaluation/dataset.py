"""
RAG Evaluation dataset for BantenPedia (PRD §27).

Each entry contains:
  - query:    The user question.
  - expected: Keywords / phrases that should appear in the retrieved content.
  - notes:    Context about what a good retrieval should contain.
"""

EVALUATION_DATASET: list[dict] = [
    {
        "id": "eval-001",
        "query": "Apa itu Canang Sari?",
        "expected_keywords": ["canang", "sari", "persembahan"],
        "notes": "Should retrieve description of Canang Sari.",
    },
    {
        "id": "eval-002",
        "query": "Apa makna Canang Sari?",
        "expected_keywords": ["makna", "canang", "sari"],
        "notes": "Should retrieve meaning/philosophy of Canang Sari.",
    },
    {
        "id": "eval-003",
        "query": "Apa komponen Banten Pejati?",
        "expected_keywords": ["pejati", "komponen"],
        "notes": "Should list components of Banten Pejati.",
    },
    {
        "id": "eval-004",
        "query": "Bagaimana fungsi Banten Pejati?",
        "expected_keywords": ["pejati", "fungsi"],
        "notes": "Should describe the ceremonial function of Banten Pejati.",
    },
    {
        "id": "eval-005",
        "query": "Apa perbedaan banten di Bali Utara dan Bali Selatan?",
        "expected_keywords": ["utara", "selatan", "bali"],
        "notes": "Should surface regional variation information.",
    },
    {
        "id": "eval-006",
        "query": "Apa itu porosan?",
        "expected_keywords": ["porosan"],
        "notes": "Should retrieve description of porosan component.",
    },
    {
        "id": "eval-007",
        "query": "Apa itu sampian?",
        "expected_keywords": ["sampian"],
        "notes": "Should retrieve description of sampian component.",
    },
    {
        "id": "eval-008",
        "query": "Apa banten yang digunakan dalam upacara manusa yadnya?",
        "expected_keywords": ["manusa", "yadnya"],
        "notes": "Should list banten used in manusa yadnya ceremonies.",
    },
]
