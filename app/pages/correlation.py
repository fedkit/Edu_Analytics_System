import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.page_filters import render_correlation_filters
from app.database.clickhouse import get_ch_client
from app.database.postgres import get_pg_engine
from app.views.correlation import render

engine  = get_pg_engine()
ch      = get_ch_client()
filters = render_correlation_filters(engine)
render(filters, engine, ch)
