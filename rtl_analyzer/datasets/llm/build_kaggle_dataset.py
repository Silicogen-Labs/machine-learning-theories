#!/usr/bin/env python3
"""
Combine Kaggle Verilog datasets into Unsloth-ready format.

Datasets:
1. VeriGen (108K samples) - Raw Verilog code
2. Error Correction (1.9K samples) - Instruction + Error + Correct pairs

Output: JSONL format for Unsloth fine-tuning
{
    "instruction": "...",
    "input": "...",
    "output": "..."
}
"""

import pandas as pd
import json
from pathlib import Path
from tqdm import tqdm

# Paths
KAGGLE_DIR = Path(__file__).parent / 'kaggle'
OUTPUT_DIR = Path(__file__).parent
OUTPUT_DIR.mkdir(exist_ok=True)

def process_verigen():
    """Process VeriGen dataset - generate instructions from code"""
    print("\n" + "="*60)
    print("Processing VeriGen Dataset (108K samples)")
    print("="*60)
    
    df = pd.read_csv(KAGGLE_DIR / 'verigen' / 'train.csv')
    print(f"Loaded {len(df)} samples")
    
    formatted = []
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="VeriGen"):
        code = row['text']
        if pd.isna(code) or len(str(code).strip()) < 50:
            continue
        
        # Generate instruction from code characteristics
        code_str = str(code)
        
        # Try to extract module name
        module_name = "design"
        for line in code_str.split('\n')[:20]:
            if 'module' in line.lower():
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == 'module' and i+1 < len(parts):
                        module_name = parts[i+1].split('(')[0].strip()
                        break
        
        # Create instruction
        instruction = f"Generate Verilog code for the {module_name} module"
        
        formatted.append({
            'source': 'verigen',
            'instruction': instruction,
            'input': '',
            'output': code_str,
            'text': f"""### Instruction:
{instruction}

### Response:
{code_str}"""
        })
    
    print(f"✓ Processed {len(formatted)} samples")
    return formatted


def process_error_correction():
    """Process error correction dataset - already has instructions"""
    print("\n" + "="*60)
    print("Processing Error Correction Dataset (1.9K samples)")
    print("="*60)
    
    df = pd.read_csv(KAGGLE_DIR / 'error_correction' / 'formatted_small_df.csv')
    print(f"Loaded {len(df)} samples")
    
    formatted = []
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Error Correction"):
        instruction = row.get('Instruction', '')
        error_code = row.get('Error', '')
        correct_code = row.get('Correct', '')
        
        if pd.isna(instruction) or pd.isna(error_code) or pd.isna(correct_code):
            continue
        
        # Clean up the fields
        instruction = str(instruction).replace('INSTRUCT:', '').strip()
        error_code = str(error_code).replace('CODE:', '').strip()
        correct_code = str(correct_code).replace('CODE:', '').strip()
        
        formatted.append({
            'source': 'error_correction',
            'instruction': f"Fix the errors in this Verilog code: {instruction}",
            'input': error_code,
            'output': correct_code,
            'text': f"""### Instruction:
Fix the errors in this Verilog code: {instruction}

### Input:
{error_code}

### Response:
{correct_code}"""
        })
    
    print(f"✓ Processed {len(formatted)} samples")
    return formatted


def main():
    print("Kaggle Verilog Dataset Combiner for Unsloth")
    print("="*60)
    
    # Process both datasets
    verigen_data = process_verigen()
    error_data = process_error_correction()
    
    # Combine
    all_data = verigen_data + error_data
    print(f"\n✓ Total combined: {len(all_data)} samples")
    
    # Save individual datasets
    print("\nSaving datasets...")
    
    with open(OUTPUT_DIR / 'verigen_unsloth.jsonl', 'w') as f:
        for item in verigen_data:
            f.write(json.dumps(item) + '\n')
    print(f"  ✓ verigen_unsloth.jsonl ({len(verigen_data)} samples)")
    
    with open(OUTPUT_DIR / 'error_correction_unsloth.jsonl', 'w') as f:
        for item in error_data:
            f.write(json.dumps(item) + '\n')
    print(f"  ✓ error_correction_unsloth.jsonl ({len(error_data)} samples)")
    
    with open(OUTPUT_DIR / 'combined_unsloth.jsonl', 'w') as f:
        for item in all_data:
            f.write(json.dumps(item) + '\n')
    print(f"  ✓ combined_unsloth.jsonl ({len(all_data)} samples)")
    
    # Statistics
    print("\n" + "="*60)
    print("DATASET STATISTICS")
    print("="*60)
    
    # Code length stats
    code_lengths = [len(d['output']) for d in all_data if d['output']]
    print(f"\nCode length statistics:")
    print(f"  Min: {min(code_lengths):,} chars")
    print(f"  Max: {max(code_lengths):,} chars")
    print(f"  Mean: {sum(code_lengths)/len(code_lengths):,.0f} chars")
    print(f"  Median: {sorted(code_lengths)[len(code_lengths)//2]:,} chars")
    
    # File sizes
    print(f"\nOutput files:")
    for f in OUTPUT_DIR.glob('*.jsonl'):
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"  {f.name}: {size_mb:.1f} MB")
    
    print("\n✓ Dataset preparation complete!")
    print("\nNext steps:")
    print("1. Review combined_unsloth.jsonl")
    print("2. Run notebook 08_llm_finetuning_unsloth.ipynb")
    print("3. Fine-tune Qwen3.5-2B with QLoRA on Tesla T4")


if __name__ == '__main__':
    main()
