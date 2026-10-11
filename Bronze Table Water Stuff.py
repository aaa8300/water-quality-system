# Databricks notebook source

path = "s3://knighthacks-water-telemetry-2026/readings/live/"

df = (
    spark.read
    .option("recursiveFileLookup", "true")
    .json(path)
)

display(df.limit(10))


# COMMAND ----------

display(spark.table("workspace.default.water_quality_bronze").limit(10))

# COMMAND ----------


from pyspark.sql.types import (
    StructType, StructField,
    StringType, DoubleType,
    IntegerType, BooleanType
)
from pyspark.sql.functions import col, to_timestamp

source = "s3://knighthacks-water-telemetry-2026/readings/live/"

schema = StructType([
    StructField("recorded_at_utc", StringType()),
    StructField("temperature_c", DoubleType()),
    StructField("turbidity_adc", IntegerType()),
    StructField("ph_simulated", DoubleType()),
    StructField("ph_is_simulated", BooleanType())
])

stream_df = (
    spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.useNotifications", "false")
    .schema(schema)
    .load(source)
)

bronze_stream = stream_df.select(
    to_timestamp("recorded_at_utc").alias("recorded_at_utc"),
    col("temperature_c"),
    col("turbidity_adc"),
    col("ph_simulated"),
    col("ph_is_simulated")
)

print("Bronze stream initialized!")


# COMMAND ----------

spark.sql("""
CREATE VOLUME IF NOT EXISTS workspace.default.aquawave_checkpoints
""")

print("Checkpoint volume ready!")

# COMMAND ----------


query = (
    bronze_stream.writeStream
    .format("delta")
    .outputMode("append")
    .option(
        "checkpointLocation",
        "/Volumes/workspace/default/aquawave_checkpoints/bronze"
    )
    .trigger(availableNow=True)
    .toTable("workspace.default.water_quality_bronze")
)

query.awaitTermination()

print("AquaWave Bronze ingestion completed!")


# COMMAND ----------

spark.sql("""
SELECT
    COUNT(*) AS total_readings,
    MIN(recorded_at_utc) AS first_reading,
    MAX(recorded_at_utc) AS latest_reading
FROM workspace.default.water_quality_bronze
""").show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC

# COMMAND ----------

query = (
    bronze_stream.writeStream
    .format("delta")
    .outputMode("append")
    .option(
        "checkpointLocation",
        "/Volumes/workspace/default/aquawave_checkpoints/bronze"
    )
    .trigger(availableNow=True)
    .toTable("workspace.default.water_quality_bronze")
)

query.awaitTermination()