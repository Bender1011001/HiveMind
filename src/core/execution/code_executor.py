import subprocess
import os
from typing import Dict, Optional, Tuple
from datetime import datetime
import docker
from docker.errors import DockerException
from ..settings.settings import settings
from ...utils.logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

class CodeExecutor:
    """Manages code execution in a secure environment."""

    def __init__(self, use_docker: bool = True, timeout: int = 30):
        """Initialize code executor."""
        self.use_docker = use_docker
        self.timeout = timeout
        self.docker_client = None

        logger.info(f"Initializing CodeExecutor (Docker: {use_docker}, Timeout: {timeout}s)")

        if use_docker:
            try:
                self.docker_client = docker.from_env()
                logger.info("Docker client initialized successfully")
                # Test Docker connection
                self.docker_client.ping()
                logger.info("Docker daemon is responsive")
            except DockerException as e:
                logger.warning(f"Failed to initialize Docker client: {e}. Falling back to local execution.", exc_info=True)
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
        logger.info(f"Executing {language} code{f' with filename {filename}' if filename else ''}")
        logger.debug(f"Code length: {len(code)} characters")

        if self.use_docker:
            logger.info("Using Docker for code execution")
            return self._execute_in_docker(code, language, inputs, filename)
        else:
            logger.info("Using local environment for code execution")
            return self._execute_locally(code, language, inputs, filename)

    def _get_code_file_path(self, language: str, filename: Optional[str] = None) -> str:
        """Get the full path for saving the code file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"code_{timestamp}.{language}"

        file_path = os.path.join(settings.shared_code_dir, filename)
        logger.debug(f"Generated code file path: {file_path}")
        return file_path

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
                logger.error(f"Unsupported language requested: {language}")
                raise ValueError(f"Unsupported language: {language}")

            config = container_config[language]
            logger.info(f"Using Docker image: {config['image']}")

            # Save code to shared directory
            code_file_path = self._get_code_file_path(language, filename)
            logger.debug(f"Saving code to file: {code_file_path}")
            with open(code_file_path, 'w') as f:
                f.write(code)
            logger.info(f"Code saved to {code_file_path}")

            try:
                logger.debug("Configuring Docker container")
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
                logger.info(f"Started Docker container: {container.id[:12]}")

                try:
                    logger.debug(f"Waiting for container {container.id[:12]} to complete (timeout: {self.timeout}s)")
                    container.wait(timeout=self.timeout)
                    logs = container.logs()
                    output = logs.decode('utf-8')

                    # Save output to shared output directory
                    output_file = os.path.join(
                        settings.shared_output_dir,
                        f"output_{os.path.basename(code_file_path)}.txt"
                    )
                    logger.debug(f"Saving output to: {output_file}")
                    with open(output_file, 'w') as f:
                        f.write(output)

                    logger.info(f"Code execution completed successfully in container {container.id[:12]}")
                    return True, output, ""
                except Exception as e:
                    logger.error(f"Error during container execution: {str(e)}", exc_info=True)
                    return False, "", str(e)
                finally:
                    logger.debug(f"Removing container {container.id[:12]}")
                    container.remove(force=True)

            except Exception as e:
                logger.error(f"Error executing code in Docker: {str(e)}", exc_info=True)
                return False, "", str(e)

        except Exception as e:
            logger.error(f"Error in Docker execution setup: {str(e)}", exc_info=True)
            return False, "", str(e)

    def _execute_locally(self, code: str, language: str,
                        inputs: Optional[Dict] = None,
                        filename: Optional[str] = None) -> Tuple[bool, str, str]:
        """Execute code locally with safety restrictions."""
        try:
            # Save code to shared directory
            code_file_path = self._get_code_file_path(language, filename)
            logger.debug(f"Saving code to file: {code_file_path}")
            with open(code_file_path, 'w') as f:
                f.write(code)
            logger.info(f"Code saved to {code_file_path}")

            try:
                # Execute based on language
                if language == 'python':
                    logger.debug("Executing Python code")
                    process = subprocess.Popen(
                        ['python', code_file_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=settings.shared_code_dir
                    )
                elif language == 'javascript':
                    logger.debug("Executing JavaScript code")
                    process = subprocess.Popen(
                        ['node', code_file_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=settings.shared_code_dir
                    )
                else:
                    logger.error(f"Unsupported language requested: {language}")
                    raise ValueError(f"Unsupported language: {language}")

                try:
                    logger.debug(f"Waiting for process to complete (timeout: {self.timeout}s)")
                    stdout, stderr = process.communicate(timeout=self.timeout)
                    success = process.returncode == 0

                    if success:
                        logger.info("Code execution completed successfully")
                    else:
                        logger.warning(f"Code execution failed with return code: {process.returncode}")
                        logger.debug(f"Error output: {stderr}")

                    # Save output to shared output directory
                    output_file = os.path.join(
                        settings.shared_output_dir,
                        f"output_{os.path.basename(code_file_path)}.txt"
                    )
                    logger.debug(f"Saving output to: {output_file}")
                    with open(output_file, 'w') as f:
                        f.write(stdout if success else stderr)

                    return success, stdout, stderr
                except subprocess.TimeoutExpired:
                    logger.error(f"Code execution timed out after {self.timeout} seconds")
                    process.kill()
                    return False, "", "Execution timed out"

            except Exception as e:
                logger.error(f"Error executing code locally: {str(e)}", exc_info=True)
                return False, "", str(e)

        except Exception as e:
            logger.error(f"Error in local execution setup: {str(e)}", exc_info=True)
            return False, "", str(e)

    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up CodeExecutor resources")
        if self.docker_client:
            try:
                self.docker_client.close()
                logger.info("Docker client closed successfully")
            except Exception as e:
                logger.error(f"Error closing Docker client: {str(e)}", exc_info=True)
