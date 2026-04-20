"""
Anomaly Detector: Detect financial anomalies and red flags
"""

import json
import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def detect_anomalies(
    kpis_current: Dict,
    kpis_prior: Optional[Dict] = None,
    company_name: str = None
) -> Dict:
    """
    Detect financial anomalies by comparing current vs prior year metrics.
    
    Args:
        kpis_current: Current year KPIs
        kpis_prior: Prior year KPIs (optional)
        company_name: Company name
        
    Returns:
        Dict with detected anomalies
    """
    
    anomalies = []
    
    # Handle missing/null KPI data
    if not kpis_current:
        logger.warning("No current year KPI data provided - skipping anomaly detection")
        return {
            'company': company_name,
            'fiscal_year': None,
            'anomalies': [],
            'detection_metadata': {'reason': 'no_kpi_data', 'error': 'kpis_current_is_null'}
        }
    
    if not kpis_prior:
        logger.warning("No prior year data provided - skipping anomaly detection")
        return {
            'company': company_name,
            'fiscal_year': kpis_current.get('fiscal_year'),
            'anomalies': [],
            'detection_metadata': {'reason': 'no_prior_year_data'}
        }
    
    # Extract values
    rev_curr = _get_value(kpis_current, 'revenue')
    rev_prior = _get_value(kpis_prior, 'revenue')
    
    ni_curr = _get_value(kpis_current, 'net_income')
    ni_prior = _get_value(kpis_prior, 'net_income')
    
    gm_curr = _get_value(kpis_current, 'gross_margin_pct')
    gm_prior = _get_value(kpis_prior, 'gross_margin_pct')
    
    fcf_curr = _get_value(kpis_current, 'free_cash_flow')
    fcf_prior = _get_value(kpis_prior, 'free_cash_flow')
    
    # Check 1: Margin compression
    if gm_curr is not None and gm_prior is not None:
        margin_delta = gm_curr - gm_prior
        if margin_delta < -300:  # 300+ bps compression
            anomalies.append({
                'type': 'margin_compression',
                'description': f'Gross margin declined from {gm_prior}% to {gm_curr}%',
                'magnitude': f'{abs(margin_delta):.0f} bps',
                'severity': 'high' if margin_delta < -500 else 'medium',
                'prior_value': gm_prior,
                'current_value': gm_curr
            })
    
    # Check 2: Revenue decline with profit decline (worse ratio = issue)
    if rev_curr is not None and rev_prior is not None and ni_curr is not None and ni_prior is not None:
        if rev_prior > 0 and ni_prior > 0:
            rev_growth = ((rev_curr - rev_prior) / rev_prior) * 100
            ni_growth = ((ni_curr - ni_prior) / ni_prior) * 100
            
            if ni_growth < rev_growth - 20:  # Net income growing much slower than revenue
                anomalies.append({
                    'type': 'profit_deterioration',
                    'description': f'Net income growth ({ni_growth:.1f}%) lagging revenue growth ({rev_growth:.1f}%)',
                    'magnitude': f'{abs(ni_growth - rev_growth):.1f}% gap',
                    'severity': 'medium',
                    'prior_ni': ni_prior,
                    'current_ni': ni_curr
                })
    
    # Check 3: Cash flow divergence from earnings
    if fcf_curr is not None and fcf_prior is not None and ni_curr is not None:
        if abs(fcf_curr - ni_curr) / max(abs(ni_curr), 1) > 0.5:  # FCF differs from NI by >50%
            anomalies.append({
                'type': 'fcf_ni_divergence',
                'description': f'Free cash flow diverging from net income (FCF: ${fcf_curr}M, NI: ${ni_curr}M)',
                'magnitude': f'{abs(fcf_curr - ni_curr):.0f}M gap',
                'severity': 'medium',
                'fcf': fcf_curr,
                'net_income': ni_curr
            })
    
    logger.info(f"✅ Detected {len(anomalies)} anomalies for {company_name}")
    
    return {
        'company': company_name,
        'fiscal_year': kpis_current.get('fiscal_year'),
        'anomalies': anomalies,
        'detection_metadata': {
            'total_checks': 3,
            'anomalies_found': len(anomalies),
            'success': True
        }
    }


def _get_value(kpis: Dict, key: str) -> Optional[float]:
    """Safely extract numeric value from KPIs dict."""
    try:
        if key in kpis:
            val = kpis[key]
            if isinstance(val, dict):
                return float(val.get('value'))
            else:
                return float(val)
    except (TypeError, ValueError):
        pass
    return None


if __name__ == "__main__":
    # Test
    kpis_2021 = {
        'fiscal_year': 2021,
        'revenue': {'value': 16434},
        'net_income': {'value': 3161},
        'gross_margin_pct': {'value': 47}
    }
    
    kpis_2020 = {
        'fiscal_year': 2020,
        'revenue': {'value': 9763},
        'net_income': {'value': 2491},
        'gross_margin_pct': {'value': 45}
    }
    
    result = detect_anomalies(kpis_2021, kpis_2020, "AMD")
    print(json.dumps(result, indent=2))
