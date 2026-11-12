#!/usr/bin/env python3
"""P4 pipeline: skeleton -> render -> verify. Deterministic end-to-end."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render
import skeleton
import verify

if __name__ == '__main__':
    skeleton.main()
    render.main()
    verify.main()
