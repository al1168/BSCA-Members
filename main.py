"""Deprecated launcher kept so `python main.py` still works; the real entry
point (settings, theme, crash log, icon) is member_manager.main()."""
from member_manager import main

if __name__ == "__main__":
    main()
