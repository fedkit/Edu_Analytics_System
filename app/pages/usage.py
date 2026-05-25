import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.page_filters import render_usage_filters
from app.database.clickhouse import get_ch_client
from app.views.usage import render

ch      = get_ch_client()
filters = render_usage_filters()
render(filters, ch)
