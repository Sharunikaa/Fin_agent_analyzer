"""
Signal Extraction: Extract structured signals from text
"""

import re
from typing import Dict, List, Set
from config import SIGNAL_PATTERNS, NER_PATTERNS


def extract_risk_markers(text: str) -> List[Dict]:
    """
    Extract risk markers from text.
    
    Args:
        text: Input text
        
    Returns:
        markers: List of risk marker dicts with position and text
    """
    markers = []
    
    for pattern in SIGNAL_PATTERNS['risk_markers']:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            markers.append({
                'type': 'risk_marker',
                'text': match.group(),
                'start': match.start(),
                'end': match.end(),
                'pattern': pattern,
            })
    
    return markers


def extract_commitments(text: str) -> List[Dict]:
    """
    Extract commitment keywords from text.
    
    Args:
        text: Input text
        
    Returns:
        commitments: List of commitment dicts
    """
    commitments = []
    
    for pattern in SIGNAL_PATTERNS['commitment_keywords']:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            # Get surrounding context (50 chars before and after)
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end]
            
            commitments.append({
                'type': 'commitment',
                'text': match.group(),
                'context': context,
                'start': match.start(),
                'end': match.end(),
                'pattern': pattern,
            })
    
    return commitments


def extract_temporal_anchors(text: str) -> List[Dict]:
    """
    Extract temporal anchors (dates, fiscal years, quarters).
    
    Args:
        text: Input text
        
    Returns:
        anchors: List of temporal anchor dicts
    """
    anchors = []
    
    for pattern in SIGNAL_PATTERNS['temporal_anchors']:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            anchors.append({
                'type': 'temporal_anchor',
                'text': match.group(),
                'start': match.start(),
                'end': match.end(),
                'pattern': pattern,
            })
    
    return anchors


def extract_metric_mentions(text: str) -> List[Dict]:
    """
    Extract metric mentions (revenue increased, margin expanded, etc.).
    
    Args:
        text: Input text
        
    Returns:
        mentions: List of metric mention dicts
    """
    mentions = []
    
    for pattern in SIGNAL_PATTERNS['metric_mentions']:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            # Get surrounding context
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            context = text[start:end]
            
            mentions.append({
                'type': 'metric_mention',
                'text': match.group(),
                'context': context,
                'start': match.start(),
                'end': match.end(),
                'pattern': pattern,
            })
    
    return mentions


def extract_financial_amounts(text: str) -> List[Dict]:
    """
    Extract financial amounts ($5B, $100M, etc.).
    
    Args:
        text: Input text
        
    Returns:
        amounts: List of financial amount dicts
    """
    amounts = []
    
    for pattern in SIGNAL_PATTERNS['financial_amounts']:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            amount_text = match.group()
            
            # Parse amount
            parsed_amount = parse_financial_amount(amount_text)
            
            amounts.append({
                'type': 'financial_amount',
                'text': amount_text,
                'parsed_value': parsed_amount,
                'start': match.start(),
                'end': match.end(),
                'pattern': pattern,
            })
    
    return amounts


def parse_financial_amount(text: str) -> float:
    """
    Parse financial amount text to numeric value in millions.
    
    Args:
        text: Amount text (e.g., "$5.2B", "100 million dollars")
        
    Returns:
        value: Numeric value in millions
    """
    text = text.lower()
    
    # Extract number
    number_match = re.search(r'(\d+(?:\.\d+)?)', text)
    if not number_match:
        return 0.0
    
    number = float(number_match.group(1))
    
    # Determine multiplier
    if 'billion' in text or 'b' in text:
        multiplier = 1000  # Convert to millions
    elif 'million' in text or 'm' in text:
        multiplier = 1
    elif 'thousand' in text or 'k' in text:
        multiplier = 0.001
    else:
        multiplier = 1
    
    return number * multiplier


def extract_named_entities(text: str) -> List[Dict]:
    """
    Extract named entities (companies, people) using simple patterns.
    
    Args:
        text: Input text
        
    Returns:
        entities: List of named entity dicts
    """
    entities = []
    
    # Extract companies
    for pattern in NER_PATTERNS['companies']:
        for match in re.finditer(pattern, text):
            entities.append({
                'type': 'company',
                'text': match.group(),
                'start': match.start(),
                'end': match.end(),
            })
    
    # Extract people
    for pattern in NER_PATTERNS['people']:
        for match in re.finditer(pattern, text):
            entities.append({
                'type': 'person',
                'text': match.group(),
                'start': match.start(),
                'end': match.end(),
            })
    
    # Deduplicate
    seen = set()
    unique_entities = []
    for entity in entities:
        key = (entity['type'], entity['text'].lower())
        if key not in seen:
            seen.add(key)
            unique_entities.append(entity)
    
    return unique_entities


def extract_all_signals(text: str) -> Dict:
    """
    Extract all signals from text.
    
    Args:
        text: Input text
        
    Returns:
        signals: Dict with all signal types
    """
    signals = {
        'risk_markers': extract_risk_markers(text),
        'commitments': extract_commitments(text),
        'temporal_anchors': extract_temporal_anchors(text),
        'metric_mentions': extract_metric_mentions(text),
        'financial_amounts': extract_financial_amounts(text),
        'named_entities': extract_named_entities(text),
    }
    
    # Add summary stats
    signals['summary'] = {
        'total_signals': sum(len(v) for v in signals.values() if isinstance(v, list)),
        'risk_marker_count': len(signals['risk_markers']),
        'commitment_count': len(signals['commitments']),
        'temporal_anchor_count': len(signals['temporal_anchors']),
        'metric_mention_count': len(signals['metric_mentions']),
        'financial_amount_count': len(signals['financial_amounts']),
        'named_entity_count': len(signals['named_entities']),
    }
    
    return signals


def extract_signals_from_chunk(chunk: Dict) -> Dict:
    """
    Extract signals from a chunk and add to chunk metadata.
    
    Args:
        chunk: Chunk dict with 'text' field
        
    Returns:
        chunk_with_signals: Chunk with 'signals' field added
    """
    text = chunk.get('text', '')
    signals = extract_all_signals(text)
    
    chunk['signals'] = signals
    
    return chunk


def get_signal_statistics(chunks_with_signals: List[Dict]) -> Dict:
    """
    Get statistics on signals across all chunks.
    
    Args:
        chunks_with_signals: Chunks with 'signals' field
        
    Returns:
        stats: Dict with aggregate statistics
    """
    total_signals = 0
    signal_counts = {
        'risk_markers': 0,
        'commitments': 0,
        'temporal_anchors': 0,
        'metric_mentions': 0,
        'financial_amounts': 0,
        'named_entities': 0,
    }
    
    for chunk in chunks_with_signals:
        signals = chunk.get('signals', {})
        summary = signals.get('summary', {})
        
        total_signals += summary.get('total_signals', 0)
        
        for key in signal_counts.keys():
            signal_counts[key] += summary.get(f'{key.replace("_", "_")}_count', 0)
    
    stats = {
        'total_chunks': len(chunks_with_signals),
        'total_signals': total_signals,
        'avg_signals_per_chunk': total_signals / len(chunks_with_signals) if chunks_with_signals else 0,
        'signal_counts': signal_counts,
    }
    
    return stats


if __name__ == "__main__":
    # Test signal extraction
    test_text = """
    We face material risks related to supply chain disruptions. Revenue increased 123% to $16.4 billion in fiscal year 2021.
    We plan to expand our manufacturing capacity by 2025. Intel and NVIDIA are significant competitors.
    Our CEO, Lisa Su, expects continued growth in Q4 2021.
    """
    
    signals = extract_all_signals(test_text)
    
    print("Signal Extraction Results:")
    print(f"\n  Risk Markers ({len(signals['risk_markers'])}):")
    for marker in signals['risk_markers']:
        print(f"    - {marker['text']}")
    
    print(f"\n  Commitments ({len(signals['commitments'])}):")
    for commit in signals['commitments']:
        print(f"    - {commit['text']}")
    
    print(f"\n  Temporal Anchors ({len(signals['temporal_anchors'])}):")
    for anchor in signals['temporal_anchors']:
        print(f"    - {anchor['text']}")
    
    print(f"\n  Metric Mentions ({len(signals['metric_mentions'])}):")
    for mention in signals['metric_mentions']:
        print(f"    - {mention['text']}")
    
    print(f"\n  Financial Amounts ({len(signals['financial_amounts'])}):")
    for amount in signals['financial_amounts']:
        print(f"    - {amount['text']} → ${amount['parsed_value']:.1f}M")
    
    print(f"\n  Named Entities ({len(signals['named_entities'])}):")
    for entity in signals['named_entities']:
        print(f"    - {entity['text']} ({entity['type']})")
    
    print(f"\n  Total Signals: {signals['summary']['total_signals']}")
