"""Simple version control system for the shared workspace."""

import os
import shutil
import hashlib
from datetime import datetime
from typing import List, Dict
from ..core.settings import settings
from .logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

class VersionControl:
    """Manages versioning of files within the shared workspace."""

    def __init__(self):
        """Initialize the version control system."""
        logger.info("Initializing version control system")
        self.repo_dir = os.path.join(settings.workspace_root, '.vc_repo')
        try:
            os.makedirs(self.repo_dir, exist_ok=True)
            logger.debug(f"Version control repository directory: {self.repo_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize version control repository: {str(e)}", exc_info=True)
            raise

    def _compute_hash(self, file_path: str) -> str:
        """Compute the SHA256 hash of a file."""
        try:
            logger.debug(f"Computing hash for file: {file_path}")
            hasher = hashlib.sha256()
            with open(file_path, 'rb') as afile:
                buf = afile.read()
                hasher.update(buf)
            file_hash = hasher.hexdigest()
            logger.debug(f"Computed hash for {file_path}: {file_hash[:8]}...")
            return file_hash
        except Exception as e:
            logger.error(f"Failed to compute hash for file {file_path}: {str(e)}", exc_info=True)
            raise

    def commit(self, file_path: str, agent_id: str, message: str) -> None:
        """Commit a file to the version control system."""
        try:
            logger.info(f"Attempting to commit file: {file_path}")
            logger.debug(f"Commit details - Agent: {agent_id}, Message: {message}")

            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                raise FileNotFoundError(f"File {file_path} does not exist.")

            rel_path = os.path.relpath(file_path, settings.workspace_root)
            logger.debug(f"Relative path: {rel_path}")

            file_hash = self._compute_hash(file_path)
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            commit_file_name = f"{timestamp}_{agent_id}_{os.path.basename(file_path)}_{file_hash}"
            logger.debug(f"Generated commit filename: {commit_file_name}")

            commit_path = os.path.join(self.repo_dir, rel_path)
            os.makedirs(os.path.dirname(commit_path), exist_ok=True)

            dest_path = os.path.join(commit_path, commit_file_name)
            shutil.copy2(file_path, dest_path)
            logger.info(f"Successfully committed file {file_path} to {dest_path}")
            logger.debug(f"Commit details - Hash: {file_hash[:8]}, Timestamp: {timestamp}")

        except Exception as e:
            logger.error(f"Failed to commit file {file_path}: {str(e)}", exc_info=True)
            raise

    def get_file_history(self, file_path: str) -> List[Dict]:
        """Retrieve the commit history of a file."""
        try:
            logger.info(f"Retrieving commit history for file: {file_path}")
            rel_path = os.path.relpath(file_path, settings.workspace_root)
            commit_path = os.path.join(self.repo_dir, rel_path)
            logger.debug(f"Looking for commits in: {commit_path}")

            if not os.path.exists(commit_path):
                logger.info(f"No commit history found for {file_path}")
                return []

            commits = []
            for commit_file in sorted(os.listdir(commit_path)):
                parts = commit_file.split('_')
                if len(parts) >= 3:
                    timestamp_str, agent_id, file_name = parts[:3]
                    timestamp = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
                    commit_info = {
                        'timestamp': timestamp,
                        'agent_id': agent_id,
                        'file_name': file_name,
                        'file_path': os.path.join(commit_path, commit_file)
                    }
                    commits.append(commit_info)
                    logger.debug(f"Found commit: {timestamp_str} by {agent_id}")

            logger.info(f"Retrieved {len(commits)} commits for {file_path}")
            return commits

        except Exception as e:
            logger.error(f"Failed to retrieve file history for {file_path}: {str(e)}", exc_info=True)
            raise

    def revert(self, file_path: str, commit_index: int) -> None:
        """Revert a file to a previous commit."""
        try:
            logger.info(f"Attempting to revert {file_path} to commit index {commit_index}")
            history = self.get_file_history(file_path)

            if not history:
                logger.error(f"No commit history found for {file_path}")
                raise ValueError(f"No history found for {file_path}")

            if commit_index < 0 or commit_index >= len(history):
                logger.error(f"Invalid commit index {commit_index} for {file_path}")
                raise IndexError("Commit index out of range.")

            commit = history[commit_index]
            logger.debug(f"Reverting to commit: {commit['timestamp']} by {commit['agent_id']}")

            # Create a backup before reverting
            backup_path = f"{file_path}.backup_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            shutil.copy2(file_path, backup_path)
            logger.debug(f"Created backup at: {backup_path}")

            # Perform the revert
            shutil.copy2(commit['file_path'], file_path)
            logger.info(f"Successfully reverted {file_path} to commit {commit_index}")
            logger.debug(f"Revert details - Timestamp: {commit['timestamp']}, Agent: {commit['agent_id']}")

        except Exception as e:
            logger.error(f"Failed to revert file {file_path}: {str(e)}", exc_info=True)
            raise

    def get_stats(self) -> Dict:
        """Get statistics about the version control repository."""
        try:
            logger.debug("Collecting version control statistics")
            total_commits = 0
            total_files = 0
            repo_size = 0

            for root, _, files in os.walk(self.repo_dir):
                total_files += len(files)
                total_commits += sum(1 for f in files if f.count('_') >= 3)
                repo_size += sum(os.path.getsize(os.path.join(root, f)) for f in files)

            stats = {
                'total_commits': total_commits,
                'total_files': total_files,
                'repository_size_bytes': repo_size,
                'repository_path': self.repo_dir
            }

            logger.info(f"Version control statistics: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to collect version control statistics: {str(e)}", exc_info=True)
            raise
