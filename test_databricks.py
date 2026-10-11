
from databricks import sql
import os

# ==========================================
# KNIGHT HACKS IX
# DATABRICKS CONNECTION + INSERT TEST
# ==========================================

DB_HOST = "dbc-384fb431-bc55.cloud.databricks.com"
DB_HTTP_PATH = "/sql/1.0/warehouses/1efe042d5906ff40"

TABLE_NAME = "workspace.default.water_quality"

print("=" * 45)
print("KNIGHT HACKS IX - DATABRICKS TEST")
print("=" * 45)

try:
    # STEP 1: CONNECT TO DATABRICKS
    print("[1] Connecting to Databricks...", flush=True)

  with sql.connect(
    server_hostname=DB_HOST,
    http_path=DB_HTTP_PATH,
    access_token=os.environ["DATABRICKS_TOKEN"]
) as connection:

        print("[2] Connection successful!", flush=True)

        with connection.cursor() as cursor:

            # STEP 2: TEST SQL CONNECTION
            cursor.execute("SELECT current_timestamp()")
            result = cursor.fetchone()

            print("[3] SQL query successful!", flush=True)
            print("Databricks time:", result[0])

            # STEP 3: INSERT TEST SENSOR DATA
            print("[4] Inserting test sensor reading...", flush=True)

            cursor.execute(f"""
                INSERT INTO {TABLE_NAME}
                (
                    recorded_at,
                    temperature_c,
                    turbidity_adc,
                    ph_simulated,
                    ph_is_simulated
                )
                VALUES (
                    current_timestamp(),
                    23.06,
                    578,
                    13.97,
                    TRUE
                )
            """)

            print("[5] TEST INSERT SUCCESSFUL!", flush=True)

            # STEP 4: VERIFY TABLE CONTENTS
            cursor.execute(f"""
                SELECT COUNT(*)
                FROM {TABLE_NAME}
            """)

            count = cursor.fetchone()[0]

            print(f"[6] Total rows in Databricks: {count}")

            # STEP 5: DISPLAY LATEST READINGS
            cursor.execute(f"""
                SELECT *
                FROM {TABLE_NAME}
                ORDER BY recorded_at DESC
                LIMIT 5
            """)

            print("\nLATEST SENSOR READINGS:")

            for row in cursor.fetchall():
                print(row)

except Exception as error:
    print("\n[ERROR] Databricks operation failed!")
    print("Error type:", type(error).__name__)
    print("Error message:", error)

print("\nTest finished.")
