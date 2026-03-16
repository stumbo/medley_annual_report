#!/usr/bin/env python3
"""
Extract and count all email headers from .eml files efficiently.
Processes in batches and saves results incrementally.
"""
import email
from pathlib import Path
from collections import defaultdict
import json

folder = Path("/home/wstumbo/development/medley_annual_report/lispUsers")
eml_files = sorted(list(folder.glob("*.eml")))

print(f"Found {len(eml_files)} email files")

header_counts = defaultdict(int)
batch_size = 500
total_files = len(eml_files)

for batch_num, i in enumerate(range(0, total_files, batch_size)):
    batch_files = eml_files[i:i+batch_size]
    
    for eml_file in batch_files:
        try:
            with open(eml_file, 'rb') as f:
                msg = email.message_from_binary_file(f)
                for header_name in msg.keys():
                    header_counts[header_name] += 1
        except:
            pass
    
    processed = min(i + batch_size, total_files)
    print(f"Batch {batch_num + 1}: Processed {processed}/{total_files} files")

# Sort and prepare output
sorted_headers = sorted(header_counts.items(), key=lambda x: (-x[1], x[0]))

# Save as JSON
output_json = '/home/wstumbo/development/medley_annual_report/email_headers.json'
with open(output_json, 'w') as f:
    json.dump({
        'total_files': total_files,
        'total_unique_headers': len(header_counts),
        'headers': [{'name': h, 'count': c, 'percentage': round((c/total_files)*100, 2)} 
                    for h, c in sorted_headers]
    }, f, indent=2)

# Save as text report
output_txt = '/home/wstumbo/development/medley_annual_report/email_headers.txt'
with open(output_txt, 'w') as f:
    f.write("="*70 + "\n")
    f.write(f"Email Header Analysis - {total_files} files processed\n")
    f.write("="*70 + "\n\n")
    f.write(f"{'Header Name':<40} {'Count':>10} {'Percentage':>15}\n")
    f.write("-" * 70 + "\n")
    
    for header_name, count in sorted_headers:
        percentage = (count / total_files) * 100
        f.write(f"{header_name:<40} {count:>10} {percentage:>14.1f}%\n")
    
    f.write("-" * 70 + "\n")
    f.write(f"{'Total unique headers':<40} {len(header_counts):>10}\n")
    f.write("="*70 + "\n")

print(f"\nComplete!")
print(f"Processed {total_files} files")
print(f"Found {len(header_counts)} unique headers")
print(f"Results saved to:")
print(f"  - {output_json}")
print(f"  - {output_txt}")
