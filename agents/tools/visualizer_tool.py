"""
Visualizer Tool: Create charts and visualizations
"""

import json
from typing import Dict, List
from langchain_core.tools import Tool
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from pathlib import Path


class VisualizerTool:
    """Tool for creating financial visualizations."""
    
    def __init__(self, output_dir: str = "visualizations"):
        """Initialize visualizer."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def create_line_chart(self, data: Dict, title: str = "Trend Chart") -> str:
        """
        Create a line chart.
        
        Args:
            data: Dict with 'x' (labels) and 'y' (values)
            title: Chart title
            
        Returns:
            Path to saved chart
        """
        x = data.get('x', [])
        y = data.get('y', [])
        
        if not x or not y:
            return "Error: Need 'x' and 'y' data"
        
        # Create figure
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode='lines+markers',
            name=data.get('label', 'Value'),
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=8),
        ))
        
        fig.update_layout(
            title=title,
            xaxis_title=data.get('x_label', 'Year'),
            yaxis_title=data.get('y_label', 'Value'),
            template='plotly_white',
            height=500,
        )
        
        # Save
        filename = f"line_chart_{len(list(self.output_dir.glob('*.html')))}.html"
        filepath = self.output_dir / filename
        fig.write_html(str(filepath))
        
        return str(filepath)
    
    def create_bar_chart(self, data: Dict, title: str = "Comparison Chart") -> str:
        """
        Create a bar chart.
        
        Args:
            data: Dict with 'x' (labels) and 'y' (values)
            title: Chart title
            
        Returns:
            Path to saved chart
        """
        x = data.get('x', [])
        y = data.get('y', [])
        
        if not x or not y:
            return "Error: Need 'x' and 'y' data"
        
        # Create figure
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=x,
            y=y,
            name=data.get('label', 'Value'),
            marker_color='#2ca02c',
        ))
        
        fig.update_layout(
            title=title,
            xaxis_title=data.get('x_label', 'Category'),
            yaxis_title=data.get('y_label', 'Value'),
            template='plotly_white',
            height=500,
        )
        
        # Save
        filename = f"bar_chart_{len(list(self.output_dir.glob('*.html')))}.html"
        filepath = self.output_dir / filename
        fig.write_html(str(filepath))
        
        return str(filepath)
    
    def create_comparison_chart(self, data: Dict, title: str = "Multi-Company Comparison") -> str:
        """
        Create a grouped bar chart for comparing companies.
        
        Args:
            data: Dict with 'companies' (list), 'metrics' (list), 'values' (2D list)
            title: Chart title
            
        Returns:
            Path to saved chart
        """
        companies = data.get('companies', [])
        metrics = data.get('metrics', [])
        values = data.get('values', [])
        
        if not companies or not metrics or not values:
            return "Error: Need 'companies', 'metrics', and 'values'"
        
        # Create figure
        fig = go.Figure()
        
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        
        for i, company in enumerate(companies):
            fig.add_trace(go.Bar(
                name=company,
                x=metrics,
                y=values[i] if i < len(values) else [],
                marker_color=colors[i % len(colors)],
            ))
        
        fig.update_layout(
            title=title,
            xaxis_title="Metric",
            yaxis_title="Value",
            barmode='group',
            template='plotly_white',
            height=500,
        )
        
        # Save
        filename = f"comparison_chart_{len(list(self.output_dir.glob('*.html')))}.html"
        filepath = self.output_dir / filename
        fig.write_html(str(filepath))
        
        return str(filepath)
    
    def visualize(self, chart_type: str, data: Dict, title: str = None) -> str:
        """
        Main visualization function (used by agent).
        
        Args:
            chart_type: Type of chart (line, bar, comparison)
            data: Chart data
            title: Chart title
            
        Returns:
            Path to saved chart
        """
        title = title or f"{chart_type.title()} Chart"
        
        if chart_type == 'line':
            return self.create_line_chart(data, title)
        
        elif chart_type == 'bar':
            return self.create_bar_chart(data, title)
        
        elif chart_type == 'comparison':
            return self.create_comparison_chart(data, title)
        
        else:
            return f"Error: Unknown chart type: {chart_type}"


def create_visualizer_tool() -> Tool:
    """Create LangChain tool for visualizer."""
    visualizer = VisualizerTool()
    
    def visualize_wrapper(input_str: str) -> str:
        """Wrapper function for LangChain tool."""
        import json
        
        try:
            input_dict = json.loads(input_str)
        except:
            return ("Error: Input must be JSON. Examples:\n"
                    '  {"type": "bar", "data": {"x": ["2020", "2021"], "y": [19.3, 23.6]}, "title": "AMD Revenue"}\n'
                    '  {"type": "line", "data": {"x": ["2019", "2020", "2021"], "y": [6.7, 9.8, 16.4]}, "title": "Revenue Trend"}')
        
        chart_type = input_dict.get('type', 'bar')
        data = input_dict.get('data', {})
        title = input_dict.get('title', 'Financial Chart')
        
        # Auto-fix: if data has simple key-value pairs instead of x/y, convert
        if 'x' not in data and 'y' not in data:
            keys = [k for k in data.keys() if k not in ('label', 'x_label', 'y_label')]
            if keys:
                data = {'x': keys, 'y': [data[k] for k in keys]}
        
        filepath = visualizer.visualize(chart_type, data, title)
        return f"Chart created and saved to: {filepath}"
    
    return Tool(
        name="financial_visualizer",
        description="""Create financial charts. Input MUST be JSON with 'type', 'data' (with 'x' and 'y' arrays), and 'title'.

Examples:
  {"type": "bar", "data": {"x": ["2020", "2021"], "y": [19.3, 23.6]}, "title": "AMD Revenue"}
  {"type": "line", "data": {"x": ["Q1", "Q2", "Q3", "Q4"], "y": [3.4, 3.9, 4.3, 4.8]}, "title": "Quarterly Revenue"}
  {"type": "comparison", "data": {"x": ["AMD", "Intel"], "y": [23.6, 79.0]}, "title": "Revenue Comparison"}""",
        func=visualize_wrapper,
    )


if __name__ == "__main__":
    # Test visualizer
    tool = create_visualizer_tool()
    
    # Test line chart
    test_input = '{"type": "line", "data": {"x": [2019, 2020, 2021], "y": [6.7, 9.8, 16.4], "label": "Revenue ($B)"}, "title": "AMD Revenue Trend"}'
    result = tool.run(test_input)
    
    print(result)
