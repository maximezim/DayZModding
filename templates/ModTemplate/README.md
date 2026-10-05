# ModTemplate

Empty mod skeleton used by `tools/build/New-Mod.ps1` and by the toolchain smoke test.
It contains only a `CfgPatches` entry — no scripts, items or gameplay.

```
ModTemplate/
  mod.cpp                 launcher metadata (copied to build/@Mod/)
  addons/
    scripts/              one folder = one PBO (prefix ModTemplate\scripts)
      config.cpp          CfgPatches (+ CfgMods once scripts exist)
```

Add more PBO folders under `addons/` (e.g. `data/` for models/textures — binarized
automatically when it contains .p3d/.rtm/.wrp). Put a `$PBOPREFIX$` file in a PBO
folder only if it needs a non-default prefix.
