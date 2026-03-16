import pandas as pd 


# Reads the uploaded file into a Pandas DataFrame.
# Supports: CSV, Excel (.xlsx/.xls), JSON, XML, HTML

# Allowed file extensions
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls', 'json', 'xml', 'html', 'htm'}

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_dataframe(filepath: str) -> pd.DataFrame:
    ext = filepath.rsplit('.', 1)[1].lower()
    if ext == 'csv':
        df = pd.read_csv(filepath)
    elif ext in ('xlsx', 'xls'):
        df = pd.read_excel(filepath)
    elif ext == 'json':
        df = pd.read_json(filepath)
    elif ext == 'xml':
        df = pd.read_xml(filepath)
    elif ext in ('html', 'htm'):
# read_html returns a list of tables; use the first one
        tables = pd.read_html(filepath)
        if not tables:
            raise ValueError("No HTML table found in the uploaded file.")
        df = tables[0]
    else:
        raise ValueError(f"Unsupported file format: .{ext}")
    return df

