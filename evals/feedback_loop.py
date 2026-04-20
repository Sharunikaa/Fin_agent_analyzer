"""
Feedback Loop: Log results, track performance, trigger improvements
"""

import json
import time
from typing import Dict, List
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from config import LOGS_DIR, RESULTS_DIR, IMPROVEMENT_THRESHOLDS, EVAL_METRICS


class FeedbackLoop:
    """Manage feedback loop for continuous improvement."""
    
    def __init__(self):
        """Initialize feedback loop."""
        self.feedback_log = []
        self.performance_history = []
    
    def log_query(
        self,
        query: str,
        response: Dict,
        evaluation: Dict = None,
        user_feedback: str = None,
    ):
        """
        Log a query execution with evaluation and feedback.
        
        Args:
            query: User query
            response: Agent response
            evaluation: Evaluation results
            user_feedback: Optional user feedback
        """
        log_entry = {
            'log_id': f"log_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'response': response,
            'evaluation': evaluation,
            'user_feedback': user_feedback,
        }
        
        self.feedback_log.append(log_entry)
        
        # Save to file
        self._save_log_entry(log_entry)
    
    def _save_log_entry(self, log_entry: Dict):
        """Save a single log entry to file."""
        date_str = datetime.now().strftime('%Y%m%d')
        log_file = LOGS_DIR / f"feedback_log_{date_str}.jsonl"
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def analyze_performance(self, logs: List[Dict] = None) -> Dict:
        """
        Analyze performance from logs.
        
        Args:
            logs: Optional list of logs (if None, use self.feedback_log)
            
        Returns:
            performance_analysis: Dict with statistics and trends
        """
        logs = logs or self.feedback_log
        
        if not logs:
            return {}
        
        # Aggregate metrics
        total_queries = len(logs)
        
        # Count by category
        by_category = defaultdict(lambda: {'total': 0, 'passed': 0, 'avg_score': 0.0})
        
        # Aggregate scores
        total_scores = {
            'recall_at_k': [], 'precision_at_k': [], 'mrr': [], 'ndcg': [],
            'context_recall': [], 'context_precision': [], 'context_relevance': [],
            'faithfulness': [], 'answer_relevancy': [], 'answer_correctness': [],
            'semantic_similarity': [], 'overall': [],
        }
        
        for log in logs:
            evaluation = log.get('evaluation', {})
            
            if evaluation:
                category = evaluation.get('category', 'unknown')
                overall = evaluation.get('overall_score', 0)
                
                by_category[category]['total'] += 1
                by_category[category]['avg_score'] += overall
                
                # Collect from all 3 layers
                for layer in ('layer1_retrieval', 'layer2_context', 'layer3_generation'):
                    for metric, value in evaluation.get(layer, {}).items():
                        if metric in total_scores:
                            total_scores[metric].append(value)
                
                # Legacy flat metrics fallback
                for metric, value in evaluation.get('metrics', {}).items():
                    if metric in total_scores:
                        total_scores[metric].append(value)
                
                total_scores['overall'].append(overall)
        
        # Calculate averages
        avg_scores = {}
        for metric, values in total_scores.items():
            if values:
                avg_scores[metric] = sum(values) / len(values)
        
        # Calculate pass rates by category
        for cat, stats in by_category.items():
            if stats['total'] > 0:
                stats['pass_rate'] = (stats['passed'] / stats['total']) * 100
                stats['avg_score'] = stats['avg_score'] / stats['total']
        
        # Identify issues
        issues = []
        
        if avg_scores.get('faithfulness', 1.0) < IMPROVEMENT_THRESHOLDS.get('faithfulness_low', 0.5):
            issues.append({
                'type': 'low_faithfulness',
                'severity': 'critical',
                'metric': 'faithfulness',
                'current': avg_scores['faithfulness'],
                'threshold': IMPROVEMENT_THRESHOLDS['faithfulness_low'],
                'recommendation': 'High hallucination rate — improve context quality and grounding',
            })
        
        if avg_scores.get('recall_at_k', 1.0) < IMPROVEMENT_THRESHOLDS.get('retrieval_recall_low', 0.4):
            issues.append({
                'type': 'low_retrieval_recall',
                'severity': 'high',
                'metric': 'recall_at_k',
                'current': avg_scores['recall_at_k'],
                'threshold': IMPROVEMENT_THRESHOLDS['retrieval_recall_low'],
                'recommendation': 'Poor retrieval — review embedding model and chunking strategy',
            })
        
        if avg_scores.get('context_precision', 1.0) < IMPROVEMENT_THRESHOLDS.get('context_precision_low', 0.3):
            issues.append({
                'type': 'low_context_precision',
                'severity': 'medium',
                'metric': 'context_precision',
                'current': avg_scores['context_precision'],
                'threshold': IMPROVEMENT_THRESHOLDS['context_precision_low'],
                'recommendation': 'Too much noise in context — improve filtering and re-ranking',
            })
        
        if avg_scores.get('answer_correctness', 1.0) < IMPROVEMENT_THRESHOLDS.get('answer_correctness_low', 0.5):
            issues.append({
                'type': 'low_answer_correctness',
                'severity': 'high',
                'metric': 'answer_correctness',
                'current': avg_scores['answer_correctness'],
                'threshold': IMPROVEMENT_THRESHOLDS['answer_correctness_low'],
                'recommendation': 'Answers not matching ground truth — review prompts and retrieval',
            })
        
        # Calculate error rate
        failed = total_queries - sum(stats['passed'] for stats in by_category.values())
        error_rate = (failed / total_queries) if total_queries > 0 else 0
        
        if error_rate > IMPROVEMENT_THRESHOLDS['error_rate_high']:
            issues.append({
                'type': 'high_error_rate',
                'severity': 'critical',
                'metric': 'error_rate',
                'current': error_rate,
                'threshold': IMPROVEMENT_THRESHOLDS['error_rate_high'],
                'recommendation': 'Review agent prompts and tool implementations',
            })
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_queries': total_queries,
            'average_scores': {k: round(v, 3) for k, v in avg_scores.items()},
            'by_category': dict(by_category),
            'issues': issues,
            'overall_health': 'good' if not issues else 'needs_improvement',
        }
    
    def generate_improvement_report(self, analysis: Dict) -> str:
        """
        Generate improvement recommendations.
        
        Args:
            analysis: Performance analysis
            
        Returns:
            report: Human-readable report
        """
        report = []
        
        report.append("="*80)
        report.append("PERFORMANCE ANALYSIS & IMPROVEMENT RECOMMENDATIONS")
        report.append("="*80)
        
        report.append(f"\nTimestamp: {analysis['timestamp']}")
        report.append(f"Total Queries: {analysis['total_queries']}")
        report.append(f"Overall Health: {analysis['overall_health'].upper()}")
        
        # Average scores
        report.append("\n" + "-"*80)
        report.append("AVERAGE SCORES")
        report.append("-"*80)
        
        for metric, score in analysis['average_scores'].items():
            threshold = EVAL_METRICS.get(metric, {}).get('threshold', 0.7)
            status = "✅" if score >= threshold else "⚠️"
            report.append(f"  {status} {metric:20s}: {score:.3f} (threshold: {threshold})")
        
        # By category
        report.append("\n" + "-"*80)
        report.append("PERFORMANCE BY CATEGORY")
        report.append("-"*80)
        
        for category, stats in analysis['by_category'].items():
            report.append(f"\n  {category}:")
            report.append(f"    Total: {stats['total']}")
            report.append(f"    Passed: {stats['passed']}")
            report.append(f"    Pass Rate: {stats['pass_rate']:.1f}%")
            report.append(f"    Avg Score: {stats['avg_score']:.3f}")
        
        # Issues
        if analysis['issues']:
            report.append("\n" + "-"*80)
            report.append("ISSUES DETECTED")
            report.append("-"*80)
            
            for issue in analysis['issues']:
                report.append(f"\n  🚨 {issue['type'].upper()} (Severity: {issue['severity']})")
                report.append(f"     Metric: {issue['metric']}")
                report.append(f"     Current: {issue['current']:.3f}")
                report.append(f"     Threshold: {issue['threshold']}")
                report.append(f"     Recommendation: {issue['recommendation']}")
        else:
            report.append("\n✅ No issues detected - system performing well!")
        
        report.append("\n" + "="*80)
        
        return "\n".join(report)
    
    def save_performance_snapshot(self, analysis: Dict):
        """Save performance snapshot for tracking over time."""
        snapshot_file = RESULTS_DIR / f"performance_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(snapshot_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"✅ Saved performance snapshot: {snapshot_file}")
        
        return snapshot_file


if __name__ == "__main__":
    # Test feedback loop
    feedback_loop = FeedbackLoop()
    
    # Sample log entry
    test_query = "What is AMD's revenue in 2021?"
    test_response = {
        'data': {'revenue': 16400.0, 'year': 2021, 'company': 'AMD'},
        'text': "AMD's revenue in 2021 was $16.4 billion.",
        'sources': ['AMD_2021_10K'],
        'latency': 2.5,
    }
    test_evaluation = {
        'metrics': {'accuracy': 0.95, 'relevance': 0.90, 'completeness': 0.85, 'latency': 2.5, 'coherence': 0.80},
        'overall_score': 0.88,
        'passed': True,
        'category': 'factual_retrieval',
    }
    
    # Log
    feedback_loop.log_query(test_query, test_response, test_evaluation, "correct")
    
    # Analyze
    analysis = feedback_loop.analyze_performance()
    
    # Generate report
    report = feedback_loop.generate_improvement_report(analysis)
    print(report)
