"""
WSGI for pythonanywhere.com hosting
"""

import sys
project_home = u'/home/RichardHills/rdhlang4/rdhlang4_web/'
if project_home not in sys.path:
    sys.path.append(project_home)
    
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rdhlang4_web.settings")

    # Add the language python code to the PYTHON_PATH
    sys.path.append('../rdhlang4')

    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
