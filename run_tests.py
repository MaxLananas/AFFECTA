"""Dependency-free test runner (pytest not available in this env).
Discovers test_* functions across tests/ and runs them."""
import importlib, sys, traceback

MODULES = [
    "movement_engine.tests.test_scorer",
    "movement_engine.tests.test_engine",
    "movement_engine.tests.test_properties",
    "movement_engine.tests.test_optimality",
    "movement_engine.tests.test_adversarial",
    "movement_engine.tests.test_da_engine",
    "movement_engine.tests.test_matching",
    "movement_engine.tests.test_native",
    "movement_engine.tests.test_realism",
]

def main():
    passed = failed = 0
    fails = []
    for modname in MODULES:
        try:
            mod = importlib.import_module(modname)
        except Exception as e:
            print(f"  IMPORT FAIL {modname}: {e}")
            failed += 1
            fails.append(modname)
            continue
        for name in sorted(dir(mod)):
            if not name.startswith("test_"):
                continue
            fn = getattr(mod, name)
            if not callable(fn):
                continue
            try:
                fn()
                passed += 1
            except Exception as e:
                failed += 1
                fails.append(f"{modname}.{name}")
                print(f"  FAIL {modname}.{name}: {e}")
                if "-v" in sys.argv:
                    traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
