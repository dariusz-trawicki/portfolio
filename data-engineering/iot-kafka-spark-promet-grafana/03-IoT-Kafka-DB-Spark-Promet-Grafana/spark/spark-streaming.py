from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window, avg, max as spark_max, to_timestamp
from pyspark.sql.types import StructType, DoubleType, LongType
import mysql.connector

spark = SparkSession.builder \
    .appName("KafkaTemperatureStream") \
    .master("local[*]") \
    .getOrCreate()
spark.sparkContext.setLogLevel("WARN")

schema = StructType() \
    .add("temperature", DoubleType()) \
    .add("timestamp", LongType())

df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "temperature") \
    .load()

parsed = df.selectExpr("CAST(value AS STRING) as json") \
    .select(from_json("json", schema).alias("data")) \
    .select("data.*") \
    .withColumn("timestamp", to_timestamp(col("timestamp")))

aggregated = parsed \
    .withWatermark("timestamp", "1 minute") \
    .groupBy(window(col("timestamp"), "1 minute")) \
    .agg(
        avg("temperature").alias("avg_temp"),
        spark_max("temperature").alias("current_temp")
    )

def foreach_batch_function(batch_df, epoch_id):
    rows = batch_df.collect()
    if not rows:
        return

    try:
        db = mysql.connector.connect(
            host="mysql", user="root", password="root", database="sensors"
        )
        cursor = db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS avg_temperatures (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp BIGINT,
                avg_temp FLOAT,
                current_temp FLOAT
            )
        """)
        for row in rows:
            ts_start = int(row['window'].start.timestamp())
            avg_t = float(row['avg_temp'])
            curr_t = float(row['current_temp'])
            cursor.execute(
                "INSERT INTO avg_temperatures (timestamp, avg_temp, current_temp) VALUES (%s, %s, %s)",
                (ts_start, avg_t, curr_t)
            )
            print(f"Okno {row['window'].start} – średnia={avg_t}, aktualna={curr_t}")
        db.commit()
    except Exception as e:
        print("MySQL error:", e)
    finally:
        if 'db' in locals():
            db.close()

    last = rows[-1]
    avg_t = float(last['avg_temp'])
    curr_t = float(last['current_temp'])
    with open("/tmp/metrics.txt", "w") as f:
        f.write(f"average_temperature {avg_t}\n")
        f.write(f"current_temperature {curr_t}\n")

query = aggregated.writeStream \
    .foreachBatch(foreach_batch_function) \
    .outputMode("update") \
    .start()

query.awaitTermination()
