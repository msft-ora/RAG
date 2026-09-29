from pyspark.sql.functions import (col, concat_ws, sort_array, collect_list, count,
                                   lit, to_date, date_format, xxhash64, sha2)
def compute_partition_checksum(params):
    """xxhash64 + sha2(256) checksum — returns a DataFrame.
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
    p = (list(params) + [None, None, None, None, None, "m"])[:7]
    schema_name, table_name, partition_date_col, start_date, end_date, table_filter, checksum_level = p
    filter_suffix = "".join(c if c.isalnum() else "_" for c in table_filter).strip("_") if table_filter else ""
    base_df = spark.table(f"{schema_name}.{table_name}")
    if table_filter:
        base_df = base_df.filter(table_filter)
    if partition_date_col is None:
        cols = sorted(base_df.columns)
        checksum_col = f"checksum_{schema_name}_{table_name}"
        if filter_suffix:
            checksum_col += f"_{filter_suffix}"
        return (base_df.withColumn("_rh", xxhash64(*[col(c) for c in cols]).cast("string"))
                  .agg(count(lit(1)).alias("row_count"),
                       sha2(concat_ws("", sort_array(collect_list("_rh"))), 256).alias(checksum_col))
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
    cols = sorted(c for c in df.columns if c != "period")
    checksum_col = f"checksum_{schema_name}_{table_name}_{checksum_level}"
    if filter_suffix:
        checksum_col += f"_{filter_suffix}"
    return (df.withColumn("_rh", xxhash64(*[col(c) for c in cols]).cast("string"))
              .groupBy("period")
              .agg(count(lit(1)).alias("row_count"),
                   sha2(concat_ws("", sort_array(collect_list("_rh"))), 256).alias(checksum_col))
              .select("period", checksum_col, "row_count")
              .orderBy("period"))