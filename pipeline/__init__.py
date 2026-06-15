"""KF CPTEC Multi-AI Content Factory Pipeline.

Automated SEO content generation for e-commerce SKUs.
Pipeline: DeepSeek → GPT → Claude → YouTube → Assembly
"""

__version__ = "2.0.0"
__author__ = "KF CPTEC"

from pipeline.core.orchestrator import Orchestrator
from pipeline.core.state_machine import SKUStateMachine

__all__ = [
    "Orchestrator",
    "SKUStateMachine",
]
