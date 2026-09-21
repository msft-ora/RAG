from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.column import Column


def add_merchant_sliding_counts(
    df: DataFrame,
    specs: list,
    merchant_col="DRVD_MRCH_ID",
    ts_col: str = "TRANS_DT",
) -> DataFrame:
    """
    Skew-safe replacement for sliding rangeBetween windows partitioned by merchant.
    Row-for-row identical to:
        Window.partitionBy(<merchant_col>).orderBy(col(<ts_col>).cast('timestamp')
              .cast('long')).rangeBetween(-window_seconds, -1)
        when(<merchant_col not null>, sum(<flag_col>).over(w))

    merchant_col: a column name (str) or a LIST of column names forming the
      partition key, e.g. ["DRVD_MRCH_ID", "CHANNEL_CD"].
      Rows where ANY key column is null get null in every out_col.

    Each spec: {"out_col": ..., "flag_col": ..., "window_seconds": ...}
      - flag_col may be a column NAME (str) or a Column EXPRESSION, e.g.
          F.col("A") * F.col("B")
          F.when(F.col("STATUS") == "FAIL", 1).otherwise(0)
        Expressions are materialized once per raw row before aggregation.
        Avoid non-deterministic expressions (rand(), current_timestamp(), ...).

    Spark sum() semantics are preserved EXACTLY:
      - empty frame (no rows in [t-w, t-1])          -> null (not 0)
      - frame rows exist but all flags are null       -> null (not 0)
      (tracked via a per-flag non-null COUNT running alongside the SUM)

    All specs share one aggregation, one cum pass, one fill-forward pass, one join.
    Specs using the same column-name flag share its cumulative columns.
    """
    if not specs:
        return df

    # ---- normalize the partition key to a list ----
    mcols = [merchant_col] if isinstance(merchant_col, str) else list(merchant_col)
    if not mcols or not all(isinstance(c, str) and c for c in mcols):
        raise ValueError(f"merchant_col must be a column name or a non-empty "
                         f"list of column names, got: {merchant_col!r}")
    for c in mcols:
        if c not in df.columns:
            raise ValueError(f"merchant_col '{c}' not in df columns")

    # ---- validate specs ----
    seen = set()
    for s in specs:
        for key in ("out_col", "flag_col", "window_seconds"):
            if key not in s:
                raise ValueError(f"spec missing required key '{key}': {s}")
        fc = s["flag_col"]
        if isinstance(fc, str):
            if fc not in df.columns:
                raise ValueError(f"flag_col '{fc}' not in df columns")
        elif not isinstance(fc, Column):
            raise TypeError(f"flag_col must be a str column name or a Column "
                            f"expression, got {type(fc).__name__}: {s}")
        if not isinstance(s["window_seconds"], int) or s["window_seconds"] <= 0:
            raise ValueError(f"window_seconds must be a positive int: {s}")
        if s["out_col"] in seen:
            raise ValueError(f"duplicate out_col '{s['out_col']}'")
        seen.add(s["out_col"])

    spec_id_of = {s["out_col"]: f"__s{i}" for i, s in enumerate(specs)}
    spec_by_id = {spec_id_of[s["out_col"]]: s for s in specs}

    # ---- normalize flags: every spec maps to an internal column name ----
    base = df.withColumn("__ts", F.col(ts_col).cast("timestamp").cast("long"))
    flag_name_of = {}                                   # spec id -> aggregatable column name
    for s in specs:
        sid = spec_id_of[s["out_col"]]
        fc = s["flag_col"]
        if isinstance(fc, str):
            flag_name_of[sid] = fc                      # use existing column directly
        else:
            internal = f"__flag_{sid}"
            base = base.withColumn(internal, fc.cast("long"))
            flag_name_of[sid] = internal

    flag_cols = sorted(set(flag_name_of.values()))
    sum_of = {f: f"__cum_{i}" for i, f in enumerate(flag_cols)}
    cnt_of = {f: f"__cumn_{i}" for i, f in enumerate(flag_cols)}

    # exclude rows where ANY key column is null
    not_null_cond = F.lit(True)
    for c in mcols:
        not_null_cond = not_null_cond & F.col(c).isNotNull()
    nn = base.where(not_null_cond)

    # Pass 1: raw rows -> one row per (key..., second).
    # Per flag: SUM (nulls skipped, coalesced) + COUNT of non-null values.
    per_sec = (nn.groupBy(*mcols, "__ts")
                 .agg(*[e for i, f in enumerate(flag_cols) for e in (
                        F.coalesce(F.sum(F.col(f).cast("long")), F.lit(0)).alias(f"__sec_{i}"),
                        F.count(F.col(f)).alias(f"__secn_{i}"))]))

    # Pass 2: cumulative sums per key over the tiny second series (sum + count)
    w_cum = (Window.partitionBy(*mcols).orderBy("__ts")
                   .rowsBetween(Window.unboundedPreceding, Window.currentRow))
    cum = per_sec.select(
        *mcols,
        F.col("__ts").alias("__x"),
        *[e for i, f in enumerate(flag_cols) for e in (
            F.sum(f"__sec_{i}").over(w_cum).alias(sum_of[f]),
            F.sum(f"__secn_{i}").over(w_cum).cast("long").alias(cnt_of[f]))],
    ).withColumn("__orig_ts", F.lit(None).cast("long")) \
     .withColumn("__spec", F.lit(None).cast("string")) \
     .withColumn("__which", F.lit(None).cast("string")) \
     .withColumn("__kind", F.lit(0))                       # 0 = anchor (cum point)

    # Pass 3: asof lookups at both frame edges for every spec
    # rangeBetween(-w, -1) inclusive => [t-w, t-1] = cum(t-1) - cum(t-w-1)
    pts = nn.select(*mcols, "__ts").distinct()

    req_frames = []
    for s in specs:
        w = s["window_seconds"]
        sid = spec_id_of[s["out_col"]]
        for edge, offset in (("hi", 1), ("lo", w + 1)):
            req_frames.append(
                pts.select(*mcols,
                           (F.col("__ts") - offset).alias("__x"),
                           F.col("__ts").alias("__orig_ts"))
                   .withColumn("__spec", F.lit(sid))
                   .withColumn("__which", F.lit(edge))
            )
    requests = req_frames[0]
    for rf in req_frames[1:]:
        requests = requests.unionByName(rf)
    requests = requests.select(
        *mcols, "__x",
        *[e for f in flag_cols for e in (
            F.lit(None).cast("long").alias(sum_of[f]),
            F.lit(None).cast("long").alias(cnt_of[f]))],
        "__orig_ts", "__spec", "__which",
    ).withColumn("__kind", F.lit(1))                        # 1 = lookup request

    # Union anchors + requests; anchor sorts before request at same __x (inclusive asof)
    w_ff = (Window.partitionBy(*mcols)
                  .orderBy("__x", "__kind")
                  .rowsBetween(Window.unboundedPreceding, Window.currentRow))
    merged = cum.unionByName(requests)
    for f in flag_cols:  # same WindowSpec -> Spark runs them in ONE WindowExec
        merged = merged.withColumn(sum_of[f], F.last(sum_of[f], ignorenulls=True).over(w_ff))
        merged = merged.withColumn(cnt_of[f], F.last(cnt_of[f], ignorenulls=True).over(w_ff))
    filled = merged.where(F.col("__kind") == 1)

    # Each request row only needs the sum/count columns of its own spec's flag
    sum_for_spec = F.coalesce(*[
        F.when(F.col("__spec") == sid, F.col(sum_of[flag_name_of[sid]]))
        for sid in spec_by_id])
    cnt_for_spec = F.coalesce(*[
        F.when(F.col("__spec") == sid, F.col(cnt_of[flag_name_of[sid]]))
        for sid in spec_by_id])
    filled = filled.select(*mcols, "__orig_ts", "__spec", "__which",
                           F.coalesce(sum_for_spec, F.lit(0)).alias("__vs"),
                           F.coalesce(cnt_for_spec, F.lit(0)).alias("__vc"))

    # Per (key..., ts, spec): frame = hi - lo; null when frame has no non-null flag
    # (covers BOTH Spark cases: empty frame and all-null frame -> sum() = null)
    per_spec = (filled.groupBy(*mcols, "__orig_ts", "__spec")
                      .agg(F.max(F.when(F.col("__which") == "hi", F.col("__vs"))).alias("hs"),
                           F.max(F.when(F.col("__which") == "lo", F.col("__vs"))).alias("ls"),
                           F.max(F.when(F.col("__which") == "hi", F.col("__vc"))).alias("hc"),
                           F.max(F.when(F.col("__which") == "lo", F.col("__vc"))).alias("lc")))

    out_exprs = [
        F.max(F.when(F.col("__spec") == sid,
                     F.when(F.col("hc") - F.col("lc") == 0, F.lit(None).cast("long"))
                       .otherwise(F.col("hs") - F.col("ls")))).alias(s["out_col"])
        for sid, s in spec_by_id.items()
    ]
    lookup = (per_spec.groupBy(*mcols, "__orig_ts")
                      .agg(*out_exprs)
                      .withColumnRenamed("__orig_ts", "__ts"))

    # Spark quirk: rows with NULL ts form a peer group inside the partition whose
    # range frame = the whole null-ts group (INCLUDING the current row), so the
    # original window returns sum(flag) over all null-ts rows of that key
    # (null if every flag in the group is null). Replicate exactly.
    null_out = (nn.where(F.col("__ts").isNull())
                  .groupBy(*mcols)
                  .agg(*[F.sum(F.col(f).cast("long")).alias(f"__ns_{i}")
                         for i, f in enumerate(flag_cols)])
                  .select(*mcols,
                          *[F.col(f"__ns_{flag_cols.index(flag_name_of[sid])}")
                              .alias(f"__n_{sid}") for sid in spec_by_id]))

    result = (base.join(lookup, mcols + ["__ts"], "left")
                  .join(null_out, mcols, "left"))
    for sid, s in spec_by_id.items():
        result = result.withColumn(
            s["out_col"],
            F.when(F.col("__ts").isNull(), F.col(f"__n_{sid}").cast("long"))
             .otherwise(F.col(s["out_col"])))

    # Drop internal expression columns so they don't leak into the result
    internal_cols = [f"__flag_{sid}" for sid, s in spec_by_id.items()
                     if not isinstance(s["flag_col"], str)]
    return result.drop("__ts", *internal_cols,
                       *[f"__n_{sid}" for sid in spec_by_id])
