<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/how-to-prove-a-spark-rule/).
<!-- /github-only -->

# How to prove a Spark rule

<!-- shop: procurement -->

A rule written as a `when` chain over a DataFrame (bands, flags,
categories) is a function of each row's columns, and Spark applies it
to every row the same way. `mathema_language.spark.rule` reads that
function out of the Spark code and gives it back as plain Python, one
parameter per column it reads, so a claim about the rule is a claim
about a function of a few numbers or strings, which mathema can prove.
It reads the source and never imports it, so neither pyspark nor a
Spark session is needed.

## The rule

The procurement pipeline bands each purchase order by its value:

```python title="examples/shop/spend.py"
def classify_po_category(df: DataFrame, value_col: str = "po_value") -> DataFrame:
    """Each purchase order's spend band: Invalid for no value or a
    negative one, then Micro, Standard, Strategic and Major."""
    return df.withColumn(
        "po_category",
        when(col(value_col).isNull() | (col(value_col) < 0), lit("Invalid"))
        .when(col(value_col) < 1000, lit("Micro"))
        .when(col(value_col) < STRATEGIC_FROM, lit("Standard"))
        .when(col(value_col) < 50000, lit("Strategic"))
        .otherwise(lit("Major")),
    )
```

`rule` takes the function, or its dotted path, and the column it sets:

```python
from mathema_language.spark import rule

band = rule("shop.spend.classify_po_category", "po_category", float_columns=set())
print(band.source)
```

<!-- output -->
```text
def classify_po_category__po_category(po_value: Optional[float]):
    """The 'po_category' column shop.spend.classify_po_category computes, from the columns it reads."""
    if ((po_value is None) or (po_value is not None and (po_value) < (0))):
        return 'Invalid'
    if (po_value is not None and (po_value) < (1000)):
        return 'Micro'
    if (po_value is not None and (po_value) < (10000)):
        return 'Standard'
    if (po_value is not None and (po_value) < (50000)):
        return 'Strategic'
    return 'Major'

```

The parameter default `value_col="po_value"` and the module constant
`STRATEGIC_FROM` are read as Spark would read them. Null is written in:
a comparison with a null value is null, so its branch is skipped.
`float_columns=set()` says no column read here can hold NaN, which is
true of the pipeline's `decimal(18, 2)` value; without it, every column
is read as one that may, and NaN is greater than every number, as it is
in Spark.

## The claims

Each band is a claim over an interval of values:

```text
f = band
for po_value in [10000, 49999.99], f(po_value) == "Strategic"
    proven

for po_value in [0, 999.99], f(po_value) == "Micro"
    proven

for po_value in [-1e12, -0.01], f(po_value) == "Invalid"
    proven

f(None) == "Invalid"
    proven
```

They are proven, for every value in the interval, not a sample of them.
The same claims over a version of the rule whose Standard band was
written `<=` instead of `<` find the edge:

```python
band_edited = rule("shop.spend.classify_po_category_bug", "po_category", float_columns=set())
```

```text
f = band_edited
for po_value in [10000, 49999.99], f(po_value) == "Strategic"
    falsified   po_value = 10000
```

An order of exactly 10,000 is banded Standard. The witness comes from
running the lowered function, so it is mathema's reading of the Spark
code; running the real function on a one-row DataFrame with that value
confirms it, and the package's own tests run every construct `rule`
reads against Spark to keep the two the same.

## What the rule does with a missing value

A null in a column is a hole, and Spark decides what a rule does with
one even when the code never says. `holes` reports, for each column the
rule reads and each hole it admits, what the rule writes and how it got
there:

```python
from mathema_language.spark import holes

for outcome in holes("shop.spend.classify_po_category", "po_category", float_columns=set()):
    print(outcome.sentence())
```

<!-- output -->
```text
at po_value = null f gave 'Invalid' (handled in the code: isNull)
```

The rule tests for the null, so the outcome is the code's. A version
without that test bands a missing value too, but not by anyone's
decision:

```python
for outcome in holes("shop.spend.classify_po_category_unguarded", "po_category", float_columns=set()):
    print(outcome.sentence())
```

<!-- output -->
```text
at po_value = null f gave 'Major' (not handled: every condition is null or false there (a comparison with null is null), so otherwise)
```

A comparison with null is null, so every `when` is skipped and the
order falls through to `otherwise`: a purchase order with no value is
reported as Major spend. The same happens with `!=` (a null country is
not "not UK"), with `~` (a null status is not "not closed") and with
arithmetic (a null quantity makes the total null, and every comparison
on it null). For a floating-point column, NaN is a second hole, and
Spark compares it as above every number.

An outcome the code did not decide is settled one of four ways: test for
the hole in the code if the outcome is wrong; mark the column
`nullable=False` in the schema if a null cannot arrive; state it as a
claim if it is intended; or accept it as a risk until one of those is
done. As a claim on the rule:

```python
unguarded = rule("shop.spend.classify_po_category_unguarded", "po_category", float_columns=set())
```

```text
f = unguarded
f(None) == "Major"
    proven
```

## What it reads

`rule` reads a `withColumn` chain, in one expression or one statement
after another, and in the column's expression:

| Spark | Read as |
|---|---|
| `when(...).when(...).otherwise(...)` | the branches in order; no `otherwise` gives `None` |
| `col("x")`, `F.col("x")`, `df.x`, `df["x"]` | the column `x`, a parameter of the result |
| `lit(v)`, a literal, a parameter default, a module constant | its value |
| `<`, `<=`, `>`, `>=`, `==`, `!=` | with null giving null and NaN above every number |
| `&`, `\|`, `~` | Spark's three-valued `and`, `or`, `not` |
| `isNull()`, `isNotNull()`, `isin(...)`, `between(a, b)` | as Spark defines them |
| `+`, `-`, `*`, `/` | with null giving null |
| `coalesce(...)` | the first value that is not null |

Anything else (a cast, a UDF, a window, a column the same function
computes earlier) is refused with `NotRead`, naming the construct, so a
rule is never proven from a reading that guessed.
