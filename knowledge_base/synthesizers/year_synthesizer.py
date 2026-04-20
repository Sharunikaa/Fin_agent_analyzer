"""
Year Synthesizer: Generate per-year sector knowledge files
"""

import logging
from typing import Dict
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

from knowledge_base.config import PER_YEAR_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def synthesize_year_knowledge(
    year: int,
    companies_data: Dict[str, Dict]  # {company: {kpis, risks, promises, sentiment}}
) -> str:
    """
    Generate per-year sector knowledge file comparing all companies.
    
    Args:
        year: Fiscal year
        companies_data: Dictionary mapping companies to their extracted data
        
    Returns:
        Markdown content
    """
    
    md = f"# {year} Sector Knowledge Base\n\n"
    md += f"**Companies Covered**: {', '.join(sorted(companies_data.keys()))}\n\n"
    
    # Performance Ranking
    md += "## Revenue Ranking\n\n"
    revenues = {}
    for company, data in companies_data.items():
        if 'kpis' in data:
            rev = data['kpis'].get('revenue', {}).get('value')
            if rev:
                revenues[company] = rev
    
    if revenues:
        md += "| Rank | Company | Revenue ($M) |\n"
        md += "|------|---------|-------------|\n"
        for rank, (company, rev) in enumerate(sorted(revenues.items(), key=lambda x: -x[1]), 1):
            md += f"| {rank} | {company} | {rev:,.0f} |\n"
        md += "\n"
    
    # Cross-Company Risk Comparison
    md += "## Risk Landscape\n\n"
    risk_summary = {}
    for company, data in companies_data.items():
        if 'risks' in data:
            risks = data['risks'].get('risks', [])
            for risk in risks:
                category = risk.get('category', 'other')
                if category not in risk_summary:
                    risk_summary[category] = []
                risk_summary[category].append({
                    'company': company,
                    'severity': risk.get('severity', 'medium'),
                    'description': risk.get('description', '')
                })
    
    for category in sorted(risk_summary.keys()):
        risks_in_cat = risk_summary[category]
        high_risks = [r for r in risks_in_cat if r['severity'] in ['high', 'critical']]
        
        if high_risks:
            md += f"### {category.title()}\n"
            for risk in high_risks:
                md += f"- **{risk['company']}**: {risk['description']}\n"
            md += "\n"
    
    # Sentiment Snapshot
    md += "## Market Sentiment\n\n"
    for company in sorted(companies_data.keys()):
        if 'sentiment' in companies_data[company]:
            sentiment = companies_data[company]['sentiment']
            md += f"- **{company}**: {sentiment.get('overall_sentiment', 'neutral').upper()}\n"
    
    md += "\n"
    
    # Sector Themes
    md += "## Common Themes\n\n"
    all_risks = []
    for company, data in companies_data.items():
        if 'risks' in data:
            all_risks.extend(data['risks'].get('risks', []))
    
    if all_risks:
        # Find most common risk categories
        categories = {}
        for risk in all_risks:
            cat = risk.get('category', 'other')
            categories[cat] = categories.get(cat, 0) + 1
        
        md += "### Top Risk Categories\n"
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            md += f"- {cat.title()}: {count} mentions\n"
        md += "\n"
    
    return md


def save_year_knowledge(year: int, content: str):
    """Save year knowledge file."""
    output_path = PER_YEAR_DIR / f"{year}_sector_knowledge.md"
    
    with open(output_path, 'w') as f:
        f.write(content)
    
    logger.info(f"✅ Saved year knowledge: {output_path}")
    return output_path


if __name__ == "__main__":
    # Test
    test_data = {
        "AMD": {
            'kpis': {'revenue': {'value': 16434}},
            'risks': {'risks': [{'category': 'competitive', 'severity': 'high', 'description': 'Intel competition'}]},
            'sentiment': {'overall_sentiment': 'optimistic'}
        },
        "NVIDIA": {
            'kpis': {'revenue': {'value': 26914}},
            'risks': {'risks': [{'category': 'competitive', 'severity': 'high', 'description': 'AMD competition'}]},
            'sentiment': {'overall_sentiment': 'optimistic'}
        }
    }
    
    content = synthesize_year_knowledge(2021, test_data)
    print(content)
