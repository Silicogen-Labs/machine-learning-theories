#!/usr/bin/env python3
"""Build combined RTL bug detection dataset with proper labels."""

import sys
import json
from pathlib import Path
from collections import Counter

# Setup
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rtl_analyzer.engine import AnalysisEngine
from rtl_analyzer.parser import parse_file
from rtl_analyzer.ml.ast_features import extract_ast_features
from rtl_analyzer.models import Severity
from sklearn.model_selection import train_test_split
import pandas as pd
from tqdm import tqdm

def main():
    print("=" * 80)
    print("RTL Bug Detection Dataset Builder")
    print("=" * 80)
    
    # Paths
    fixtures_dir = PROJECT_ROOT / 'tests' / 'fixtures'
    external_dir = PROJECT_ROOT / 'third_party' / 'rtl_corpora'
    dataset_dir = PROJECT_ROOT / 'dataset'
    dataset_dir.mkdir(exist_ok=True)
    
    # Find files
    buggy_files = list((fixtures_dir / 'buggy').glob('*.v'))
    clean_files = list((fixtures_dir / 'clean').glob('*.v'))
    external_files = list(external_dir.rglob('*.v')) + list(external_dir.rglob('*.sv'))
    
    print(f"\nFiles found:")
    print(f"  Buggy fixtures: {len(buggy_files)}")
    print(f"  Clean fixtures: {len(clean_files)}")
    print(f"  External corpus: {len(external_files)}")
    
    # Analyze external corpus
    engine = AnalysisEngine()
    external_labels = []
    
    print(f"\nAnalyzing external corpus (this may take a while)...")
    for filepath in tqdm(external_files, desc="Analyzing"):
        try:
            result = engine.analyze_file(filepath)
            errors = [f for f in result.findings if f.severity == Severity.ERROR]
            warnings = [f for f in result.findings if f.severity == Severity.WARNING]
            
            if errors:
                label = 'buggy'
                bug_types = list(set(f.check_id.value for f in errors))
            elif warnings:
                label = 'warning'
                bug_types = list(set(f.check_id.value for f in warnings))
            else:
                label = 'clean'
                bug_types = []
            
            external_labels.append({
                'file': str(filepath.relative_to(PROJECT_ROOT)),
                'label': label,
                'error_count': len(errors),
                'warning_count': len(warnings),
                'bug_types': bug_types,
                'source': 'external'
            })
        except Exception as e:
            external_labels.append({
                'file': str(filepath.relative_to(PROJECT_ROOT)),
                'label': 'parse_error',
                'error_count': 0,
                'warning_count': 0,
                'bug_types': [],
                'source': 'external',
                'error': str(e)
            })
    
    # Summarize external labels
    label_counts = Counter(d['label'] for d in external_labels)
    print(f"\nExternal corpus labels:")
    for label, count in label_counts.most_common():
        print(f"  {label}: {count}")
    
    # Build combined dataset
    all_data = []
    
    # Add fixtures (ground truth)
    print("\nProcessing fixtures...")
    for filepath in tqdm(buggy_files + clean_files):
        try:
            parsed = parse_file(filepath)
            features = extract_ast_features(parsed)
            label = 'buggy' if 'buggy' in str(filepath) else 'clean'
            all_data.append({
                'file': str(filepath.relative_to(PROJECT_ROOT)),
                'label': label,
                'source': 'fixture',
                'error_count': 0 if label == 'clean' else 1,
                'warning_count': 0,
                'bug_types': [] if label == 'clean' else ['fixture'],
                **features
            })
        except Exception as e:
            print(f"  Skip {filepath.name}: {e}")
    
    # Add external corpus
    print("Processing external corpus...")
    for item in tqdm(external_labels):
        if item['label'] in ('parse_error', 'warning'):
            continue  # Skip for now
        
        filepath = PROJECT_ROOT / item['file']
        try:
            parsed = parse_file(filepath)
            features = extract_ast_features(parsed)
            all_data.append({
                'file': item['file'],
                'label': 'clean' if item['label'] == 'clean' else 'buggy',
                'source': 'external',
                'error_count': item['error_count'],
                'warning_count': item['warning_count'],
                'bug_types': item['bug_types'],
                **features
            })
        except Exception:
            pass
    
    df = pd.DataFrame(all_data)
    print(f"\nCombined dataset: {len(df)} samples")
    print(f"Labels: {df['label'].value_counts().to_dict()}")
    
    # Create splits
    train_df, temp_df = train_test_split(df, test_size=0.3, random_state=42, stratify=df['label'])
    val_df, test_df = train_test_split(temp_df, test_size=0.5, random_state=42, stratify=temp_df['label'])
    
    print(f"\nSplits:")
    print(f"  Train: {len(train_df)} (buggy: {sum(train_df['label']=='buggy')})")
    print(f"  Val: {len(val_df)} (buggy: {sum(val_df['label']=='buggy')})")
    print(f"  Test: {len(test_df)} (buggy: {sum(test_df['label']=='buggy')})")
    
    # Save manifest
    feature_cols = [c for c in df.columns if c not in ['file', 'label', 'source', 'error_count', 'warning_count', 'bug_types']]
    manifest = {
        'total_samples': len(df),
        'feature_columns': feature_cols,
        'splits': {
            'train': {'count': len(train_df), 'files': train_df['file'].tolist()},
            'val': {'count': len(val_df), 'files': val_df['file'].tolist()},
            'test': {'count': len(test_df), 'files': test_df['file'].tolist()}
        },
        'label_distribution': df['label'].value_counts().to_dict(),
        'source_distribution': df['source'].value_counts().to_dict()
    }
    
    manifest_path = dataset_dir / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2))
    
    # Save CSVs
    df.to_csv(dataset_dir / 'dataset.csv', index=False)
    train_df.to_csv(dataset_dir / 'train.csv', index=False)
    val_df.to_csv(dataset_dir / 'val.csv', index=False)
    test_df.to_csv(dataset_dir / 'test.csv', index=False)
    
    print(f"\nDataset saved to: {dataset_dir}")
    print(f"  manifest.json - dataset metadata")
    print(f"  dataset.csv - full dataset")
    print(f"  train.csv, val.csv, test.csv - splits")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
