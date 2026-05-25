import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.page_filters import render_academic_filters
from app.database.postgres import get_pg_engine
from app.views.academic import render

engine  = get_pg_engine()
filters = render_academic_filters(engine)
render(filters, engine)
