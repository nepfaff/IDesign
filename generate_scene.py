#!/usr/bin/env python3
"""
Generate interior design scenes from text prompts.

Usage:
    python generate_scene.py "A cozy modern living room"
    python generate_scene.py "A minimalist bedroom" --objects 10 --width 4 --depth 3.5 --height 2.5
    python generate_scene.py "A home office" -o output.json
    python generate_scene.py "A luxurious master suite" --auto  # Let GPT-4 decide parameters
"""

import argparse
import sys
import re
import os
import json
from IDesign import IDesign


def get_openai_client():
    """Get OpenAI client for auto mode."""
    try:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        return OpenAI(api_key=api_key)
    except ImportError:
        raise ImportError("openai package required for --auto mode. Install with: pip install openai")


def auto_determine_parameters(prompt: str) -> dict:
    """
    Use GPT-4 to determine optimal room dimensions and object count based on the prompt.

    This approach is inspired by SceneWeaver's evaluation methodology where scene completeness
    is measured by object density and functional coverage.
    """
    client = get_openai_client()

    system_prompt = """You are an expert interior designer. Given a room description, determine:
1. Optimal room dimensions (width, depth, height in meters)
2. Appropriate number of objects to place

Consider:
- Room type and typical sizes (e.g., bathrooms are smaller than living rooms)
- Descriptive words like "spacious", "cozy", "large", "small"
- Functional requirements (a home office needs desk, chair, shelving; a bedroom needs bed, nightstands)
- Scene completeness - rooms should feel furnished but not cluttered
- For bedrooms: typically 8-15 objects
- For living rooms: typically 12-20 objects
- For offices: typically 8-12 objects
- For studios/open plans: typically 15-25 objects

Respond with ONLY a JSON object in this exact format:
{
    "room_type": "detected room type",
    "width": <float>,
    "depth": <float>,
    "height": <float>,
    "num_objects": <int>,
    "reasoning": "brief explanation"
}"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Room description: {prompt}"}
        ],
        temperature=0.3,
    )

    content = response.choices[0].message.content
    # Extract JSON from response (handle potential markdown code blocks)
    if "```" in content:
        match = re.search(r'```(?:json)?\s*([^`]+)\s*```', content, re.DOTALL)
        if match:
            content = match.group(1).strip()

    return json.loads(content)


# Default room configurations based on room type
# Values inspired by typical room sizes and object counts from the paper
ROOM_PRESETS = {
    "bedroom": {
        "dimensions": [4.0, 4.0, 2.5],
        "objects": 12,
    },
    "living room": {
        "dimensions": [5.0, 5.0, 2.5],
        "objects": 15,
    },
    "livingroom": {
        "dimensions": [5.0, 5.0, 2.5],
        "objects": 15,
    },
    "office": {
        "dimensions": [3.5, 3.5, 2.5],
        "objects": 10,
    },
    "home office": {
        "dimensions": [3.5, 3.5, 2.5],
        "objects": 10,
    },
    "kitchen": {
        "dimensions": [4.0, 3.5, 2.5],
        "objects": 12,
    },
    "dining room": {
        "dimensions": [4.0, 4.0, 2.5],
        "objects": 10,
    },
    "bathroom": {
        "dimensions": [2.5, 2.0, 2.5],
        "objects": 6,
    },
    "studio": {
        "dimensions": [6.0, 5.0, 2.5],
        "objects": 18,
    },
    "nursery": {
        "dimensions": [3.5, 3.5, 2.5],
        "objects": 10,
    },
    "kids room": {
        "dimensions": [4.0, 4.0, 2.5],
        "objects": 12,
    },
}

# Default fallback
DEFAULT_CONFIG = {
    "dimensions": [4.0, 4.0, 2.5],
    "objects": 12,
}


def detect_room_type(prompt: str) -> dict:
    """Detect room type from prompt and return appropriate defaults."""
    prompt_lower = prompt.lower()

    for room_type, config in ROOM_PRESETS.items():
        if room_type in prompt_lower:
            print(f"Detected room type: {room_type}")
            return config

    print("No specific room type detected, using default configuration")
    return DEFAULT_CONFIG


def generate_scene(
    prompt: str,
    num_objects: int = None,
    width: float = None,
    depth: float = None,
    height: float = None,
    output_file: str = "scene_graph.json",
    verbose: bool = False,
    auto_mode: bool = False,
):
    """
    Generate a scene from a text prompt.

    Args:
        prompt: Text description of the desired room
        num_objects: Number of objects to place (auto-detected if not specified)
        width: Room width in meters (auto-detected if not specified)
        depth: Room depth in meters (auto-detected if not specified)
        height: Room height in meters (default 2.5m)
        output_file: Output JSON file path
        verbose: Print detailed progress
        auto_mode: Use GPT-4 to determine optimal parameters
    """
    if auto_mode:
        print("\n[Auto Mode] Asking GPT-4 to determine optimal room parameters...")
        auto_params = auto_determine_parameters(prompt)
        print(f"  Room type: {auto_params['room_type']}")
        print(f"  Reasoning: {auto_params['reasoning']}")

        # Use auto-determined values unless explicitly overridden
        if width is None:
            width = auto_params["width"]
        if depth is None:
            depth = auto_params["depth"]
        if height is None:
            height = auto_params["height"]
        if num_objects is None:
            num_objects = auto_params["num_objects"]

        room_dimensions = [width, depth, height]
    else:
        # Get defaults based on room type detection
        defaults = detect_room_type(prompt)

        # Use provided values or fall back to detected defaults
        room_dimensions = [
            width if width is not None else defaults["dimensions"][0],
            depth if depth is not None else defaults["dimensions"][1],
            height if height is not None else defaults["dimensions"][2],
        ]

        if num_objects is None:
            num_objects = defaults["objects"]

    print(f"\n{'='*60}")
    print(f"IDesign Scene Generator")
    print(f"{'='*60}")
    print(f"Prompt: {prompt}")
    print(f"Room dimensions: {room_dimensions[0]}m x {room_dimensions[1]}m x {room_dimensions[2]}m")
    print(f"Number of objects: {num_objects}")
    print(f"Output file: {output_file}")
    print(f"{'='*60}\n")

    # Create IDesign instance
    print("Initializing IDesign...")
    i_design = IDesign(
        no_of_objects=num_objects,
        user_input=prompt,
        room_dimensions=room_dimensions,
    )

    # Run the pipeline
    print("\n[1/5] Creating initial design (Interior Designer + Architect + Engineer)...")
    i_design.create_initial_design()

    print("\n[2/5] Correcting design (Layout Corrector)...")
    i_design.correct_design(verbose=verbose)

    print("\n[3/5] Refining design (Layout Refiner)...")
    i_design.refine_design(verbose=verbose)

    print("\n[4/5] Creating object clusters...")
    i_design.create_object_clusters(verbose=verbose)

    print("\n[5/5] Running backtracking algorithm for positioning...")
    i_design.backtrack(verbose=verbose)

    # Save output
    print(f"\nSaving scene graph to {output_file}...")
    i_design.to_json(output_file)

    print(f"\n{'='*60}")
    print(f"SUCCESS! Scene generated and saved to {output_file}")
    print(f"{'='*60}\n")

    return i_design


def main():
    parser = argparse.ArgumentParser(
        description="Generate interior design scenes from text prompts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "A cozy modern living room"
  %(prog)s "A minimalist bedroom" --objects 10
  %(prog)s "A home office" --width 4 --depth 3.5
  %(prog)s "A creative studio apartment" -o my_scene.json -v
  %(prog)s "A luxurious master suite with walk-in closet" --auto

Modes:
  Default: Auto-detects room type from prompt and uses preset defaults
  --auto:  Uses GPT-4 to intelligently determine room size and object count
           based on the full prompt description (recommended for complex prompts)

Room types with auto-detected defaults:
  bedroom, living room, office, home office, kitchen,
  dining room, bathroom, studio, nursery, kids room
        """
    )

    parser.add_argument(
        "prompt",
        type=str,
        help="Text description of the desired room (e.g., 'A modern minimalist bedroom')"
    )

    parser.add_argument(
        "--objects", "-n",
        type=int,
        default=None,
        help="Number of objects to place (auto-detected based on room type if not specified)"
    )

    parser.add_argument(
        "--width", "-W",
        type=float,
        default=None,
        help="Room width in meters (auto-detected based on room type if not specified)"
    )

    parser.add_argument(
        "--depth", "-D",
        type=float,
        default=None,
        help="Room depth in meters (auto-detected based on room type if not specified)"
    )

    parser.add_argument(
        "--height", "-H",
        type=float,
        default=None,
        help="Room height in meters (default: 2.5m)"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default="scene_graph.json",
        help="Output JSON file path (default: scene_graph.json)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed progress information"
    )

    parser.add_argument(
        "--auto", "-a",
        action="store_true",
        help="Use GPT-4 to intelligently determine room dimensions and object count based on prompt"
    )

    args = parser.parse_args()

    try:
        generate_scene(
            prompt=args.prompt,
            num_objects=args.objects,
            width=args.width,
            depth=args.depth,
            height=args.height,
            output_file=args.output,
            verbose=args.verbose,
            auto_mode=args.auto,
        )
    except KeyboardInterrupt:
        print("\n\nGeneration cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
