from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from ..messaging.message import Message, MessageType
from ...utils.logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

class QualityMetric(Enum):
    """Types of quality metrics for evaluating responses."""
    RELEVANCE = "relevance"
    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
    CLARITY = "clarity"
    COHERENCE = "coherence"

    @classmethod
    def get_description(cls, metric: 'QualityMetric') -> str:
        """Get description of a quality metric."""
        descriptions = {
            cls.RELEVANCE: "How well the response addresses the specific task or question",
            cls.ACCURACY: "Correctness and factual accuracy of the information provided",
            cls.COMPLETENESS: "Coverage of all aspects of the task or question",
            cls.CLARITY: "Clarity and understandability of the response",
            cls.COHERENCE: "Logical flow and connection between ideas"
        }
        return descriptions.get(metric, "No description available")

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
        try:
            return sum(self.scores.values()) / len(self.scores)
        except Exception as e:
            logger.error(f"Error calculating average score: {str(e)}", exc_info=True)
            raise

    def validate(self) -> bool:
        """Validate score data."""
        try:
            if not all(isinstance(metric, QualityMetric) for metric in self.scores.keys()):
                logger.error("Invalid metric types in scores")
                return False
            if not all(0 <= score <= 1 for score in self.scores.values()):
                logger.error("Score values out of range")
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating score: {str(e)}", exc_info=True)
            return False

class QualityScorer:
    """Manages the quality scoring system for agent responses."""

    def __init__(self, retention_days: int = 30):
        """Initialize the quality scoring system."""
        try:
            logger.info("Initializing QualityScorer")
            self.scores: Dict[str, List[QualityScore]] = {}  # task_id -> list of scores
            self.agent_performance: Dict[str, Dict[QualityMetric, List[Tuple[datetime, float]]]] = {}  # agent_id -> metric -> [(timestamp, score)]
            self.lock = Lock()
            self.retention_days = retention_days
            logger.debug(f"QualityScorer initialized with {retention_days} days retention")
        except Exception as e:
            logger.error(f"Error initializing QualityScorer: {str(e)}", exc_info=True)
            raise

    def evaluate_response(self, message: Message, evaluator_id: str,
                         scores: Dict[QualityMetric, float], feedback: str) -> QualityScore:
        """Evaluate a response and store the quality score."""
        try:
            logger.debug(f"Evaluating response for task {message.task_id} by evaluator {evaluator_id}")

            # Validate inputs
            if not isinstance(message, Message):
                logger.error("Invalid message type provided")
                raise ValueError("message must be an instance of Message")
            if not all(isinstance(metric, QualityMetric) for metric in scores.keys()):
                logger.error("Invalid quality metrics provided")
                raise ValueError("All metrics must be instances of QualityMetric")
            if not all(0 <= score <= 1 for score in scores.values()):
                logger.error("Invalid score values provided")
                raise ValueError("All scores must be between 0 and 1")

            with self.lock:
                # Create quality score
                response_id = message.metadata.get('message_id', str(datetime.utcnow().timestamp()))
                logger.debug(f"Creating quality score for response {response_id}")

                score = QualityScore(
                    response_id=response_id,
                    task_id=message.task_id,
                    evaluator_id=evaluator_id,
                    scores=scores,
                    feedback=feedback,
                    metadata={
                        'sender_id': message.sender_id,
                        'message_type': message.message_type.value,
                        'evaluation_context': message.content.get('context', ''),
                        'evaluation_timestamp': datetime.utcnow().isoformat()
                    }
                )

                # Validate score
                if not score.validate():
                    logger.error("Score validation failed")
                    raise ValueError("Invalid score data")

                # Store score by task
                if message.task_id not in self.scores:
                    logger.debug(f"Initializing scores list for task {message.task_id}")
                    self.scores[message.task_id] = []
                self.scores[message.task_id].append(score)

                # Update agent performance metrics
                if message.sender_id not in self.agent_performance:
                    logger.debug(f"Initializing performance metrics for agent {message.sender_id}")
                    self.agent_performance[message.sender_id] = {metric: [] for metric in QualityMetric}

                timestamp = datetime.utcnow()
                for metric, score_value in scores.items():
                    self.agent_performance[message.sender_id][metric].append((timestamp, score_value))
                    logger.debug(f"Updated {metric.value} score for agent {message.sender_id}: {score_value}")

                # Cleanup old data
                self._cleanup_old_data()

                logger.info(
                    f"Successfully recorded quality score for task {message.task_id} "
                    f"from evaluator {evaluator_id} (avg score: {score.get_average_score():.2f})"
                )
                return score

        except Exception as e:
            logger.error(f"Error evaluating response: {str(e)}", exc_info=True)
            raise

    def get_agent_metrics(self, agent_id: str, time_window: Optional[timedelta] = None) -> Dict[QualityMetric, Dict[str, float]]:
        """Get detailed performance metrics for an agent."""
        try:
            logger.debug(f"Retrieving metrics for agent {agent_id}")

            if agent_id not in self.agent_performance:
                logger.info(f"No performance metrics found for agent {agent_id}")
                return {}

            with self.lock:
                metrics = {}
                for metric, scores in self.agent_performance[agent_id].items():
                    if time_window:
                        cutoff = datetime.utcnow() - time_window
                        scores = [(ts, score) for ts, score in scores if ts >= cutoff]

                    if scores:
                        values = [score for _, score in scores]
                        metrics[metric] = {
                            'average': sum(values) / len(values),
                            'min': min(values),
                            'max': max(values),
                            'count': len(values),
                            'latest': scores[-1][1]
                        }

                logger.info(f"Retrieved metrics for agent {agent_id}: {metrics}")
                return metrics

        except Exception as e:
            logger.error(f"Error retrieving agent metrics: {str(e)}", exc_info=True)
            raise

    def get_task_scores(self, task_id: str) -> List[QualityScore]:
        """Get all quality scores for a specific task."""
        try:
            logger.debug(f"Retrieving scores for task {task_id}")
            with self.lock:
                scores = self.scores.get(task_id, [])
                logger.info(f"Retrieved {len(scores)} scores for task {task_id}")
                return scores
        except Exception as e:
            logger.error(f"Error retrieving task scores: {str(e)}", exc_info=True)
            raise

    def get_agent_performance_trend(self, agent_id: str,
                                  metric: QualityMetric,
                                  window_size: timedelta = timedelta(hours=1)) -> List[Tuple[datetime, float]]:
        """Get performance trend for a specific agent and metric."""
        try:
            logger.debug(f"Retrieving performance trend for agent {agent_id} on metric {metric.value}")

            if agent_id not in self.agent_performance:
                logger.info(f"No performance data found for agent {agent_id}")
                return []

            with self.lock:
                # Group scores by time window
                scores = self.agent_performance[agent_id].get(metric, [])
                if not scores:
                    return []

                trends = []
                current_window = []
                window_start = scores[0][0]

                for timestamp, score in sorted(scores):
                    if timestamp - window_start >= window_size:
                        if current_window:
                            avg_score = sum(current_window) / len(current_window)
                            trends.append((window_start, avg_score))
                        window_start = timestamp
                        current_window = []
                    current_window.append(score)

                if current_window:
                    avg_score = sum(current_window) / len(current_window)
                    trends.append((window_start, avg_score))

                logger.info(f"Retrieved {len(trends)} trend points for agent {agent_id} on metric {metric.value}")
                return trends

        except Exception as e:
            logger.error(f"Error retrieving performance trend: {str(e)}", exc_info=True)
            raise

    def get_top_performers(self, metric: QualityMetric, n: int = 5,
                          min_scores: int = 5) -> List[Tuple[str, float]]:
        """Get top performing agents for a specific metric."""
        try:
            logger.debug(f"Retrieving top {n} performers for metric {metric.value}")

            with self.lock:
                agent_averages = []

                for agent_id, metrics in self.agent_performance.items():
                    scores = [score for _, score in metrics.get(metric, [])]
                    if len(scores) >= min_scores:
                        avg_score = sum(scores) / len(scores)
                        agent_averages.append((agent_id, avg_score))

                top_performers = sorted(agent_averages, key=lambda x: x[1], reverse=True)[:n]
                logger.info(
                    f"Retrieved top {len(top_performers)} performers for metric {metric.value} "
                    f"(minimum {min_scores} scores required)"
                )
                return top_performers

        except Exception as e:
            logger.error(f"Error retrieving top performers: {str(e)}", exc_info=True)
            raise

    def get_improvement_suggestions(self, agent_id: str,
                                  threshold: float = 0.6) -> Dict[QualityMetric, Dict[str, Any]]:
        """Generate detailed improvement suggestions based on agent's performance."""
        try:
            logger.debug(f"Generating improvement suggestions for agent {agent_id}")

            if agent_id not in self.agent_performance:
                logger.info(f"No performance data found for agent {agent_id}")
                return {}

            suggestions = {}
            metrics = self.get_agent_metrics(agent_id)

            for metric, stats in metrics.items():
                avg_score = stats['average']
                if avg_score < threshold:
                    suggestion = self._generate_suggestion(metric, avg_score)
                    suggestions[metric] = {
                        'suggestion': suggestion,
                        'current_score': avg_score,
                        'target_score': threshold,
                        'improvement_needed': threshold - avg_score,
                        'metric_description': QualityMetric.get_description(metric)
                    }
                    logger.debug(f"Generated suggestion for {metric.value}: {suggestion}")

            logger.info(f"Generated {len(suggestions)} improvement suggestions for agent {agent_id}")
            return suggestions

        except Exception as e:
            logger.error(f"Error generating improvement suggestions: {str(e)}", exc_info=True)
            raise

    def _generate_suggestion(self, metric: QualityMetric, score: float) -> str:
        """Generate a specific improvement suggestion based on metric and score."""
        try:
            logger.debug(f"Generating suggestion for metric {metric.value} with score {score}")

            suggestions = {
                QualityMetric.RELEVANCE: "Focus on providing more relevant information directly related to the task",
                QualityMetric.ACCURACY: "Double-check facts and information before responding",
                QualityMetric.COMPLETENESS: "Ensure all aspects of the task are addressed in the response",
                QualityMetric.CLARITY: "Use clearer language and provide more structured responses",
                QualityMetric.COHERENCE: "Improve the logical flow and connection between ideas"
            }

            base_suggestion = suggestions.get(metric, "General improvement needed")
            severity = "significant" if score < 0.3 else "some"

            suggestion = f"{base_suggestion}. Current performance shows {severity} room for improvement."
            logger.debug(f"Generated suggestion: {suggestion}")
            return suggestion

        except Exception as e:
            logger.error(f"Error generating suggestion: {str(e)}", exc_info=True)
            raise

    def _cleanup_old_data(self):
        """Remove data older than retention period."""
        try:
            cutoff = datetime.utcnow() - timedelta(days=self.retention_days)

            with self.lock:
                # Cleanup agent performance data
                for agent_id in list(self.agent_performance.keys()):
                    for metric in list(self.agent_performance[agent_id].keys()):
                        original_count = len(self.agent_performance[agent_id][metric])
                        self.agent_performance[agent_id][metric] = [
                            (ts, score) for ts, score in self.agent_performance[agent_id][metric]
                            if ts >= cutoff
                        ]
                        removed_count = original_count - len(self.agent_performance[agent_id][metric])
                        if removed_count > 0:
                            logger.debug(
                                f"Removed {removed_count} old scores for agent {agent_id}, "
                                f"metric {metric.value}"
                            )

                # Cleanup task scores
                for task_id in list(self.scores.keys()):
                    original_count = len(self.scores[task_id])
                    self.scores[task_id] = [
                        score for score in self.scores[task_id]
                        if score.timestamp >= cutoff
                    ]
                    removed_count = original_count - len(self.scores[task_id])
                    if removed_count > 0:
                        logger.debug(f"Removed {removed_count} old scores for task {task_id}")

        except Exception as e:
            logger.error(f"Error cleaning up old data: {str(e)}", exc_info=True)
            raise
