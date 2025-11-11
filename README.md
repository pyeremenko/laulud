# Laulud - Estonian Song Generator

Automated Estonian song generation and evaluation system using multiple AI models via OpenRouter API.

## Overview

This project automates the process of:
1. Generating Estonian songs based on Bible passages using multiple AI models
2. Evaluating all generated variants using the same models
3. Scoring the songs with a points system (with penalty for self-votes)
4. Outputting the top 2 songs

## Prerequisites

- **pyenv** - Python version management
- **uv** - Fast Python package manager
- **OpenRouter API key** - Get one at [openrouter.ai](https://openrouter.ai)

## Setup

1. **Install Python version:**
   ```bash
   pyenv install
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Configure OpenRouter API key:**
   ```bash
   export OPENROUTER_API_KEY='your-api-key-here'
   ```

   Add this to your `~/.bashrc` or `~/.zshrc` to persist across sessions.

4. **Configure models:**

   Edit `config/models.yaml` to enable/disable models:
   ```yaml
   models:
     - name: "anthropic/claude-3.5-sonnet"
       is_enabled: true

     - name: "openai/gpt-4-turbo"
       is_enabled: false
   ```

## Usage

### Basic Usage

```bash
uv run python src/generate_song.py config/song_input_example.yaml
```

### Dry Run (Preview without API calls)

```bash
uv run python src/generate_song.py config/song_input_example.yaml --dry-run
```

### Creating a Song Input File

Create a YAML file with your song parameters:

```yaml
# Topic of the song
topic: "Meie Isa Palve"

# Bible chapter reference
chapter: "Matthew 6:9-13"

# Verse numbers for couplets
couplet_verse_numbers: "9-13"

# Text of verses for couplets
couplet_verses_text: |
  9 Teie palvetage nõnda: Meie Isa, kes sa oled taevas...

# Verse numbers for chorus
chorus_verse_numbers: "6"

# Text of verses for chorus
chorus_verses_text: |
  6 Aga sina, kui sa palvetad, mine oma kambrisse...

# Output filename (without .md extension)
output_filename: "my_song"
```

See `config/song_input_example.yaml` for a complete example.

## How It Works

### Generation Phase
Each enabled model in `config/models.yaml` generates a song variant using the `prompts/writing.hbs` template.

### Evaluation Phase
Each model evaluates all generated songs using the `prompts/evaluation.hbs` template and returns its top 3 choices.

### Scoring System
- **1st place:** 5 points
- **2nd place:** 4 points
- **3rd place:** 3 points
- **4th place:** 2 points
- **5th place:** 1 point

**Self-vote penalty:** If a model ranks its own generated song as 1st place, it only receives 2.5 points instead of 5 (50% penalty).

### Output
The top 2 songs (by total points) are saved to `songs/{output_filename}.md`.

## Project Structure

```
laulud/
├── src/
│   └── generate_song.py    # Main script
├── config/
│   ├── models.yaml          # Model configuration
│   └── song_input_example.yaml  # Example input
├── prompts/
│   ├── writing.hbs          # Song generation template
│   └── evaluation.hbs       # Song evaluation template
├── songs/                   # Generated songs output
├── pyproject.toml          # Python dependencies
└── .python-version         # Python version
```

## Troubleshooting

### API Key Issues
If you get authentication errors:
```bash
echo $OPENROUTER_API_KEY  # Check if key is set
```

### No Models Enabled
Ensure at least one model in `config/models.yaml` has `is_enabled: true`.

### Parsing Errors
If evaluations fail to parse, check that the evaluation prompt in `prompts/evaluation.hbs` produces clear "Option 1", "Option 2", etc. rankings.

## Model Configuration

The system supports any models available on OpenRouter. See [OpenRouter Models](https://openrouter.ai/docs/models) for a complete list.

Popular options:
- `anthropic/claude-3.5-sonnet` - High quality, good at creative writing
- `openai/gpt-4-turbo` - Well-balanced performance
- `google/gemini-pro-1.5` - Fast and cost-effective
- `meta-llama/llama-3.1-70b-instruct` - Open source option

## Cost Estimation

API costs vary by model. Check [OpenRouter Pricing](https://openrouter.ai/docs/pricing) for current rates.

For a typical run with 4 enabled models:
- 4 generation calls (~2000 tokens output each)
- 4 evaluation calls (~1000 tokens output each)

Estimated cost: $0.10-$0.50 depending on models chosen.

## License

This project is for personal use in creating Estonian worship songs based on Biblical texts.
