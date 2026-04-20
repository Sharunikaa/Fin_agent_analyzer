"""
Evaluation Dashboard: Monitor performance and track improvements
"""

import streamlit as st
import json
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, timedelta

from config import LOGS_DIR, RESULTS_DIR, EVAL_METRICS

st.set_page_config(page_title="Evals Dashboard", layout="wide")

st.title("📊 Evaluation & Feedback Dashboard")
st.markdown("**Monitor agent performance, track improvements, identify issues**")

# Load evaluation results
results_files = sorted(RESULTS_DIR.glob("eval_results_*.json"), reverse=True)
logs_files = sorted(LOGS_DIR.glob("eval_log_*.json"), reverse=True)

if not results_files:
    st.warning("No evaluation results found. Run `python run_evals.py` first.")
    st.stop()

# Load latest results
with open(results_files[0]) as f:
    latest_results = json.load(f)

stats = latest_results['statistics']
analysis = latest_results['analysis']
results = latest_results['results']

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Overview",
    "📈 Metrics",
    "🔍 Query Analysis",
    "🔄 Feedback Loop"
])

# Tab 1: Overview
with tab1:
    st.header("Evaluation Overview")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Queries", stats['total_evaluations'])
    with col2:
        st.metric("Pass Rate", f"{stats['pass_rate']:.1f}%")
    with col3:
        st.metric("Avg Score", f"{stats['average_overall_score']:.3f}")
    with col4:
        st.metric("Avg Latency", f"{stats['average_latency']:.2f}s")
    
    # Health status
    st.subheader("System Health")
    
    health = analysis['overall_health']
    if health == 'good':
        st.success("✅ System is performing well!")
    else:
        st.warning("⚠️ System needs improvement")
    
    # Issues
    if analysis['issues']:
        st.subheader("🚨 Issues Detected")
        
        for issue in analysis['issues']:
            severity_color = {
                'critical': 'error',
                'high': 'warning',
                'medium': 'info',
            }.get(issue['severity'], 'info')
            
            with st.expander(f"{issue['type'].upper()} (Severity: {issue['severity']})"):
                st.write(f"**Metric**: {issue['metric']}")
                st.write(f"**Current**: {issue['current']:.3f}")
                st.write(f"**Threshold**: {issue['threshold']}")
                st.write(f"**Recommendation**: {issue['recommendation']}")
    else:
        st.success("✅ No issues detected!")

# Tab 2: Metrics
with tab2:
    st.header("Performance Metrics")
    
    # Metrics table
    st.subheader("Average Scores")
    
    metrics_data = []
    for metric, score in stats['average_metrics'].items():
        threshold = EVAL_METRICS.get(metric, {}).get('threshold', 0.7)
        status = "✅ Pass" if score >= threshold else "❌ Fail"
        
        metrics_data.append({
            "Metric": metric.replace('_', ' ').title(),
            "Score": f"{score:.3f}",
            "Threshold": f"{threshold:.2f}",
            "Status": status,
        })
    
    df_metrics = pd.DataFrame(metrics_data)
    st.dataframe(df_metrics, use_container_width=True)
    
    # Metrics chart
    st.subheader("Metrics Visualization")
    
    fig = go.Figure()
    
    metrics = list(stats['average_metrics'].keys())
    scores = list(stats['average_metrics'].values())
    thresholds = [EVAL_METRICS.get(m, {}).get('threshold', 0.7) for m in metrics]
    
    fig.add_trace(go.Bar(
        name='Actual Score',
        x=metrics,
        y=scores,
        marker_color='#2ca02c',
    ))
    
    fig.add_trace(go.Scatter(
        name='Threshold',
        x=metrics,
        y=thresholds,
        mode='lines+markers',
        line=dict(color='red', dash='dash'),
        marker=dict(size=8),
    ))
    
    fig.update_layout(
        title="Metrics vs Thresholds",
        xaxis_title="Metric",
        yaxis_title="Score",
        yaxis_range=[0, 1],
        template='plotly_white',
        height=400,
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Tab 3: Query Analysis
with tab3:
    st.header("Query-Level Analysis")
    
    # By category
    st.subheader("Performance by Category")
    
    category_data = []
    for category, cat_stats in stats['by_category'].items():
        category_data.append({
            "Category": category.replace('_', ' ').title(),
            "Total": cat_stats['total'],
            "Passed": cat_stats['passed'],
            "Pass Rate": f"{cat_stats['pass_rate']:.1f}%",
            "Avg Score": f"{cat_stats['avg_score']:.3f}",
        })
    
    df_category = pd.DataFrame(category_data)
    st.dataframe(df_category, use_container_width=True)
    
    # Individual query results
    st.subheader("Individual Query Results")
    
    query_data = []
    for result in results:
        eval_data = result['evaluation']
        
        query_data.append({
            "Query": result['query'][:60] + "...",
            "Category": result['category'],
            "Score": f"{eval_data['overall_score']:.3f}",
            "Accuracy": f"{eval_data['metrics']['accuracy']:.3f}",
            "Relevance": f"{eval_data['metrics']['relevance']:.3f}",
            "Status": "✅" if eval_data['passed'] else "❌",
        })
    
    df_queries = pd.DataFrame(query_data)
    st.dataframe(df_queries, use_container_width=True)
    
    # Failed queries
    failed_queries = [r for r in results if not r['evaluation']['passed']]
    
    if failed_queries:
        st.subheader(f"❌ Failed Queries ({len(failed_queries)})")
        
        for result in failed_queries:
            with st.expander(f"{result['query']}"):
                eval_data = result['evaluation']
                st.write(f"**Category**: {result['category']}")
                st.write(f"**Overall Score**: {eval_data['overall_score']:.3f}")
                st.write(f"**Metrics**:")
                for metric, value in eval_data['metrics'].items():
                    st.write(f"  - {metric}: {value:.3f}")

# Tab 4: Feedback Loop
with tab4:
    st.header("Feedback Loop & Improvements")
    
    # Improvement recommendations
    st.subheader("🔄 Improvement Recommendations")
    
    if analysis['issues']:
        for issue in analysis['issues']:
            severity_emoji = {
                'critical': '🔴',
                'high': '🟠',
                'medium': '🟡',
            }.get(issue['severity'], '🟢')
            
            st.markdown(f"### {severity_emoji} {issue['type'].replace('_', ' ').title()}")
            st.write(f"**Severity**: {issue['severity'].upper()}")
            st.write(f"**Metric**: {issue['metric']}")
            st.write(f"**Current**: {issue['current']:.3f}")
            st.write(f"**Threshold**: {issue['threshold']}")
            st.write(f"**Recommendation**: {issue['recommendation']}")
            st.markdown("---")
    else:
        st.success("✅ No improvements needed - system performing well!")
    
    # Historical performance (if multiple snapshots exist)
    st.subheader("📈 Historical Performance")
    
    snapshot_files = sorted(RESULTS_DIR.glob("performance_snapshot_*.json"))
    
    if len(snapshot_files) > 1:
        historical_data = []
        
        for snapshot_file in snapshot_files[-10:]:  # Last 10 snapshots
            with open(snapshot_file) as f:
                snapshot = json.load(f)
            
            historical_data.append({
                'timestamp': snapshot['timestamp'],
                'pass_rate': (snapshot['by_category'].get('factual_retrieval', {}).get('passed', 0) / 
                             snapshot['by_category'].get('factual_retrieval', {}).get('total', 1)) * 100,
                'avg_score': snapshot['average_scores'].get('overall', 0),
            })
        
        df_history = pd.DataFrame(historical_data)
        
        # Plot historical performance
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_history['timestamp'],
            y=df_history['avg_score'],
            mode='lines+markers',
            name='Avg Score',
            line=dict(color='#1f77b4', width=2),
        ))
        
        fig.update_layout(
            title="Performance Over Time",
            xaxis_title="Timestamp",
            yaxis_title="Average Score",
            template='plotly_white',
            height=400,
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Run evaluations multiple times to see historical trends")
    
    # Feedback log
    st.subheader("📝 Recent Feedback Logs")
    
    if logs_files:
        with open(logs_files[0]) as f:
            recent_logs = [json.loads(line) for line in f.readlines()[-5:]]
        
        for log in recent_logs:
            with st.expander(f"{log['query'][:60]}..."):
                st.write(f"**Timestamp**: {log['timestamp']}")
                st.write(f"**Category**: {log['evaluation']['category']}")
                st.write(f"**Score**: {log['evaluation']['overall_score']:.3f}")
                st.write(f"**Passed**: {'✅' if log['evaluation']['passed'] else '❌'}")

# Footer
st.markdown("---")
st.info("""
**How to Use This Dashboard**:
1. Run evaluations: `python run_evals.py`
2. View results here
3. Check improvement recommendations
4. Track performance over time
5. Iterate and improve agents
""")
