import json
import os
from typing import Dict, Any
from pathlib import Path

class PromptLoader:
    """Load and manage versioned prompts for essay evaluation."""
    
    def __init__(self, prompts_dir: str = "prompts", version: str = "v1.0.0"):
        self.prompts_dir = Path(prompts_dir)
        self.version = version
        self._prompts_cache: Dict[str, Dict[str, str]] = {}
        self._load_prompts()
    
    def _load_prompts(self):
        """Load all prompts from the versioned directory."""
        version_dir = self.prompts_dir / self.version
        
        if not version_dir.exists():
            raise FileNotFoundError(
                f"Prompts directory not found: {version_dir}. "
                f"Please ensure the prompts are properly set up in {version_dir}"
            )
        
        # Load prompts from JSON files
        required_files = ["introduction.json", "body.json", "conclusion.json", "grammar.json"]
        
        for filename in required_files:
            json_file = version_dir / filename
            if not json_file.exists():
                raise FileNotFoundError(f"Required prompt file not found: {json_file}")
                
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    prompts_data = json.load(f)
                    rubric_item = json_file.stem
                    self._prompts_cache[rubric_item] = prompts_data
                    
                # Validate that all required levels are present
                required_levels = ["Basic", "Intermediate", "Advanced", "Expert"]
                for level in required_levels:
                    if level not in prompts_data:
                        raise ValueError(f"Missing level '{level}' in {json_file}")
                        
            except Exception as e:
                raise RuntimeError(f"Error loading prompts from {json_file}: {e}")
    
    def load_prompt(self, rubric_item: str, level_group: str) -> str:
        """Load a specific prompt for given rubric item and level."""
        if rubric_item not in self._prompts_cache:
            available_items = list(self._prompts_cache.keys())
            raise ValueError(
                f"No prompts found for rubric item: '{rubric_item}'. "
                f"Available items: {available_items}"
            )
        
        level_prompts = self._prompts_cache[rubric_item]
        if level_group not in level_prompts:
            available_levels = list(level_prompts.keys())
            raise ValueError(
                f"No prompt found for level: '{level_group}' in rubric: '{rubric_item}'. "
                f"Available levels: {available_levels}"
            )
        
        return level_prompts[level_group]
    
    def get_available_rubric_items(self) -> list:
        """Get list of available rubric items."""
        return list(self._prompts_cache.keys())
    
    def get_available_levels(self, rubric_item: str) -> list:
        """Get list of available levels for a specific rubric item."""
        if rubric_item not in self._prompts_cache:
            return []
        return list(self._prompts_cache[rubric_item].keys())
    
    def reload_prompts(self):
        """Reload prompts from files (useful for development/testing)."""
        self._prompts_cache.clear()
        self._load_prompts()