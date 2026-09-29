from pyspark.sql.functions import (col, concat_ws, count, lit, to_date, date_format,
                                   xxhash64, sha2, sum, coalesce)
def compute_partition_checksum(params):
    """xxhash64 + sha2(256) checksum — returns a DataFrame.
    Order-independent fingerprint: per-row xxhash64 over NULL-coalesced string values,
    aggregated as count + sum(h1) + sum(hash(h1)) per period, then sha2-256 of the triple.
    Fully distributed tree aggregation — no collect_list/sort_array bottleneck.
    params = [schema_name, table_name, partition_date_col, start_date,
              end_date, table_filter, checksum_level]
    - Required:     schema_name, table_name
    - Optional:     partition_date_col (None), start_date (None), end_date (None),
                    table_filter (None), checksum_level ("m")
    - Table-level:  only schema_name + table_name → single checksum for the whole table.
    - Partition-level: partition_date_col provided → per-period checksum.
      - checksum_level: 'm' for month (yyyy-MM) or 'd' for day (yyyy-MM-dd)
    Returns DataFrame with columns: period, checksum_<schema>_<table>[_<level>][_<filter>], row_count.
    """
    p = list(params) + [None, None, None, None, None, None, "m"][len(params):]
    schema_name, table_name, partition_date_col, start_date, end_date, table_filter, checksum_level = p
    filter_suffix = "".join(c if c.isalnum() else "_" for c in table_filter).strip("_") if table_filter else ""
    base_df = spark.table(f"{schema_name}.{table_name}")
    if table_filter:
        base_df = base_df.filter(table_filter)
    def _hash(df, cols):
        return (df.withColumn("_h1", xxhash64(*[coalesce(col(c).cast("string"), lit("\x00")) for c in cols]))
                  .withColumn("_h2", xxhash64(col("_h1"))))
    def _aggs():
        return [count(lit(1)).alias("row_count"),
                sum(col("_h1").cast("decimal(38,0)")).alias("_s1"),
                sum(col("_h2").cast("decimal(38,0)")).alias("_s2")]
    def _finish(agg_df, checksum_col):
        return agg_df.withColumn(checksum_col, sha2(concat_ws("|", col("row_count"),
                coalesce(col("_s1"), lit(0)), coalesce(col("_s2"), lit(0))), 256))
    if partition_date_col is None:
        checksum_col = f"checksum_{schema_name}_{table_name}" + (f"_{filter_suffix}" if filter_suffix else "")
        return (_finish(_hash(base_df, sorted(base_df.columns)).agg(*_aggs()), checksum_col)
                  .withColumn("period", lit("ALL"))
                  .select("period", checksum_col, "row_count"))
    dt_col = to_date(col(partition_date_col))
    if checksum_level == "m":
        period_col = date_format(dt_col, "yyyy-MM")
    elif checksum_level == "d":
        period_col = date_format(dt_col, "yyyy-MM-dd")
    else:
        raise ValueError(f"checksum_level must be 'm' or 'd', got '{checksum_level}'")
    df = base_df.withColumn("period", period_col)
    if start_date:
        df = df.filter(dt_col >= to_date(lit(start_date)))
    if end_date:
        df = df.filter(dt_col <= to_date(lit(end_date)))
    checksum_col = f"checksum_{schema_name}_{table_name}_{checksum_level}" + (f"_{filter_suffix}" if filter_suffix else "")
    return (_finish(_hash(df, sorted(c for c in df.columns if c != "period")).groupBy("period").agg(*_aggs()), checksum_col)
              .select("period", checksum_col, "row_count")
              .orderBy("period"))