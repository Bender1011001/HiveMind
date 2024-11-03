import subprocess
import os
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
import docker
from docker.errors import DockerException
from ..settings import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CodeExecutor:
    """Manages code execution in a secure environment."""
    
    def __init__(self, use_docker: bool = True, timeout: int = 30):
        """Initialize code executor."""
        self.use_docker = use_docker
        self.timeout = timeout
        self.docker_client = None
        
        if use_docker:
            try:
                self.docker_client = docker.from_env()
                logger.info("Docker client initialized successfully")
            except DockerException as e:
                logger.warning(f"Failed to initialize Docker client: {e}. Falling back to local execution.")
                self.use_docker = False
                
    def execute_code(self, code: str, language: str, 
                    inputs: Optional[Dict] = None,
                    filename: Optional[str] = None) -> Tuple[bool, str, str]:
        """
        Execute code in a secure environment.
        
        Args:
            code: The code to execute
            language: Programming language of the code
            inputs: Optional dictionary of input variables
            filename: Optional filename to save code (if None, generates timestamp-based name)
            
        Returns:
            Tuple of (success, output, error)
        """
        if self.use_docker:
            return self._execute_in_docker(code, language, inputs, filename)
        else:
            return self._execute_locally(code, language, inputs, filename)
            
    def _get_code_file_path(self, language: str, filename: Optional[str] = None) -> str:
        """Get the full path for saving the code file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"code_{timestamp}.{language}"
            
        return os.path.join(settings.shared_code_dir, filename)
            
    def _execute_in_docker(self, code: str, language: str,
                          inputs: Optional[Dict] = None,
                          filename: Optional[str] = None) -> Tuple[bool, str, str]:
        """Execute code inside a Docker container."""
        try:
            # Prepare container configuration
            container_config = {
                'python': {
                    'image': 'python:3.8-slim',
                    'command': ['python'],
                    'extension': '.py'
                },
                'javascript': {
                    'image': 'node:14-alpine',
                    'command': ['node'],
                    'extension': '.js'
                }
            }
            
            if language not in container_config:
                raise ValueError(f"Unsupported language: {language}")
                
            config = container_config[language]
            
            # Save code to shared directory
            code_file_path = self._get_code_file_path(language, filename)
            with open(code_file_path, 'w') as f:
                f.write(code)
                
            try:
                # Run container with mounted code file
                container = self.docker_client.containers.run(
                    image=config['image'],
                    command=[*config['command'], os.path.basename(code_file_path)],
                    volumes={
                        settings.shared_code_dir: {
                            'bind': '/code',
                            'mode': 'ro'
                        },
                        settings.shared_output_dir: {
                            'bind': '/output',
                            'mode': 'rw'
                        }
                    },
                    working_dir='/code',
                    detach=True,
                    mem_limit='100m',
                    cpu_period=100000,
                    cpu_quota=50000,  # Limit to 50% CPU
                    network_disabled=True
                )
                
                try:
                    container.wait(timeout=self.timeout)
                    logs = container.logs()
                    output = logs.decode('utf-8')
                    
                    # Save output to shared output directory
                    output_file = os.path.join(
                        settings.shared_output_dir,
                        f"output_{os.path.basename(code_file_path)}.txt"
                    )
                    with open(output_file, 'w') as f:
                        f.write(output)
                    
                    return True, output, ""
                except Exception as e:
                    return False, "", str(e)
                finally:
                    container.remove(force=True)
                    
            except Exception as e:
                logger.error(f"Error executing code in Docker: {e}")
                return False, "", str(e)
                
        except Exception as e:
            logger.error(f"Error in Docker execution setup: {e}")
            return False, "", str(e)
            
    def _execute_locally(self, code: str, language: str,
                        inputs: Optional[Dict] = None,
                        filename: Optional[str] = None) -> Tuple[bool, str, str]:
        """Execute code locally with safety restrictions."""
        try:
            # Save code to shared directory
            code_file_path = self._get_code_file_path(language, filename)
            with open(code_file_path, 'w') as f:
                f.write(code)
                
            try:
                # Execute based on language
                if language == 'python':
                    process = subprocess.Popen(
                        ['python', code_file_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=settings.shared_code_dir
                    )
                elif language == 'javascript':
                    process = subprocess.Popen(
                        ['node', code_file_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=settings.shared_code_dir
                    )
                else:
                    raise ValueError(f"Unsupported language: {language}")
                    
                try:
                    stdout, stderr = process.communicate(timeout=self.timeout)
                    success = process.returncode == 0
                    
                    # Save output to shared output directory
                    output_file = os.path.join(
                        settings.shared_output_dir,
                        f"output_{os.path.basename(code_file_path)}.txt"
                    )
                    with open(output_file, 'w') as f:
                        f.write(stdout if success else stderr)
                    
                    return success, stdout, stderr
                except subprocess.TimeoutExpired:
                    process.kill()
                    return False, "", "Execution timed out"
                    
            except Exception as e:
                logger.error(f"Error executing code locally: {e}")
                return False, "", str(e)
                
        except Exception as e:
            logger.error(f"Error in local execution setup: {e}")
            return False, "", str(e)
            
    def cleanup(self):
        """Clean up resources."""
        if self.docker_client:
            self.docker_client.close()
