"""Test runner for CourtListener MCP server tests."""

from pathlib import Path
import subprocess
import sys

from loguru import logger


def run_tests() -> int:
    """Run all tests with appropriate settings.

    Returns:
        int: The return code from the test run (0 if all tests pass, nonzero otherwise).

    """
    test_dir = Path(__file__).parent

    # Run pytest with coverage
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_dir),
        "-v",
        "--tb=short",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
    ]

    logger.info(f"Running tests with command: {' '.join(cmd)}")

    result = subprocess.run(cmd, check=False)

    if result.returncode == 0:
        logger.success("All tests passed!")
    else:
        logger.error(f"Tests failed with return code {result.returncode}")

    return result.returncode


if __name__ == "__main__":
    sys.exit(run_tests())
