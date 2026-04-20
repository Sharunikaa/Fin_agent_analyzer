"""
Master Synthesizer: Generate master sector knowledge file
"""

import logging
from typing import Dict
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

from knowledge_base.config import MASTER_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def synthesize_master_knowledge(all_data: Dict) -> str:
    """
    Generate master sector knowledge file across all companies and years.
    
    Args:
        all_data: {company: {year: {kpis, risks, promises, sentiment}}}
        
    Returns:
        Markdown content
    """
    
    md = "# Master Financial Knowledge Base\n\n"
    
    companies = sorted(all_data.keys())
    years = set()
    for company_data in all_data.values():
        years.update(company_data.keys())
    years = sorted(years)
    
    md += f"**Coverage**: {companies}\n"
    md += f"**Period**: {years[0]}-{years[-1]}\n\n"
    
    # Executive Summary
    md += "## Executive Summary\n\n"
    md += f"- **Companies**: {len(companies)}\n"
    md += f"- **Years**: {len(years)}\n"
    md += f"- **Total Documents**: ~{len(companies) * len(years)}\n\n"
    
    # Key Insights by Company
    md += "## Company Profiles\n\n"
    for company in companies:
        company_years = sorted(all_data[company].keys())
        
        md += f"### {company}\n"
        md += f"**Years**: {company_years[0]}-{company_years[-1]}\n\n"
        
        # Latest KPIs
        latest_year = company_years[-1]
        if 'kpis' in all_data[company][latest_year]:
            kpis = all_data[company][latest_year]['kpis']
            rev = kpis.get('revenue', {}).get('value', 'N/A')
            ni = kpis.get('net_income', {}).get('value', 'N/A')
            md += f"**{latest_year}**: Revenue ${rev}M | Net Income ${ni}M\n\n"
        
        # Top risks
        all_company_risks = []
        for year_data in all_data[company].values():
            if 'risks' in year_data:
                all_company_risks.extend(year_data['risks'].get('risks', []))
        
        high_risks = [r for r in all_company_risks if r.get('severity') in ['high', 'critical']]
        if high_risks:
            md += f"**Top Risks**: "
            md += " | ".join([r.get('category', '?') for r in high_risks[:3]])
            md += "\n\n"
    
    # Sector Trends
    md += "## Sector Trends\n\n"
    
    # Growth analysis
    md += "### Revenue Growth\n"
    for company in companies:
        company_years = sorted(all_data[company].keys())
        if len(company_years) >= 2:
            year1 = company_years[0]
            year2 = company_years[-1]
            
            rev1 = all_data[company][year1].get('kpis', {}).get('revenue', {}).get('value')
            rev2 = all_data[company][year2].get('kpis', {}).get('revenue', {}).get('value')
            
            if rev1 and rev2:
                growth = ((rev2 - rev1) / rev1) * 100
                md += f"- {company}: {growth:+.1f}% ({year1}-{year2})\n"
    
    md += "\n"
    
    # Risk themes
    md += "### Industry Risk Themes\n"
    all_risk_categories = {}
    for company_data in all_data.values():
        for year_data in company_data.values():
            if 'risks' in year_data:
                for risk in year_data['risks'].get('risks', []):
                    cat = risk.get('category', 'other')
                    all_risk_categories[cat] = all_risk_categories.get(cat, 0) + 1
    
    for cat, count in sorted(all_risk_categories.items(), key=lambda x: -x[1])[:5]:
        md += f"- {cat.title()}: {count} mentions\n"
    
    md += "\n"
    
    # Guidance Summary
    md += "### Management Guidance\n"
    total_promises = 0
    quantified = 0
    for company_data in all_data.values():
        for year_data in company_data.values():
            if 'promises' in year_data:
                promises = year_data['promises'].get('promises', [])
                total_promises += len(promises)
                quantified += sum(1 for p in promises if p.get('is_quantified'))
    
    md += f"- Total Promises Extracted: {total_promises}\n"
    md += f"- Quantified Targets: {quantified}\n"
    md += f"- Quantification Rate: {(quantified/total_promises*100) if total_promises else 0:.0f}%\n\n"
    
    return md


def save_master_knowledge(content: str):
    """Save master knowledge file."""
    output_path = MASTER_DIR / "sector_knowledge.md"
    
    with open(output_path, 'w') as f:
        f.write(content)
    
    logger.info(f"✅ Saved master knowledge: {output_path}")
    return output_path


if __name__ == "__main__":
    # Test
    test_data = {
        "AMD": {
            2021: {
                'kpis': {'revenue': {'value': 16434}},
                'risks': {'risks': [{'category': 'competitive', 'severity': 'high'}]},
                'promises': {'promises': [{'text': '50% margin', 'is_quantified': True}]},
            }
        }
    }
    
    content = synthesize_master_knowledge(test_data)
    print(content)
