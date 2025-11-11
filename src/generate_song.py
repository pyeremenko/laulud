#!/usr/bin/env python3
"""
Estonian Song Generation and Evaluation Script

This script automates the process of generating Estonian songs based on Bible
passages using multiple AI models, then evaluating them to find the best versions.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple

import yaml
import requests
from pybars import Compiler


# Constants
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
CONFIG_DIR = PROJECT_ROOT / "config"
SONGS_DIR = PROJECT_ROOT / "songs"

# Scoring configuration
FIRST_PLACE_POINTS = 5
SELF_VOTE_PENALTY = 0.5  # Multiplier for self-votes


class SongGenerator:
    """Handles song generation and evaluation workflow"""

    def __init__(self, api_key: str, dry_run: bool = False):
        self.api_key = api_key
        self.dry_run = dry_run
        self.compiler = Compiler()

    def load_models(self) -> List[Dict[str, Any]]:
        """Load enabled models from configuration"""
        models_file = CONFIG_DIR / "models.yaml"
        with open(models_file, 'r') as f:
            config = yaml.safe_load(f)

        enabled_models = [m for m in config['models'] if m['is_enabled']]
        if not enabled_models:
            raise ValueError("No enabled models found in config/models.yaml")

        print(f"✓ Loaded {len(enabled_models)} enabled model(s)")
        for model in enabled_models:
            print(f"  - {model['name']}")
        print()

        return enabled_models

    def load_song_input(self, input_file: Path) -> Dict[str, Any]:
        """Load song input parameters from YAML file"""
        with open(input_file, 'r') as f:
            song_input = yaml.safe_load(f)

        required_fields = [
            'topic', 'chapter', 'couplet_verse_numbers', 'couplet_verses_text',
            'chorus_verse_numbers', 'chorus_verses_text', 'output_filename'
        ]

        missing = [f for f in required_fields if f not in song_input]
        if missing:
            raise ValueError(f"Missing required fields in input file: {', '.join(missing)}")

        print(f"✓ Loaded song parameters:")
        print(f"  Topic: {song_input['topic']}")
        print(f"  Chapter: {song_input['chapter']}")
        print(f"  Output: songs/{song_input['output_filename']}.md")
        print()

        return song_input

    def load_template(self, template_name: str) -> Any:
        """Load and compile a Handlebars template"""
        template_file = PROMPTS_DIR / f"{template_name}.hbs"
        with open(template_file, 'r') as f:
            template_content = f.read()
        return self.compiler.compile(template_content)

    def call_openrouter(self, model: str, prompt: str) -> str:
        """Call OpenRouter API with the given model and prompt"""
        if self.dry_run:
            return f"[DRY RUN] Would call {model} with prompt length: {len(prompt)}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        try:
            response = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=data,
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except requests.exceptions.RequestException as e:
            print(f"  ✗ API Error: {e}")
            raise

    def generate_songs(self, models: List[Dict[str, Any]], song_input: Dict[str, Any]) -> Dict[str, str]:
        """Generate song variants using each model"""
        print("=" * 60)
        print("PHASE 1: GENERATING SONGS")
        print("=" * 60)
        print()

        writing_template = self.load_template("writing")
        prompt = writing_template(song_input)

        songs = {}
        for i, model in enumerate(models, 1):
            model_name = model['name']
            print(f"[{i}/{len(models)}] Generating with {model_name}...")

            try:
                song_text = self.call_openrouter(model_name, prompt)
                songs[model_name] = song_text
                print(f"  ✓ Generated ({len(song_text)} chars)")
            except Exception as e:
                print(f"  ✗ Failed: {e}")
                songs[model_name] = None

            print()

        successful = sum(1 for s in songs.values() if s is not None)
        print(f"Successfully generated {successful}/{len(models)} songs")
        print()

        return songs

    def evaluate_songs(
        self,
        models: List[Dict[str, Any]],
        songs: Dict[str, str],
        topic: str
    ) -> Dict[str, List[int]]:
        """Evaluate songs using each model"""
        print("=" * 60)
        print("PHASE 2: EVALUATING SONGS")
        print("=" * 60)
        print()

        evaluation_template = self.load_template("evaluation")

        # Prepare songs text for evaluation
        song_list = []
        model_names = list(songs.keys())
        for i, model_name in enumerate(model_names, 1):
            if songs[model_name] is not None:
                song_list.append(f"## Option {i}\n\n{songs[model_name]}")

        songs_text = "\n\n".join(song_list)

        evaluation_input = {
            'count': len(song_list),
            'topic': topic,
            'songs_text': songs_text
        }

        prompt = evaluation_template(evaluation_input)

        evaluations = {}
        for i, model in enumerate(models, 1):
            model_name = model['name']
            print(f"[{i}/{len(models)}] Evaluating with {model_name}...")

            try:
                eval_result = self.call_openrouter(model_name, prompt)
                rankings = self.parse_evaluation_result(eval_result, len(song_list))
                evaluations[model_name] = rankings
                print(f"  ✓ Rankings: {rankings}")
            except Exception as e:
                print(f"  ✗ Failed: {e}")
                evaluations[model_name] = None

            print()

        return evaluations

    def parse_evaluation_result(self, eval_text: str, num_songs: int) -> List[int]:
        """
        Parse evaluation result to extract rankings.
        Returns list of option numbers in order from best to worst.
        """
        # Try to extract "Option X" patterns
        import re
        options = re.findall(r'Option\s+(\d+)', eval_text, re.IGNORECASE)

        if options:
            # Convert to integers and take first 3
            rankings = [int(opt) for opt in options[:3]]
            return rankings

        # Fallback: return empty list if parsing fails
        print(f"    Warning: Could not parse rankings from evaluation")
        return []

    def calculate_scores(
        self,
        songs: Dict[str, str],
        evaluations: Dict[str, List[int]]
    ) -> Dict[str, float]:
        """Calculate final scores for each song"""
        print("=" * 60)
        print("PHASE 3: CALCULATING SCORES")
        print("=" * 60)
        print()

        model_names = list(songs.keys())
        scores = {model: 0.0 for model in model_names}

        # Points for each position
        points_map = {
            1: FIRST_PLACE_POINTS,
            2: FIRST_PLACE_POINTS - 1,
            3: FIRST_PLACE_POINTS - 2,
            4: FIRST_PLACE_POINTS - 3,
            5: FIRST_PLACE_POINTS - 4,
        }

        print("Scoring breakdown:")
        print()

        for evaluator_model, rankings in evaluations.items():
            if rankings is None or len(rankings) == 0:
                print(f"  {evaluator_model}: [skipped - evaluation failed]")
                continue

            print(f"  {evaluator_model}:")
            evaluator_idx = model_names.index(evaluator_model)

            for rank, option_num in enumerate(rankings, 1):
                if rank > 5:  # Only top 5 get points
                    break

                song_idx = option_num - 1  # Convert to 0-indexed
                if song_idx < 0 or song_idx >= len(model_names):
                    continue

                song_model = model_names[song_idx]
                base_points = points_map.get(rank, 0)

                # Apply self-vote penalty
                if song_idx == evaluator_idx:
                    points = base_points * SELF_VOTE_PENALTY
                    print(f"    #{rank} Option {option_num} ({song_model}): {points:.1f} pts (self-vote)")
                else:
                    points = base_points
                    print(f"    #{rank} Option {option_num} ({song_model}): {points:.1f} pts")

                scores[song_model] += points

            print()

        return scores

    def save_top_songs(
        self,
        songs: Dict[str, str],
        scores: Dict[str, float],
        output_filename: str,
        topic: str
    ):
        """Save the top 2 songs to output file"""
        print("=" * 60)
        print("FINAL RESULTS")
        print("=" * 60)
        print()

        # Sort by score
        sorted_songs = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        print("All scores:")
        for model, score in sorted_songs:
            print(f"  {model}: {score:.1f} points")
        print()

        # Get top 2
        top_2 = sorted_songs[:2]

        print(f"Top 2 songs will be saved to: songs/{output_filename}.md")
        print()

        if self.dry_run:
            print("[DRY RUN] Skipping file write")
            return

        # Create output content
        output_lines = [f"# {topic}", ""]

        for rank, (model, score) in enumerate(top_2, 1):
            song_text = songs[model]
            output_lines.append(f"## Variant {rank}")
            output_lines.append("")
            output_lines.append(f"Points: {score:.1f}")
            output_lines.append("")
            output_lines.append(f"Model: {model}")
            output_lines.append("")
            output_lines.append(song_text)
            output_lines.append("")
            output_lines.append("")

        # Save to file
        SONGS_DIR.mkdir(exist_ok=True)
        output_file = SONGS_DIR / f"{output_filename}.md"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))

        print(f"✓ Saved successfully!")


def main():
    parser = argparse.ArgumentParser(
        description="Generate and evaluate Estonian songs using AI models"
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to YAML file with song parameters"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without making API calls"
    )

    args = parser.parse_args()

    # Check API key
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key and not args.dry_run:
        print("Error: OPENROUTER_API_KEY environment variable not set")
        print("Please set it with: export OPENROUTER_API_KEY='your-key-here'")
        sys.exit(1)

    # Validate input file
    if not args.input_file.exists():
        print(f"Error: Input file not found: {args.input_file}")
        sys.exit(1)

    if args.dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No API calls will be made")
        print("=" * 60)
        print()

    try:
        generator = SongGenerator(api_key, dry_run=args.dry_run)

        # Load configuration
        models = generator.load_models()
        song_input = generator.load_song_input(args.input_file)

        # Generate songs
        songs = generator.generate_songs(models, song_input)

        # Filter out failed generations
        valid_songs = {k: v for k, v in songs.items() if v is not None}
        if len(valid_songs) < 2:
            print("Error: Not enough songs generated successfully (need at least 2)")
            sys.exit(1)

        # Evaluate songs
        evaluations = generator.evaluate_songs(
            models,
            valid_songs,
            song_input['topic']
        )

        # Calculate scores
        scores = generator.calculate_scores(valid_songs, evaluations)

        # Save results
        generator.save_top_songs(
            valid_songs,
            scores,
            song_input['output_filename'],
            song_input['topic']
        )

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
