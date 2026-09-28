from pyspark.sql.functions import (col, concat_ws, sort_array, collect_list, count,
                                   lit, to_date, date_format, xxhash64, sha2)
def compute_partition_checksum(schema_name, table_name, partition_date_col,
                               start_date, end_date, table_filter=None, checksum_level="m"):
    """xxhash64 + sha2(256) partition checksum — returns a DataFrame.
    Single-pass groupBy, no Python loop.
    Per-row: xxhash64(*all_columns) — NULL-safe natively.
    Final:   sha2-256 of sorted row-hash strings concatenated within each period.
      - table_filter:   SQL condition string (without WHERE), default None
      - checksum_level: 'm' for month (yyyy-MM) or 'd' for day (yyyy-MM-dd), default 'm'
    Returns DataFrame with columns: period, checksum_<schema>_<table>_<level>, row_count.
    """
    base_df = spark.table(f"{schema_name}.{table_name}")
    pcol = partition_date_col
    dt_col = to_date(col(pcol))
    if checksum_level == "m":
        period_col = date_format(dt_col, "yyyy-MM")
    elif checksum_level == "d":
        period_col = date_format(dt_col, "yyyy-MM-dd")
    else:
        raise ValueError(f"checksum_level must be 'm' or 'd', got '{checksum_level}'")
    df = base_df.withColumn("period", period_col).filter(
        dt_col >= to_date(lit(start_date))).filter(dt_col <= to_date(lit(end_date)))
    if table_filter:
        df = df.filter(table_filter)
    cols = sorted(c for c in df.columns if c != "period")
    checksum_col = f"checksum_{schema_name}_{table_name}_{checksum_level}"
    return (df.withColumn("_rh", xxhash64(*[col(c) for c in cols]).cast("string"))
              .groupBy("period")
              .agg(count(lit(1)).alias("row_count"),
                   sha2(concat_ws("", sort_array(collect_list("_rh"))), 256).alias(checksum_col))
              .select("period", checksum_col, "row_count")
              .orderBy("period"))