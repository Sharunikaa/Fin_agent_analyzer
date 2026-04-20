"""
Section Classification: Classify sections into 12 canonical types
"""

import re
from typing import Dict, List
from rapidfuzz import fuzz
from config import SECTION_TYPES


def classify_section(section: Dict, page_num: int = None) -> str:
    """
    Classify a section into one of 12 canonical types.
    
    Args:
        section: Section dict with 'text', 'level', 'page_start'
        page_num: Optional page number for context
        
    Returns:
        section_type: One of the 12 canonical types
    """
    text = section.get('text', '').lower()
    level = section.get('level', 0)
    page_start = section.get('page_start', page_num or 0)
    
    # Short sections are likely headers
    if len(text) < 50:
        return "header"
    
    # Check each section type in priority order
    for section_type, config in sorted(SECTION_TYPES.items(), key=lambda x: x[1]['priority']):
        # Check max pages constraint
        if 'max_pages' in config and page_start > config['max_pages']:
            continue
        
        # Check keywords
        keywords = config.get('keywords', [])
        exclude_keywords = config.get('exclude_keywords', [])
        
        # Check for exclude keywords first
        if any(kw in text for kw in exclude_keywords):
            continue
        
        # Check for include keywords
        if keywords:
            # For section types, check first 200 chars for better accuracy
            text_start = text[:200]
            
            if any(kw in text_start for kw in keywords):
                return section_type
    
    return "other"


def classify_section_enhanced(section: Dict, context: Dict = None) -> str:
    """
    Enhanced classification using context (previous sections, document structure).
    
    Args:
        section: Section dict
        context: Optional context dict with 'previous_sections', 'doc_metadata'
        
    Returns:
        section_type: Classified type
    """
    # Basic classification
    section_type = classify_section(section)
    
    # If "other", try to infer from context
    if section_type == "other" and context:
        previous_sections = context.get('previous_sections', [])
        
        # If previous section was "business_overview", this might be too
        if previous_sections and previous_sections[-1] == "business_overview":
            text = section.get('text', '').lower()
            # Check if it's a continuation (no "item" keyword)
            if 'item' not in text[:100]:
                return "business_overview"
        
        # If previous section was "risk_factors", this might be too
        if previous_sections and previous_sections[-1] == "risk_factors":
            text = section.get('text', '').lower()
            if 'item' not in text[:100] and len(text) > 200:
                return "risk_factors"
        
        # If previous section was "mda", this might be too
        if previous_sections and previous_sections[-1] == "mda":
            text = section.get('text', '').lower()
            if 'item' not in text[:100] and len(text) > 200:
                return "mda"
    
    return section_type


def classify_all_sections(sections: List[Dict], doc_metadata: Dict = None) -> List[Dict]:
    """
    Classify all sections in a document with context awareness.
    
    Args:
        sections: List of section dicts
        doc_metadata: Optional document metadata
        
    Returns:
        classified_sections: Sections with 'section_type' field added
    """
    classified_sections = []
    previous_types = []
    
    for i, section in enumerate(sections):
        context = {
            'previous_sections': previous_types[-5:],  # Last 5 sections
            'doc_metadata': doc_metadata,
            'section_index': i,
        }
        
        section_type = classify_section_enhanced(section, context)
        
        # Add classification to section
        section['section_type'] = section_type
        classified_sections.append(section)
        
        # Track for context
        previous_types.append(section_type)
    
    return classified_sections


def get_section_statistics(classified_sections: List[Dict]) -> Dict:
    """
    Get statistics on section classification.
    
    Args:
        classified_sections: Sections with 'section_type' field
        
    Returns:
        stats: Dict with counts and percentages
    """
    from collections import Counter
    
    section_types = [s['section_type'] for s in classified_sections]
    counts = Counter(section_types)
    total = len(section_types)
    
    stats = {
        'total_sections': total,
        'counts': dict(counts),
        'percentages': {k: (v / total) * 100 for k, v in counts.items()},
    }
    
    return stats


def validate_classification(classified_sections: List[Dict]) -> Dict:
    """
    Validate that classification makes sense.
    
    Args:
        classified_sections: Sections with 'section_type' field
        
    Returns:
        validation: Dict with warnings and issues
    """
    stats = get_section_statistics(classified_sections)
    counts = stats['counts']
    percentages = stats['percentages']
    
    warnings = []
    
    # Check if too many "other"
    if percentages.get('other', 0) > 50:
        warnings.append(f"⚠️  {percentages['other']:.1f}% sections classified as 'other' (>50%)")
    
    # Check if critical sections are present
    critical_sections = ['business_overview', 'risk_factors', 'mda', 'financial_statements']
    for section_type in critical_sections:
        if counts.get(section_type, 0) == 0:
            warnings.append(f"⚠️  No '{section_type}' sections found")
        elif counts.get(section_type, 0) < 3:
            warnings.append(f"⚠️  Only {counts[section_type]} '{section_type}' sections found (seems low)")
    
    return {
        'valid': len(warnings) == 0,
        'warnings': warnings,
        'stats': stats,
    }


if __name__ == "__main__":
    # Test classification
    test_sections = [
        {"text": "ITEM 1. BUSINESS", "level": 1, "page_start": 5},
        {"text": "ITEM 1A. RISK FACTORS", "level": 1, "page_start": 15},
        {"text": "ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS", "level": 1, "page_start": 30},
        {"text": "Our company operates in three segments...", "level": 2, "page_start": 6},
        {"text": "We face significant risks related to...", "level": 2, "page_start": 16},
    ]
    
    classified = classify_all_sections(test_sections)
    
    print("Classification Results:")
    for sec in classified:
        print(f"  {sec['section_type']:20s}: {sec['text'][:60]}...")
    
    validation = validate_classification(classified)
    print(f"\nValidation: {'✅ Valid' if validation['valid'] else '⚠️  Issues found'}")
    for warning in validation['warnings']:
        print(f"  {warning}")
