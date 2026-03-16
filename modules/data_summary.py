import pandas as pd

# Generates a clean summary of the DataFrame:
# Shape (rows × columns)
# Column names + data types
# Missing value counts
# Basic descriptive statistics (describe())

def get_summary(df: pd.DataFrame) -> dict:
    rows, cols = df.shape
    columns_info = []
    for col in df.columns:
        missing_count = int(df[col].isna().sum())
        missing_pct = round((missing_count / rows) * 100, 1) if rows > 0 else 0.0
        columns_info.append({
            'name': col,
            'dtype': str(df[col].dtype),
            'missing': missing_count,
            'missing_pct': missing_pct
        })
    desc = df.describe(include='number') 
    stats_dict = desc.round(3).to_dict()
    preview_df = df.head(5)
    preview_cols = list(preview_df.columns)
    # Convert each row to a plain list so Jinja can iterate
    preview_rows = [list(row) for row in preview_df.values]
    return {
        'rows': rows,
        'cols': cols,
        'columns_info': columns_info,
        'stats': stats_dict,
        'preview_cols': preview_cols,
        'preview_rows': preview_rows,
    }