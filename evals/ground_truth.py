"""
Ground Truth Dataset: Known correct answers for evaluation
"""

import json
from pathlib import Path
from typing import Dict, List
from config import GROUND_TRUTH_DIR


# Ground Truth Dataset
GROUND_TRUTH_DATASET = [
    # Factual Retrieval
    {
        "id": "gt_001",
        "category": "factual_retrieval",
        "query": "What is AMD's revenue in 2021?",
        "expected_answer": {
            "revenue": 16434.0,  # $16.434 billion
            "unit": "millions",
            "year": 2021,
            "company": "AMD",
        },
        "expected_sources": ["AMD_2021_10K"],
        "difficulty": "easy",
    },
    {
        "id": "gt_002",
        "category": "factual_retrieval",
        "query": "What is Apple's gross margin in 2022?",
        "expected_answer": {
            "gross_margin": 43.3,  # Approximate
            "unit": "percentage",
            "year": 2022,
            "company": "APPLE",
        },
        "expected_sources": ["APPLE_2022_10K"],
        "difficulty": "easy",
    },
    
    # Trend Analysis
    {
        "id": "gt_003",
        "category": "trend_analysis",
        "query": "Show me AMD revenue trend from 2020 to 2021",
        "expected_answer": {
            "values": [9763.0, 16434.0],
            "years": [2020, 2021],
            "growth_rate": 68.3,  # Approximate
            "trend": "upward",
        },
        "expected_sources": ["AMD_2020_10K", "AMD_2021_10K"],
        "difficulty": "medium",
    },
    {
        "id": "gt_004",
        "category": "trend_analysis",
        "query": "Calculate AMD's revenue CAGR from 2019 to 2021",
        "expected_answer": {
            "cagr": 55.0,  # Approximate
            "start_year": 2019,
            "end_year": 2021,
            "trend": "strong growth",
        },
        "expected_sources": ["AMD_2019_10K", "AMD_2020_10K", "AMD_2021_10K"],
        "difficulty": "medium",
    },
    
    # Comparison
    {
        "id": "gt_005",
        "category": "comparison",
        "query": "Compare AMD vs Intel revenue in 2021",
        "expected_answer": {
            "amd_revenue": 16434.0,
            "intel_revenue": 79000.0,  # Approximate
            "leader": "Intel",
            "ratio": 4.8,  # Intel is ~4.8x larger
        },
        "expected_sources": ["AMD_2021_10K", "INTEL_2021_10K"],
        "difficulty": "hard",
    },
    
    # Semantic Search
    {
        "id": "gt_006",
        "category": "semantic_search",
        "query": "What are AMD's main risk factors?",
        "expected_answer": {
            "risk_categories": [
                "supply chain",
                "competition",
                "technology",
                "market demand",
                "intellectual property",
            ],
            "section_type": "risk_factors",
        },
        "expected_sources": ["AMD_2021_10K"],
        "difficulty": "medium",
    },
    {
        "id": "gt_007",
        "category": "semantic_search",
        "query": "Explain Microsoft's cloud strategy",
        "expected_answer": {
            "topics": [
                "Azure",
                "cloud computing",
                "enterprise",
                "hybrid cloud",
            ],
            "section_type": "business_overview",
        },
        "expected_sources": ["MICROSOFT_2017_10K"],
        "difficulty": "hard",
    },
    
    # Complex Queries
    {
        "id": "gt_008",
        "category": "trend_analysis",
        "query": "How did AMD's gross margin change from 2020 to 2021?",
        "expected_answer": {
            "margin_2020": 45.0,  # Approximate
            "margin_2021": 48.3,  # Approximate
            "change": 3.3,
            "trend": "improved",
        },
        "expected_sources": ["AMD_2020_10K", "AMD_2021_10K"],
        "difficulty": "medium",
    },
    {
        "id": "gt_009",
        "category": "factual_retrieval",
        "query": "What is Netflix's subscriber count in 2020?",
        "expected_answer": {
            "subscribers": 203.7,  # Approximate (millions)
            "unit": "millions",
            "year": 2020,
            "company": "NETFLIX",
        },
        "expected_sources": ["NETFLIX_2020_10K"],
        "difficulty": "easy",
    },
    {
        "id": "gt_010",
        "category": "comparison",
        "query": "Which company had higher revenue growth: AMD or Apple?",
        "expected_answer": {
            "amd_growth": 68.3,  # 2020-2021
            "apple_growth": 33.0,  # Approximate
            "leader": "AMD",
        },
        "expected_sources": ["AMD_2021_10K", "APPLE_2022_10K"],
        "difficulty": "hard",
    },
]


def save_ground_truth():
    """Save ground truth dataset to JSON file."""
    output_path = GROUND_TRUTH_DIR / "ground_truth_dataset.json"
    
    with open(output_path, 'w') as f:
        json.dump(GROUND_TRUTH_DATASET, f, indent=2)
    
    print(f"✅ Saved {len(GROUND_TRUTH_DATASET)} ground truth examples to {output_path}")
    
    # Statistics
    categories = {}
    difficulties = {}
    
    for item in GROUND_TRUTH_DATASET:
        cat = item['category']
        diff = item['difficulty']
        
        categories[cat] = categories.get(cat, 0) + 1
        difficulties[diff] = difficulties.get(diff, 0) + 1
    
    print(f"\n📊 Ground Truth Statistics:")
    print(f"   Total: {len(GROUND_TRUTH_DATASET)}")
    print(f"   Categories: {categories}")
    print(f"   Difficulties: {difficulties}")


def load_ground_truth() -> List[Dict]:
    """Load ground truth dataset from JSON file."""
    input_path = GROUND_TRUTH_DIR / "ground_truth_dataset.json"
    
    if input_path.exists():
        with open(input_path) as f:
            return json.load(f)
    else:
        return GROUND_TRUTH_DATASET


def get_ground_truth_by_category(category: str) -> List[Dict]:
    """Get ground truth examples for a specific category."""
    dataset = load_ground_truth()
    return [item for item in dataset if item['category'] == category]


def get_ground_truth_by_difficulty(difficulty: str) -> List[Dict]:
    """Get ground truth examples by difficulty level."""
    dataset = load_ground_truth()
    return [item for item in dataset if item['difficulty'] == difficulty]


if __name__ == "__main__":
    save_ground_truth()
    
    # Test loading
    dataset = load_ground_truth()
    print(f"\n✅ Loaded {len(dataset)} ground truth examples")
    
    # Show sample
    print(f"\n📋 Sample Ground Truth:")
    sample = dataset[0]
    print(f"   ID: {sample['id']}")
    print(f"   Category: {sample['category']}")
    print(f"   Query: {sample['query']}")
    print(f"   Expected: {sample['expected_answer']}")
