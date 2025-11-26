# IDesign
This is the official Github Repo for [*I-Design: Personalized LLM Interior Designer*](https://atcelen.github.io/I-Design/)

## Requirements

### Quick Setup (using uv - Recommended)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/atcelen/IDesign.git
cd IDesign
uv sync

# Set your OpenAI API key
export OPENAI_API_KEY="your-api-key-here"
```

### Alternative: Using OAI_CONFIG_LIST.json

Instead of using the environment variable, you can create `OAI_CONFIG_LIST.json`:
```json
[
    {
        "model": "gpt-4",
        "api_key": "YOUR_API_KEY"
    },
    {
        "model": "gpt-4-1106-preview",
        "api_key": "YOUR_API_KEY"
    }
]
```

### 3D Asset Retrieval Dependencies

For the full pipeline including 3D asset retrieval (`retrieve.py`), install additional dependencies:
```bash
# Install retrieval extras
uv sync --extra retrieval

# Install DGL (requires special wheel index)
uv pip install dgl -f https://data.dgl.ai/wheels/torch-2.4/cu124/repo.html

# Install OpenShape
git clone https://huggingface.co/OpenShape/openshape-demo-support
uv pip install ./openshape-demo-support
```

### Blender for Rendering

For rendering scenes, download portable Blender:
```bash
cd ~
curl -L -o blender.tar.xz "https://mirror.clarkson.edu/blender/release/Blender4.2/blender-4.2.0-linux-x64.tar.xz"
tar -xf blender.tar.xz
```

## Inference

### Quick Start (Command Line)

The easiest way to generate a scene is using the `generate_scene.py` script:

```bash
source .venv/bin/activate

# Basic usage - room type is auto-detected
python generate_scene.py "A cozy modern living room"

# With custom parameters
python generate_scene.py "A minimalist bedroom" --objects 10 --width 5 --depth 4

# Save to custom file
python generate_scene.py "A home office" -o my_office.json

# Verbose output
python generate_scene.py "A creative studio" -v
```

**Supported room types with auto-detected defaults:**
- bedroom, living room, office, home office, kitchen, dining room, bathroom, studio, nursery, kids room

**Auto mode (`--auto`):** Let GPT-4 intelligently determine room dimensions and object count based on your full prompt. Recommended for complex or descriptive prompts:
```bash
python generate_scene.py "A spacious luxurious master bedroom with reading nook" --auto
```

### Python API

For more control, use the Python API directly:

```python
from IDesign import IDesign

i_design = IDesign(no_of_objects = 15,
                   user_input = "A creative livingroom",
                   room_dimensions = [4.0, 4.0, 2.5])

# Interior Designer, Interior Architect and Engineer
i_design.create_initial_design()
# Layout Corrector
i_design.correct_design()
# Layout Refiner
i_design.refine_design()
# Backtracking Algorithm
i_design.create_object_clusters(verbose=False)
i_design.backtrack(verbose=True)
i_design.to_json()
```

### Full Pipeline: Scene Generation to Render

Complete workflow from text prompt to rendered image:

```bash
# 1. Activate environment
source .venv/bin/activate

# 2. Generate scene graph from text prompt
python generate_scene.py "A modern home office with desk and bookshelf"

# 3. Retrieve 3D assets from Objaverse
python retrieve.py

# 4. Render in Blender (headless)
~/blender-4.2.0-linux-x64/blender --background --python place_in_blender.py
```

This produces:
- `scene_graph.json` - Scene layout with object positions
- `Assets/` - Downloaded 3D models (.glb files)
- `scene.blend` - Blender scene file
- `render.png` - Rendered image

## Evaluation
After creating scene renders in Blender, you can use the GPT-V evaluator to generate grades for evaluation. Fill in the necessary variables denoted with TODO and run the script
```bash
python gpt_v_as_evaluator.py
```

## Results
![gallery](imgs/gallery.jpg)
