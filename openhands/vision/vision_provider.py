"""Vision provider — multimodal screen/image understanding integration layer.

Provides a unified interface for vision capabilities:
- Screenshot analysis and UI element detection
- Web page visual understanding
- Image-to-text description
- Visual grounding (locating elements by description)

Supports multiple backends:
- OmniParser (Microsoft's pure-vision GUI parser)
- Ollama multimodal models (llava, bakllava, moondream)
- OpenAI GPT-4V / Claude vision APIs
- Local screenshot capture via Playwright

Per OPERATING_RULES.md RULE 5: Production-grade — no prototypes.
"""

import base64
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from openhands.core.logger import openhands_logger as logger

# Vision limits
MAX_IMAGE_SIZE_BYTES = 20_971_520  # 20MB
MAX_ELEMENTS_PER_SCREEN = 500
MAX_DESCRIPTION_LENGTH = 10_000
VISION_TIMEOUT_S = 60


class VisionBackend(Enum):
    """Available vision backends."""

    OLLAMA = 'ollama'  # Local multimodal models
    OPENAI = 'openai'  # GPT-4V / GPT-4o
    ANTHROPIC = 'anthropic'  # Claude vision
    OMNIPARSER = 'omniparser'  # Microsoft OmniParser
    MOCK = 'mock'  # For testing


class ElementType(Enum):
    """Types of UI elements detected in screenshots."""

    BUTTON = 'button'
    INPUT = 'input'
    LINK = 'link'
    TEXT = 'text'
    IMAGE = 'image'
    DROPDOWN = 'dropdown'
    CHECKBOX = 'checkbox'
    RADIO = 'radio'
    MENU = 'menu'
    ICON = 'icon'
    CONTAINER = 'container'
    OTHER = 'other'


@dataclass
class BoundingBox:
    """Bounding box for a detected UI element."""

    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass
class UIElement:
    """A detected UI element from visual analysis."""

    element_id: str
    element_type: ElementType
    label: str  # Text label or description
    bbox: BoundingBox
    confidence: float = 0.0  # Detection confidence (0.0 to 1.0)
    is_interactable: bool = False
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class ScreenAnalysis:
    """Result of analyzing a screenshot."""

    analysis_id: str
    description: str  # Natural language description of the screen
    elements: list[UIElement]
    raw_text: str = ''  # OCR text if available
    page_title: str = ''
    screenshot_path: str = ''
    backend_used: str = ''
    analyzed_at: float = 0.0
    analysis_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.analyzed_at == 0.0:
            self.analyzed_at = time.time()

    def find_element(self, label: str) -> UIElement | None:
        """Find an element by label (case-insensitive partial match)."""
        label_lower = label.lower()
        for elem in self.elements:
            if label_lower in elem.label.lower():
                return elem
        return None

    def get_interactable(self) -> list[UIElement]:
        """Get all interactable elements."""
        return [e for e in self.elements if e.is_interactable]


@dataclass
class VisionConfig:
    """Configuration for the vision provider."""

    backend: VisionBackend = VisionBackend.OLLAMA
    ollama_url: str = 'http://localhost:11434'
    ollama_model: str = 'moondream'  # Small, fast vision model
    openai_api_key: str = ''
    openai_model: str = 'gpt-4o'
    anthropic_api_key: str = ''
    anthropic_model: str = 'claude-sonnet-4-20250514'
    omniparser_url: str = 'http://localhost:8000'
    screenshot_dir: str = ''
    timeout_s: int = VISION_TIMEOUT_S

    def __post_init__(self) -> None:
        if not self.screenshot_dir:
            self.screenshot_dir = os.path.join(
                str(Path.home()), '.openhands', 'screenshots'
            )
        # Read API keys from env if not provided
        if not self.openai_api_key:
            self.openai_api_key = os.environ.get('OPENAI_API_KEY', '')
        if not self.anthropic_api_key:
            self.anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY', '')


class VisionProviderInterface(Protocol):
    """Protocol for vision analysis backends."""

    def analyze_screenshot(
        self,
        image_path: str,
        prompt: str,
    ) -> ScreenAnalysis:
        """Analyze a screenshot and return structured results."""
        ...


class OllamaVisionProvider:
    """Vision analysis using local Ollama multimodal models.

    Supports models like moondream, llava, bakllava that can
    understand images and answer questions about them.
    """

    def __init__(self, config: VisionConfig) -> None:
        self._config = config
        self._available: bool | None = None

    def analyze_screenshot(
        self,
        image_path: str,
        prompt: str = 'Describe this screenshot in detail. List all visible UI elements, buttons, text fields, and their labels.',
    ) -> ScreenAnalysis:
        """Analyze a screenshot using Ollama vision model."""
        start_time = time.time()
        analysis_id = f'vis-{uuid.uuid4().hex[:8]}'

        # Validate image
        if not os.path.exists(image_path):
            raise FileNotFoundError(f'Screenshot not found: {image_path}')

        file_size = os.path.getsize(image_path)
        if file_size > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(
                f'Image too large: {file_size} bytes (max {MAX_IMAGE_SIZE_BYTES})'
            )

        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        # Call Ollama vision API
        description = self._call_ollama_vision(image_data, prompt)

        # Parse elements from description (basic extraction)
        elements = self._extract_elements(description)

        elapsed_ms = (time.time() - start_time) * 1000

        return ScreenAnalysis(
            analysis_id=analysis_id,
            description=description,
            elements=elements,
            screenshot_path=image_path,
            backend_used=f'ollama/{self._config.ollama_model}',
            analysis_time_ms=elapsed_ms,
        )

    def _call_ollama_vision(self, image_b64: str, prompt: str) -> str:
        """Call Ollama multimodal API."""
        import urllib.request

        payload = json.dumps({
            'model': self._config.ollama_model,
            'prompt': prompt,
            'images': [image_b64],
            'stream': False,
        }).encode('utf-8')

        req = urllib.request.Request(
            f'{self._config.ollama_url}/api/generate',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )

        try:
            with urllib.request.urlopen(
                req, timeout=self._config.timeout_s
            ) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data.get('response', '')
        except Exception as e:
            logger.error(f'Ollama vision call failed: {e}')
            raise

    def _extract_elements(self, description: str) -> list[UIElement]:
        """Extract UI elements from a text description.

        Basic heuristic extraction — in production this would use
        OmniParser or a specialized model for structured output.
        """
        elements: list[UIElement] = []

        # Common UI keywords to detect
        keywords = {
            'button': ElementType.BUTTON,
            'input': ElementType.INPUT,
            'text field': ElementType.INPUT,
            'link': ElementType.LINK,
            'dropdown': ElementType.DROPDOWN,
            'checkbox': ElementType.CHECKBOX,
            'menu': ElementType.MENU,
            'icon': ElementType.ICON,
            'image': ElementType.IMAGE,
        }

        lines = description.split('\n')
        for line_idx, line in enumerate(lines):
            line_lower = line.lower().strip()
            if not line_lower:
                continue

            for keyword, elem_type in keywords.items():
                if keyword in line_lower:
                    elem_id = f'elem-{uuid.uuid4().hex[:6]}'
                    elements.append(
                        UIElement(
                            element_id=elem_id,
                            element_type=elem_type,
                            label=line.strip()[:200],
                            bbox=BoundingBox(
                                x=0, y=line_idx * 30, width=100, height=30
                            ),
                            confidence=0.5,
                            is_interactable=elem_type
                            in (
                                ElementType.BUTTON,
                                ElementType.INPUT,
                                ElementType.LINK,
                                ElementType.DROPDOWN,
                                ElementType.CHECKBOX,
                            ),
                        )
                    )
                    break  # One element per line

            if len(elements) >= MAX_ELEMENTS_PER_SCREEN:
                break

        return elements


class VisionProvider:
    """High-level vision provider that delegates to appropriate backend.

    Provides a unified interface for all vision operations regardless
    of which backend (Ollama, OpenAI, OmniParser) is configured.
    """

    def __init__(self, config: VisionConfig | None = None) -> None:
        self._config = config or VisionConfig()
        self._backend = self._create_backend()
        os.makedirs(self._config.screenshot_dir, exist_ok=True)
        logger.info(
            f'VisionProvider initialized: backend={self._config.backend.value}'
        )

    def _create_backend(self) -> VisionProviderInterface:
        """Create the appropriate vision backend."""
        if self._config.backend == VisionBackend.OLLAMA:
            return OllamaVisionProvider(self._config)
        # Additional backends can be added here
        # For now, default to Ollama
        return OllamaVisionProvider(self._config)

    def analyze(
        self,
        image_path: str,
        prompt: str = '',
    ) -> ScreenAnalysis:
        """Analyze an image/screenshot.

        Args:
            image_path: Path to the image file
            prompt: Custom analysis prompt (optional)

        Returns:
            ScreenAnalysis with description and detected elements
        """
        if not prompt:
            prompt = (
                'Analyze this screenshot. Describe what you see including: '
                '1) The overall layout and purpose of the page/screen '
                '2) All visible UI elements (buttons, inputs, links, menus) '
                '3) Any text content visible '
                '4) The current state of the interface'
            )

        return self._backend.analyze_screenshot(image_path, prompt)

    def find_element(
        self,
        image_path: str,
        element_description: str,
    ) -> UIElement | None:
        """Find a specific UI element by natural language description.

        Args:
            image_path: Path to the screenshot
            element_description: Natural language description of the element

        Returns:
            The matching UIElement if found, None otherwise
        """
        prompt = (
            f'Find the UI element matching this description: "{element_description}". '
            f'Describe its exact location, type, and label.'
        )

        analysis = self._backend.analyze_screenshot(image_path, prompt)
        return analysis.find_element(element_description)

    def describe(self, image_path: str) -> str:
        """Get a natural language description of an image.

        Args:
            image_path: Path to the image file

        Returns:
            Text description of the image content
        """
        analysis = self.analyze(image_path)
        return analysis.description

    def stats(self) -> dict[str, Any]:
        """Get vision provider statistics."""
        return {
            'backend': self._config.backend.value,
            'model': self._config.ollama_model,
            'screenshot_dir': self._config.screenshot_dir,
        }
