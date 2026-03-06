#!/usr/bin/env python3
import sys
import os

def find_waf_dir(base_dir):
	candidates = [
		'.waf3-1.7.11-edc6ccb516c5e3f9b892efc9f53a610f',
		'.waf-1.7.11-edc6ccb516c5e3f9b892efc9f53a610f',
	]
	for candidate in candidates:
		path = os.path.join(base_dir, candidate)
		if os.path.isfile(os.path.join(path, 'waflib', 'Scripting.py')):
			return path
	raise RuntimeError('Could not find a usable vendored waflib directory')


waf_dir = find_waf_dir(os.getcwd())
sys.path.append(waf_dir)

from waflib import Scripting, Context

# Define constants expected by waf (just in case)
Context.WAFVERSION="1.7.11"
Context.HEXVERSION=0x1070b00

# Scripting.waf_entry_point(current_directory, version, wafdir)
Scripting.waf_entry_point(os.getcwd(), "1.7.11", waf_dir)
