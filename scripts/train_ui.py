from util.import_util import script_imports

script_imports()

import os
import sys

# Fix for ibus-daemon infinite loop issue with CustomTkinter
# This disables input method integration that causes the hang
if sys.platform.startswith('linux'):
     # Disable X11 input method integration
     os.environ['XMODIFIERS'] = ''

from modules.ui.TrainUI import TrainUI


def main():
    ui = TrainUI()
    ui.mainloop()


if __name__ == '__main__':
    main()
