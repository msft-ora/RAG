from datetime import datetime, timedelta
from pyspark.sql.functions import (col, concat_ws, sort_array, collect_list, count,
                                   lit, to_date, date_format, xxhash64, sha2)


def compute_partition_checksum(spark, params):
    """xxhash64 + sha2(256) partition checksum.
    Per-row: xxhash64(*all_columns) — NULL-safe natively, no concat_ws needed.
    Final:   sha2-256 of sorted row-hash strings concatenated.
    params = [schema_name, table_name, partition_date_col, start_date,
              end_date, level, table_filter]
      - level:        'm' for month (yyyy-MM) or 'd' for day (yyyy-MM-dd)
      - table_filter: SQL condition string (without WHERE), or None
    Returns list of (partition_key, checksum_sha256, row_count).
    """
    schema_name, table_name, pcol, start_date, end_date, level, table_filter = params
    base_df = spark.table(f"{schema_name}.{table_name}")

    def _add_months(d, n):
        m = d.month - 1 + n
        return d.replace(year=d.year + m // 12, month=m % 12 + 1, day=1)

    keys, cur, end = [], datetime.strptime(start_date, "%Y-%m-%d"), datetime.strptime(end_date, "%Y-%m-%d")
    if level == "m":
        cur = cur.replace(day=1)
        while cur <= end:
            keys.append(cur.strftime("%Y-%m"))
            cur = _add_months(cur, 1)
    elif level == "d":
        while cur <= end:
            keys.append(cur.strftime("%Y-%m-%d"))
            cur += timedelta(days=1)
    else:
        raise ValueError(f"level must be 'm' or 'd', got '{level}'")

    results = []
    for k in keys:
        pfilt = (date_format(to_date(col(pcol)), "yyyy-MM") == lit(k)
                 if level == "m"
                 else to_date(col(pcol)) == to_date(lit(k)))
        df = base_df.filter(pfilt)
        if table_filter:
            df = df.filter(table_filter)
        cols = sorted(df.columns)
        r = (df.withColumn("_rh", xxhash64(*[col(c) for c in cols]).cast("string"))
               .agg(count(lit(1)).alias("row_count"),
                    sha2(concat_ws("", sort_array(collect_list("_rh"))), 256).alias("checksum"))
               .collect()[0])
        results.append((k, r["checksum"], r["row_count"]))
    return results