
import os
from databricks import sql

with sql.connect(
    server_hostname="dbc-384fb431-bc55.cloud.databricks.com",
    http_path="/sql/1.0/warehouses/1efe042d5906ff40",
    access_token=os.environ["DATABRICKS_TOKEN"]
) as connection:

    with connection.cursor() as cursor:

        cursor.execute("""
            SELECT
                current_catalog(),
                current_schema(),
                current_user()
        """)
        print("Connection:", cursor.fetchone())

        cursor.execute("""
            SELECT
                COUNT(*),
                MAX(recorded_at)
            FROM workspace.default.water_quality
        """)
        print("Python sees:", cursor.fetchone())
