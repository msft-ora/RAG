from pyspark.sql import DataFrame, Window
from pyspark.sql.column import Column
from pyspark.sql.functions import coalesce, col, count, last, lit, max, sum, when
from pyspark.sql.types import LongType
def _norm_keys(key, df_columns):
    cols = (key,) if isinstance(key, str) else tuple(key)
    if not cols or not all(isinstance(c, str) and c for c in cols):
        raise ValueError(f"partition_col must be a column name or a non-empty "
                         f"list of column names, got: {key!r}")
    for c in cols:
        if c not in df_columns:
            raise ValueError(f"partition_col '{c}' not in df columns")
    return cols
def _spec_lookups(base, mcols, sid_specs, flag_name_of):
    """Passes 1-3 (+ null-ts peer-group handling) for ONE partition-key group.
    sid_specs: list of (spec_id, spec_dict). Returns (lookup, null_out)."""
    sids = [sid for sid, _ in sid_specs]
    spec_of = dict(sid_specs)
    flags = sorted({flag_name_of[sid] for sid in sids})
    cnt_of = {f: f"__cumn_{i}" for i, f in enumerate(flags)}
    # SUM measures only for flags used by >=1 sum spec (Spark's sum() needs a
    # numeric column - count-only flags may be strings etc. and must NOT be cast)
    sum_flags = sorted({flag_name_of[sid] for sid in sids
                        if spec_of[sid].get("agg", "sum") == "sum"})
    sum_of = {f: f"__cum_{i}" for i, f in enumerate(sum_flags)}
    sidx_of = {f: i for i, f in enumerate(sum_flags)}
    # exclude rows where ANY key column is null
    not_null_cond = lit(True)
    for c in mcols:
        not_null_cond = not_null_cond & col(c).isNotNull()
    nn = base.where(not_null_cond)
    # Pass 1: raw rows -> one row per (key..., second).
    # Per flag: COUNT of non-null values (no cast - works for any column type).
    # Per sum-flag: SUM in Spark's natural sum type (int->bigint, decimal->
    # decimal, double->double), coalesced so every anchor is definite.
    pass1_aggs = [count(col(f)).alias(f"__secn_{i}")
                  for i, f in enumerate(flags)]
    pass1_aggs += [coalesce(sum(col(f)), lit(0)).alias(f"__secs_{i}")
                   for i, f in enumerate(sum_flags)]
    per_sec = nn.groupBy(*mcols, "__ts").agg(*pass1_aggs)
    # Pass 2: cumulative sums per key over the tiny second series (count + sum)
    w_cum = (Window.partitionBy(*mcols).orderBy("__ts")
                   .rowsBetween(Window.unboundedPreceding, Window.currentRow))
    cum_cols = [sum(f"__secn_{i}").over(w_cum).alias(cnt_of[f])
                for i, f in enumerate(flags)]
    cum_cols += [sum(f"__secs_{i}").over(w_cum).alias(sum_of[f])
                 for i, f in enumerate(sum_flags)]
    cum = per_sec.select(*mcols, col("__ts").alias("__x"), *cum_cols) \
        .withColumn("__orig_ts", lit(None).cast("long")) \
        .withColumn("__spec", lit(None).cast("string")) \
        .withColumn("__which", lit(None).cast("string")) \
        .withColumn("__kind", lit(0))                    # 0 = anchor (cum point)
    cum_types = {f.name: f.dataType for f in cum.schema.fields}  # analysis only
    # Pass 3: asof lookups at both frame edges for every spec
    # rangeBetween(-w, -1) inclusive => [t-w, t-1] = cum(t-1) - cum(t-w-1)
    pts = nn.select(*mcols, "__ts").distinct()
    req_frames = []
    for sid in sids:
        w = spec_of[sid]["window_seconds"]
        for edge, offset in (("hi", 1), ("lo", w + 1)):
            req_frames.append(
                pts.select(*mcols,
                           (col("__ts") - offset).alias("__x"),
                           col("__ts").alias("__orig_ts"))
                   .withColumn("__spec", lit(sid))
                   .withColumn("__which", lit(edge))
            )
    requests = req_frames[0]
    for rf in req_frames[1:]:
        requests = requests.unionByName(rf)
    requests = requests.select(
        *mcols, "__x",
        *[lit(None).cast(LongType()).alias(cnt_of[f]) for f in flags],
        *[lit(None).cast(cum_types[sum_of[f]]).alias(sum_of[f])
          for f in sum_flags],
        "__orig_ts", "__spec", "__which",
    ).withColumn("__kind", lit(1))                       # 1 = lookup request
    # Union anchors + requests; anchor sorts before request at same __x (inclusive asof)
    w_ff = (Window.partitionBy(*mcols)
                  .orderBy("__x", "__kind")
                  .rowsBetween(Window.unboundedPreceding, Window.currentRow))
    merged = cum.unionByName(requests)
    for f in flags:  # same WindowSpec -> Spark runs them in ONE WindowExec
        merged = merged.withColumn(cnt_of[f], last(cnt_of[f], ignorenulls=True).over(w_ff))
    for f in sum_flags:
        merged = merged.withColumn(sum_of[f], last(sum_of[f], ignorenulls=True).over(w_ff))
    filled = merged.where(col("__kind") == 1)
    # Each request row only needs the sum/count columns of its own spec's flag
    cnt_for_spec = coalesce(*[
        when(col("__spec") == sid, col(cnt_of[flag_name_of[sid]]))
        for sid in sids])
    sel_cols = [*mcols, "__orig_ts", "__spec", "__which",
                coalesce(cnt_for_spec, lit(0)).alias("__vc")]
    if sum_flags:
        sum_for_spec = coalesce(*[
            when(col("__spec") == sid, col(sum_of[flag_name_of[sid]]))
            for sid in sids
            if spec_of[sid].get("agg", "sum") == "sum"])
        sel_cols.append(coalesce(sum_for_spec, lit(0)).alias("__vs"))
    else:
        sel_cols.append(lit(None).alias("__vs"))
    filled = filled.select(*sel_cols)
    # Per (key..., ts, spec): frame = hi - lo.
    #   agg "sum":   null when frame has no non-null flag value
    #                (Spark: empty frame / all-null frame -> sum() = null)
    #   agg "count": non-null values in frame (Spark count(col): empty -> 0)
    per_spec = (filled.groupBy(*mcols, "__orig_ts", "__spec")
                      .agg(max(when(col("__which") == "hi", col("__vs"))).alias("hs"),
                           max(when(col("__which") == "lo", col("__vs"))).alias("ls"),
                           max(when(col("__which") == "hi", col("__vc"))).alias("hc"),
                           max(when(col("__which") == "lo", col("__vc"))).alias("lc")))
    out_exprs = []
    for sid in sids:
        s = spec_of[sid]
        if s.get("agg", "sum") == "count":
            out_exprs.append(
                max(when(col("__spec") == sid, col("hc") - col("lc")))
                      .alias(s["feature_name"]))
        else:
            out_exprs.append(
                max(when(col("__spec") == sid,
                             when(col("hc") - col("lc") == 0, lit(None))
                               .otherwise(col("hs") - col("ls"))))
                      .alias(s["feature_name"]))
    lookup = (per_spec.groupBy(*mcols, "__orig_ts")
                      .agg(*out_exprs)
                      .withColumnRenamed("__orig_ts", "__ts"))
    # Spark quirk: rows with NULL ts form a peer group inside the partition whose
    # range frame = the whole null-ts group (INCLUDING the current row), so the
    # original window returns agg(flag) over all null-ts rows of that key
    # (sum -> null if every flag in the group is null; count -> non-null count).
    null_aggs = [count(col(f)).alias(f"__nc_{i}")
                 for i, f in enumerate(flags)]
    null_aggs += [sum(col(f)).alias(f"__ns_{i}")
                  for i, f in enumerate(sum_flags)]
    null_agg = nn.where(col("__ts").isNull()).groupBy(*mcols).agg(*null_aggs)
    null_sel = []
    for sid in sids:
        f = flag_name_of[sid]
        if spec_of[sid].get("agg", "sum") == "count":
            null_sel.append(col(f"__nc_{flags.index(f)}").alias(f"__n_{sid}"))
        else:
            null_sel.append(col(f"__ns_{sidx_of[f]}").alias(f"__n_{sid}"))
    null_out = null_agg.select(*mcols, *null_sel)
    return lookup, null_out
def add_merchant_sliding_counts(
    df: DataFrame,
    specs: list,
    ts_col: str = "TRANS_DT",
) -> DataFrame:
    """
    Skew-safe replacement for sliding rangeBetween windows partitioned by merchant.
    Each output is row-for-row identical to ONE of these four original forms:
        sum(<col_exp>).over(w)      -> agg="sum" (default), col_exp = column name
        count(<col_exp>).over(w)    -> agg="count",          col_exp = column name
        sum(<expression>).over(w)    -> agg="sum",            col_exp = Column expr
        count(<expression>).over(w)  -> agg="count",          col_exp = Column expr
    where w = Window.partitionBy(<spec partition_col>)
                    .orderBy(col(<ts_col>).cast('timestamp').cast('long'))
                    .rangeBetween(-window_seconds, -1)
    and the whole thing is wrapped in when(<key not null>, ...).
    Each spec: {"feature_name": ..., "partition_col": ..., "col_exp": ...,
                "window_seconds": ..., "agg": "sum" | "count" (OPTIONAL, default "sum")}
      - agg "sum":   sum of col_exp over the frame (nulls skipped; numeric
                     flags/expressions only, exactly like Spark's sum).
                     null when the frame is empty or all flags are null.
                     Result keeps Spark's natural sum type (int->bigint,
                     decimal->decimal, double->double). NOTE: for float/double
                     flags, summation ORDER differs from the original window
                     (per-second groups vs row-by-row), so results can differ
                     in the last ulp - Spark's own window result is likewise
                     order-dependent among same-second peer rows. Integer and
                     decimal flags are exact.
      - agg "count": number of NON-NULL col_exp values in the frame, counted
                     on the ORIGINAL column (any type - string ids are fine,
                     nothing is cast). 0 when the frame is empty.
      - partition_col: THIS output's partition key - a column name or a list,
        e.g. "DRVD_MRCH_ID" or ["DRVD_MRCH_ID", "CHANNEL_CD"]. Specs sharing
        the same key share one pipeline.
      - col_exp: a column NAME (str) or a Column EXPRESSION, e.g.
          col("A") * col("B")
          when(col("STATUS") == "FAIL", 1).otherwise(0)
        Expressions are materialized once per raw row before aggregation.
        Avoid non-deterministic expressions (rand(), current_timestamp(), ...).
      - Rows where ANY of the spec's key columns is null get null in that
        spec's feature_name only.
    Spark semantics are preserved EXACTLY, including the null-ts quirk:
    null-ts rows form a peer group whose frame is the whole group (sum ->
    group sum, count -> group non-null count).
    """
    if not specs:
        return df
    # ---- validate + normalize specs (never mutates the caller's dicts) ----
    seen = set()
    sid_specs = []                                       # (spec_id, spec, key_tuple)
    for i, s in enumerate(specs):
        for key in ("feature_name", "partition_col", "col_exp", "window_seconds"):
            if key not in s:
                raise ValueError(f"spec missing required key '{key}': {s}")
        agg = s.get("agg", "sum")
        if agg not in ("sum", "count"):
            raise ValueError(f"agg must be 'sum' or 'count', got {agg!r}: {s}")
        fc = s["col_exp"]
        if isinstance(fc, str):
            if fc not in df.columns:
                raise ValueError(f"col_exp '{fc}' not in df columns")
        elif not isinstance(fc, Column):
            raise TypeError(f"col_exp must be a str column name or a Column "
                            f"expression, got {type(fc).__name__}: {s}")
        if not isinstance(s["window_seconds"], int) or s["window_seconds"] <= 0:
            raise ValueError(f"window_seconds must be a positive int: {s}")
        if s["feature_name"] in seen:
            raise ValueError(f"duplicate feature_name '{s['feature_name']}'")
        seen.add(s["feature_name"])
        key_tuple = _norm_keys(s["partition_col"], df.columns)
        sid_specs.append((f"__s{i}", s, key_tuple))
    # ---- materialize expression flags once per raw row (natural type, no cast) ----
    base = df.withColumn("__ts", col(ts_col).cast("timestamp").cast("long"))
    flag_name_of = {}                                    # spec id -> aggregatable column name
    internal_cols = []
    for sid, s, _ in sid_specs:
        fc = s["col_exp"]
        if isinstance(fc, str):
            flag_name_of[sid] = fc
        else:
            internal = f"__flag_{sid}"
            base = base.withColumn(internal, fc)
            flag_name_of[sid] = internal
            internal_cols.append(internal)
    # ---- group specs by partition key; one shared pipeline per group ----
    groups = {}
    for sid, s, key_tuple in sid_specs:
        groups.setdefault(key_tuple, []).append((sid, s))
    result = base
    helper_cols = []
    for key_tuple, group in groups.items():
        lookup, null_out = _spec_lookups(base, key_tuple, group, flag_name_of)
        result = result.join(lookup, list(key_tuple) + ["__ts"], "left")
        result = result.join(null_out, list(key_tuple), "left")
        for sid, s in group:
            result = result.withColumn(
                s["feature_name"],
                when(col("__ts").isNull(), col(f"__n_{sid}"))
                 .otherwise(col(s["feature_name"])))
            helper_cols.append(f"__n_{sid}")
    return result.drop("__ts", *internal_cols, *helper_cols)
