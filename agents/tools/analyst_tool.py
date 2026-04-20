"""
Analyst Tool: Perform financial calculations and analysis
"""

import json
from typing import Dict, List, Optional
from langchain_core.tools import Tool
import pandas as pd
import numpy as np


class AnalystTool:
    """Tool for financial analysis and calculations."""
    
    def calculate_growth_rate(self, values: List[float]) -> Dict:
        """
        Calculate growth rates from a series of values.
        
        Args:
            values: List of values (e.g., revenue over years)
            
        Returns:
            Growth analysis dict
        """
        if len(values) < 2:
            return {'error': 'Need at least 2 values for growth calculation'}
        
        # Year-over-year growth
        yoy_growth = []
        for i in range(1, len(values)):
            if values[i-1] != 0:
                growth = ((values[i] - values[i-1]) / values[i-1]) * 100
                yoy_growth.append(round(growth, 2))
            else:
                yoy_growth.append(None)
        
        # Compound annual growth rate (CAGR)
        if len(values) >= 2 and values[0] != 0:
            n = len(values) - 1
            cagr = (((values[-1] / values[0]) ** (1/n)) - 1) * 100
        else:
            cagr = None
        
        # Total growth
        if values[0] != 0:
            total_growth = ((values[-1] - values[0]) / values[0]) * 100
        else:
            total_growth = None
        
        return {
            'values': values,
            'yoy_growth': yoy_growth,
            'cagr': round(cagr, 2) if cagr else None,
            'total_growth': round(total_growth, 2) if total_growth else None,
            'trend': 'upward' if cagr and cagr > 0 else 'downward' if cagr and cagr < 0 else 'flat',
        }
    
    def calculate_margins(self, revenue: float, cost: float = None, profit: float = None) -> Dict:
        """
        Calculate profit margins.
        
        Args:
            revenue: Total revenue
            cost: Cost of revenue (optional)
            profit: Net profit (optional)
            
        Returns:
            Margin analysis dict
        """
        margins = {}
        
        if revenue == 0:
            return {'error': 'Revenue cannot be zero'}
        
        if cost is not None:
            gross_profit = revenue - cost
            gross_margin = (gross_profit / revenue) * 100
            margins['gross_profit'] = round(gross_profit, 2)
            margins['gross_margin_pct'] = round(gross_margin, 2)
        
        if profit is not None:
            net_margin = (profit / revenue) * 100
            margins['net_profit'] = round(profit, 2)
            margins['net_margin_pct'] = round(net_margin, 2)
        
        return margins
    
    def compare_companies(self, company_data: Dict[str, Dict]) -> Dict:
        """
        Compare metrics across companies.
        
        Args:
            company_data: Dict of {company_name: {metric: value}}
            
        Returns:
            Comparison analysis
        """
        if len(company_data) < 2:
            return {'error': 'Need at least 2 companies for comparison'}
        
        comparison = {
            'companies': list(company_data.keys()),
            'metrics': {},
        }
        
        # Get all metrics
        all_metrics = set()
        for company, data in company_data.items():
            all_metrics.update(data.keys())
        
        # Compare each metric
        for metric in all_metrics:
            values = {}
            for company, data in company_data.items():
                if metric in data:
                    values[company] = data[metric]
            
            if values:
                # Find leader
                leader = max(values, key=values.get)
                
                comparison['metrics'][metric] = {
                    'values': values,
                    'leader': leader,
                    'leader_value': values[leader],
                }
        
        return comparison
    
    def identify_trends(self, data: List[Dict]) -> Dict:
        """
        Identify trends in time series data.
        
        Args:
            data: List of {year: value} dicts
            
        Returns:
            Trend analysis
        """
        if len(data) < 3:
            return {'error': 'Need at least 3 data points for trend analysis'}
        
        # Extract values
        years = [d['year'] for d in data]
        values = [d['value'] for d in data]
        
        # Calculate trend
        z = np.polyfit(range(len(values)), values, 1)
        slope = z[0]
        
        # Volatility
        volatility = np.std(values)
        
        return {
            'years': years,
            'values': values,
            'slope': round(slope, 2),
            'trend': 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'flat',
            'volatility': round(volatility, 2),
            'stability': 'stable' if volatility < np.mean(values) * 0.1 else 'volatile',
        }
    
    def analyze(self, analysis_type: str, data: Dict) -> Dict:
        """
        Main analysis function (used by agent).
        
        Args:
            analysis_type: Type of analysis (growth, margins, comparison, trends)
            data: Input data
            
        Returns:
            Analysis results
        """
        if analysis_type == 'growth':
            values = data.get('values', [])
            return self.calculate_growth_rate(values)
        
        elif analysis_type == 'margins':
            revenue = data.get('revenue', 0)
            cost = data.get('cost')
            profit = data.get('profit')
            return self.calculate_margins(revenue, cost, profit)
        
        elif analysis_type == 'comparison':
            company_data = data.get('company_data', {})
            return self.compare_companies(company_data)
        
        elif analysis_type == 'trends':
            time_series = data.get('time_series', [])
            return self.identify_trends(time_series)
        
        else:
            return {'error': f'Unknown analysis type: {analysis_type}'}


def create_analyst_tool() -> Tool:
    """Create LangChain tool for analyst."""
    analyst = AnalystTool()
    
    def analyze_wrapper(input_str: str) -> str:
        """Wrapper function for LangChain tool."""
        import json
        
        try:
            input_dict = json.loads(input_str)
        except:
            return ("Error: Input must be JSON. Examples:\n"
                    '  {"type": "growth", "data": {"values": [9.76, 16.43, 23.6]}}\n'
                    '  {"type": "margins", "data": {"revenue": 23.6, "cost": 11.4, "profit": 3.2}}\n'
                    '  {"type": "comparison", "data": {"company_data": {"AMD": {"revenue": 23.6}, "Intel": {"revenue": 79.0}}}}\n'
                    '  {"type": "trends", "data": {"time_series": [9.76, 16.43, 23.6]}}')
        
        analysis_type = input_dict.get('type', 'growth')
        data = input_dict.get('data', {})
        
        # Auto-fix common LLM mistakes: if 'revenue' is a list, treat as values for growth
        if analysis_type == 'growth' and 'values' not in data:
            if 'revenue' in data and isinstance(data['revenue'], list):
                data['values'] = data['revenue']
            elif 'revenue' in data:
                data['values'] = [data['revenue']]
        
        results = analyst.analyze(analysis_type, data)
        
        output = f"Analysis Type: {analysis_type}\n\nResults:\n"
        output += json.dumps(results, indent=2)
        return output
    
    return Tool(
        name="financial_analyst",
        description="""Perform financial analysis. Input MUST be JSON with 'type' and 'data'.

Examples:
  {"type": "growth", "data": {"values": [9.76, 16.43, 23.6]}}
  {"type": "margins", "data": {"revenue": 23.6, "cost": 11.4, "profit": 3.2}}
  {"type": "comparison", "data": {"company_data": {"AMD": {"revenue": 23.6}, "Intel": {"revenue": 79.0}}}}
  {"type": "trends", "data": {"time_series": [9.76, 16.43, 23.6]}}""",
        func=analyze_wrapper,
    )


if __name__ == "__main__":
    # Test analyst
    tool = create_analyst_tool()
    
    # Test growth analysis
    test_input = '{"type": "growth", "data": {"values": [9.8, 16.4, 23.6]}}'
    result = tool.run(test_input)
    
    print(result)
