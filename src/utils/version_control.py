"""Simple version control system for the shared workspace."""

import os
import shutil
import hashlib
import logging
from datetime import datetime
from typing import List, Dict
from ..settings import settings

logger = logging.getLogger(__name__)

class VersionControl:
    """Manages versioning of files within the shared workspace."""

    def __init__(self):
        self.repo_dir = os.path.join(settings.workspace_root, '.vc_repo')
        os.makedirs(self.repo_dir, exist_ok=True)

    def _compute_hash(self, file_path: str) -> str:
        """Compute the SHA256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as afile:
            buf = afile.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def commit(self, file_path: str, agent_id: str, message: str) -> None:
        """Commit a file to the version control system."""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File {file_path} does not exist.")

            rel_path = os.path.relpath(file_path, settings.workspace_root)
            file_hash = self._compute_hash(file_path)
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            commit_file_name = f"{timestamp}_{agent_id}_{os.path.basename(file_path)}_{file_hash}"

            commit_path = os.path.join(self.repo_dir, rel_path)
            os.makedirs(os.path.dirname(commit_path), exist_ok=True)
            shutil.copy2(file_path, os.path.join(commit_path, commit_file_name))

            logger.info(f"File {file_path} committed by {agent_id} with message: {message}")

        except Exception as e:
            logger.error(f"Error committing file {file_path}: {e}")
            raise

    def get_file_history(self, file_path: str) -> List[Dict]:
        """Retrieve the commit history of a file."""
        try:
            rel_path = os.path.relpath(file_path, settings.workspace_root)
            commit_path = os.path.join(self.repo_dir, rel_path)

            if not os.path.exists(commit_path):
                return []

            commits = []
            for commit_file in sorted(os.listdir(commit_path)):
                parts = commit_file.split('_')
                if len(parts) >= 3:
                    timestamp_str, agent_id, file_name = parts[:3]
                    timestamp = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
                    commits.append({
                        'timestamp': timestamp,
                        'agent_id': agent_id,
                        'file_name': file_name,
                        'file_path': os.path.join(commit_path, commit_file)
                    })

            return commits

        except Exception as e:
            logger.error(f"Error retrieving file history for {file_path}: {e}")
            raise

    def revert(self, file_path: str, commit_index: int) -> None:
        """Revert a file to a previous commit."""
        try:
            history = self.get_file_history(file_path)
            if not history:
                raise ValueError(f"No history found for {file_path}")

            if commit_index < 0 or commit_index >= len(history):
                raise IndexError("Commit index out of range.")

            commit = history[commit_index]
            shutil.copy2(commit['file_path'], file_path)
            logger.info(f"File {file_path} reverted to commit {commit_index}")

        except Exception as e:
            logger.error(f"Error reverting file {file_path}: {e}")
            raise
