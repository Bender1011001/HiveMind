from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
from enum import Enum
from ..communication.message import Message, MessageType

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QualityMetric(Enum):
    """Types of quality metrics for evaluating responses."""
    RELEVANCE = "relevance"
    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
    CLARITY = "clarity"
    COHERENCE = "coherence"

@dataclass
class QualityScore:
    """Represents a quality score for a response."""
    response_id: str
    task_id: str
    evaluator_id: str
    scores: Dict[QualityMetric, float]
    feedback: str
    timestamp: datetime = datetime.utcnow()
    metadata: Optional[Dict] = None

    def get_average_score(self) -> float:
        """Calculate the average score across all metrics."""
        return sum(self.scores.values()) / len(self.scores)

class QualityScorer:
    """Manages the quality scoring system for agent responses."""
    
    def __init__(self):
        """Initialize the quality scoring system."""
        self.scores: Dict[str, List[QualityScore]] = {}  # task_id -> list of scores
        self.agent_performance: Dict[str, Dict[QualityMetric, List[float]]] = {}  # agent_id -> metric -> scores
        
    def evaluate_response(self, message: Message, evaluator_id: str, 
                         scores: Dict[QualityMetric, float], feedback: str) -> QualityScore:
        """Evaluate a response and store the quality score."""
        if not isinstance(message, Message):
            raise ValueError("message must be an instance of Message")
        if not all(isinstance(metric, QualityMetric) for metric in scores.keys()):
            raise ValueError("All metrics must be instances of QualityMetric")
        if not all(0 <= score <= 1 for score in scores.values()):
            raise ValueError("All scores must be between 0 and 1")
            
        # Create quality score
        score = QualityScore(
            response_id=message.metadata.get('message_id', str(datetime.utcnow().timestamp())),
            task_id=message.task_id,
            evaluator_id=evaluator_id,
            scores=scores,
            feedback=feedback,
            metadata={
                'sender_id': message.sender_id,
                'message_type': message.message_type.value,
                'evaluation_context': message.content.get('context', '')
            }
        )
        
        # Store score by task
        if message.task_id not in self.scores:
            self.scores[message.task_id] = []
        self.scores[message.task_id].append(score)
        
        # Update agent performance metrics
        if message.sender_id not in self.agent_performance:
            self.agent_performance[message.sender_id] = {metric: [] for metric in QualityMetric}
            
        for metric, score_value in scores.items():
            self.agent_performance[message.sender_id][metric].append(score_value)
            
        logger.info(f"Recorded quality score for task {message.task_id} from evaluator {evaluator_id}")
        return score
        
    def get_agent_metrics(self, agent_id: str) -> Dict[QualityMetric, float]:
        """Get average performance metrics for an agent."""
        if agent_id not in self.agent_performance:
            return {}
            
        return {
            metric: sum(scores) / len(scores) if scores else 0.0
            for metric, scores in self.agent_performance[agent_id].items()
        }
        
    def get_task_scores(self, task_id: str) -> List[QualityScore]:
        """Get all quality scores for a specific task."""
        return self.scores.get(task_id, [])
        
    def get_agent_performance_trend(self, agent_id: str, 
                                  metric: QualityMetric) -> List[Tuple[datetime, float]]:
        """Get performance trend for a specific agent and metric."""
        if agent_id not in self.agent_performance:
            return []
            
        task_scores = []
        for task_id, scores in self.scores.items():
            for score in scores:
                if score.metadata.get('sender_id') == agent_id and metric in score.scores:
                    task_scores.append((score.timestamp, score.scores[metric]))
                    
        return sorted(task_scores, key=lambda x: x[0])
        
    def get_top_performers(self, metric: QualityMetric, n: int = 5) -> List[Tuple[str, float]]:
        """Get top performing agents for a specific metric."""
        agent_averages = []
        
        for agent_id, metrics in self.agent_performance.items():
            if metric in metrics and metrics[metric]:
                avg_score = sum(metrics[metric]) / len(metrics[metric])
                agent_averages.append((agent_id, avg_score))
                
        return sorted(agent_averages, key=lambda x: x[1], reverse=True)[:n]
        
    def get_improvement_suggestions(self, agent_id: str) -> Dict[QualityMetric, str]:
        """Generate improvement suggestions based on agent's performance."""
        if agent_id not in self.agent_performance:
            return {}
            
        suggestions = {}
        metrics = self.get_agent_metrics(agent_id)
        
        for metric, score in metrics.items():
            if score < 0.6:
                suggestions[metric] = self._generate_suggestion(metric, score)
                
        return suggestions
        
    def _generate_suggestion(self, metric: QualityMetric, score: float) -> str:
        """Generate a specific improvement suggestion based on metric and score."""
        suggestions = {
            QualityMetric.RELEVANCE: "Focus on providing more relevant information directly related to the task",
            QualityMetric.ACCURACY: "Double-check facts and information before responding",
            QualityMetric.COMPLETENESS: "Ensure all aspects of the task are addressed in the response",
            QualityMetric.CLARITY: "Use clearer language and provide more structured responses",
            QualityMetric.COHERENCE: "Improve the logical flow and connection between ideas"
        }
        
        base_suggestion = suggestions.get(metric, "General improvement needed")
        severity = "significant" if score < 0.3 else "some"
        
        return f"{base_suggestion}. Current performance shows {severity} room for improvement."
