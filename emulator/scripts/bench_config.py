#!/usr/bin/env python3
"""Write a GT6 custom config into a test data root.

  bench_config.py ROOT SERIAL PROFILE [key=value ...]
PROFILE: 122 (WCB+RCB, no CPU blit) | 105 (CPU blit, no WCB/RCB)   per RPCS3 wiki
extra keys: spu=Safe|Mega|Giga  vblank=60|120  scale=100|150|200  mtrsx=0|1  limit=Auto|Off
"""
import sys
from pathlib import Path

root, serial, profile, *extra = sys.argv[1:]
o = dict(kv.split("=", 1) for kv in extra)
wcb = profile == "122"
cfg = f"""Core:
  PPU Decoder: Recompiler (LLVM)
  SPU Decoder: Recompiler (LLVM)
  SPU Block Size: {o.get('spu', 'Safe')}
  RSX FIFO Fetch Accuracy: Atomic
  Accurate RSX reservation access: true
  LLVM Precompilation: true
Video:
  Renderer: Vulkan
  Resolution: 1280x720
  Frame limit: {o.get('limit', 'Auto')}
  Write Color Buffers: {str(wcb).lower()}
  Read Color Buffers: {str(wcb).lower()}
  Force CPU Blit: {str(not wcb).lower()}
  Disable ZCull Occlusion Queries: true
  Multithreaded RSX: {'true' if o.get('mtrsx') == '1' else 'false'}
  Shader Mode: Async Recompiler with Shader Interpreter
  Resolution Scale: {o.get('scale', '100')}
  Vblank Rate: {o.get('vblank', '60')}
  Performance Overlay:
    Enabled: true
    Detail level: High
Audio:
  Master Volume: 10
Miscellaneous:
  Start games in fullscreen mode: false
  Exit RPCS3 when process finishes: true
  Window Title Format: "FPS: %F | %R | %V | %T [%t]"
"""
p = Path(root) / "xdg-config" / "rpcs3" / "custom_configs" / f"config_{serial}.yml"
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(cfg)
print(p)
