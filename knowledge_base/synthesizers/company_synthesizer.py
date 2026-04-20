"""
Company Synthesizer: Generate per-company knowledge files
"""

import json
import logging
from typing import Dict, List
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

from knowledge_base.config import PER_COMPANY_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def synthesize_company_knowledge(
    company: str,
    years_data: Dict[int, Dict]  # {year: {kpis, risks, promises, sentiment}}
) -> str:
    """
    Generate comprehensive company knowledge file aggregating all years.
    
    Args:
        company: Company name
        years_data: Dictionary mapping years to their extracted data
        
    Returns:
        Markdown content
    """
    
    md = f"# {company} Financial Knowledge Base\n\n"
    
    # Summary
    years_sorted = sorted(years_data.keys())
    md += f"**Coverage**: {years_sorted[0]} - {years_sorted[-1]}\n\n"
    
    # Key Metrics Trend
    md += "## Key Metrics (YoY Trend)\n\n"
    md += "| Metric | " + " | ".join(str(y) for y in years_sorted) + " |\n"
    md += "|--------|" + "|".join(["---" for _ in years_sorted]) + "|\n"
    
    # Revenue trend
    revenues = []
    for year in years_sorted:
        if 'kpis' in years_data[year]:
            rev = years_data[year]['kpis'].get('revenue', {}).get('value', '-')
            revenues.append(str(rev) if rev != '-' else '-')
        else:
            revenues.append('-')
    md += f"| Revenue ($M) | {' | '.join(revenues)} |\n"
    
    # Net Income trend
    ni_list = []
    for year in years_sorted:
        if 'kpis' in years_data[year]:
            ni = years_data[year]['kpis'].get('net_income', {}).get('value', '-')
            ni_list.append(str(ni) if ni != '-' else '-')
        else:
            ni_list.append('-')
    md += f"| Net Income ($M) | {' | '.join(ni_list)} |\n"
    
    md += "\n"
    
    # Top Risks
    md += "## Material Risks\n\n"
    all_risks = []
    for year in years_sorted:
        if 'risks' in years_data[year]:
            all_risks.extend(years_data[year]['risks'].get('risks', []))
    
    # Group by category
    risk_categories = {}
    for risk in all_risks:
        cat = risk.get('category', 'other')
        if cat not in risk_categories:
            risk_categories[cat] = []
        risk_categories[cat].append(risk)
    
    for category in sorted(risk_categories.keys()):
        risks_in_cat = risk_categories[category]
        high_severity = [r for r in risks_in_cat if r.get('severity') == 'high' or r.get('severity') == 'critical']
        
        if high_severity:
            md += f"### {category.title()}\n"
            for risk in high_severity:
                md += f"- **{risk.get('severity', 'unknown').upper()}**: {risk.get('description', '')}\n"
            md += "\n"
    
    # Guidance & Targets
    md += "## Management Guidance & Targets\n\n"
    all_promises = []
    for year in years_sorted:
        if 'promises' in years_data[year]:
            all_promises.extend(years_data[year]['promises'].get('promises', []))
    
    for promise in all_promises:
        if promise.get('is_quantified'):
            md += f"- {promise.get('text', '')} (Target: {promise.get('target_year', 'TBD')})\n"
    
    md += "\n"
    
    # Sentiment Evolution
    md += "## Tone & Sentiment Evolution\n\n"
    for year in years_sorted:
        if 'sentiment' in years_data[year]:
            sentiment = years_data[year]['sentiment']
            md += f"**{year}**: {sentiment.get('overall_sentiment', 'neutral').upper()} - {sentiment.get('tone_summary', '')}\n"
    
    md += "\n"
    
    # Anomalies
    md += "## Notable Anomalies Detected\n\n"
    for year in years_sorted:
        if 'anomalies' in years_data[year]:
            anomalies = years_data[year]['anomalies'].get('anomalies', [])
            if anomalies:
                md += f"### {year}\n"
                for anomaly in anomalies:
                    md += f"- {anomaly.get('type', 'unknown').upper()}: {anomaly.get('description', '')} ({anomaly.get('magnitude', '')})\n"
                md += "\n"
    
    return md


def save_company_knowledge(company: str, content: str):
    """Save company knowledge file."""
    output_path = PER_COMPANY_DIR / f"{company}_knowledge.md"
    
    with open(output_path, 'w') as f:
        f.write(content)
    
    logger.info(f"✅ Saved company knowledge: {output_path}")
    return output_path


if __name__ == "__main__":
    # Test
    test_data = {
        2021: {
            'kpis': {
                'revenue': {'value': 16434},
                'net_income': {'value': 3161}
            },
            'risks': {
                'risks': [
                    {'category': 'competitive', 'description': 'Intel competition', 'severity': 'high'}
                ]
            },
            'promises': {
                'promises': [
                    {'text': '50% margin by 2025', 'target_year': 2025, 'is_quantified': True}
                ]
            },
            'sentiment': {
                'overall_sentiment': 'optimistic',
                'tone_summary': 'Strong growth narrative'
            }
        }
    }
    
    content = synthesize_company_knowledge("AMD", test_data)
    print(content)
