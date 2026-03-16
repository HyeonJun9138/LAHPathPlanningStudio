#!/usr/bin/env python3
"""Check CUDA availability and device info."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent / 'src'))

from engine.training.device import detect_cuda
import json

def main():
    info = detect_cuda()
    print(json.dumps(info, indent=2, default=str))
    if info["available"]:
        print(f"\nCUDA is available with {len(info['devices'])} device(s)")
        for d in info["devices"]:
            print(f"  - {d['name']} ({d['total_memory_mb']} MB)")
    else:
        print("\nCUDA is NOT available. Training will use CPU.")

if __name__ == "__main__":
    main()
