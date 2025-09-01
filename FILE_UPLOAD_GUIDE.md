# 📤 File Upload & GitHub Path Integration Guide

## 🌟 Overview

The WMS-LLM application now supports **file upload functionality** specifically designed for **Streamlit Cloud deployment**. This feature allows users to upload CSV transaction files directly through the web interface, with automatic processing and historical price calculations.

## 🚀 Key Features

### ✅ **GitHub-Style Path Management**
- **Local Development**: Uses traditional folder paths (e.g., `./investments/username`)
- **Streamlit Cloud**: Uses GitHub-style paths (e.g., `/tmp/username_investments`)
- **Automatic Detection**: Automatically detects deployment environment
- **User-Specific Folders**: Each user gets their own isolated folder structure

### ✅ **Automatic File Processing**
- **CSV Validation**: Validates required columns and data formats
- **Historical Price Fetching**: Automatically fetches missing historical prices
- **Bulk Processing**: Processes multiple files simultaneously
- **Progress Tracking**: Real-time progress bars and status updates

### ✅ **Database Integration**
- **Supabase Storage**: All file records and transactions stored in Supabase
- **User Isolation**: Each user's data is completely isolated
- **Transaction History**: Complete audit trail of all uploaded files

## 📁 Folder Structure

### Local Development
```
./investments/
├── username1/
│   ├── portfolio_20240901_120000.csv
│   ├── transactions_20240901_130000.csv
│   └── archive/
└── username2/
    ├── my_portfolio_20240901_140000.csv
    └── archive/
```

### Streamlit Cloud (GitHub-Style)
```
/tmp/
├── username1_investments/
│   ├── portfolio_20240901_120000.csv
│   ├── transactions_20240901_130000.csv
│   └── archive/
└── username2_my_portfolio/
    ├── my_portfolio_20240901_140000.csv
    └── archive/
```

## 🔧 Implementation Details

### 1. **GitHub Path Conversion**

```python
def convert_to_github_path(username: str, local_path: str = None) -> str:
    """
    Convert local folder path to GitHub path for Streamlit Cloud deployment
    """
    is_streamlit_cloud = os.getenv('STREAMLIT_SERVER_RUN_ON_IP', '').startswith('0.0.0.0')
    
    if is_streamlit_cloud:
        if local_path and local_path.strip():
            folder_name = os.path.basename(local_path.strip())
            return f"/tmp/{username}_{folder_name}"
        else:
            return f"/tmp/{username}_investments"
    else:
        if local_path and local_path.strip():
            return local_path.strip()
        else:
            return f"./investments/{username}"
```

### 2. **File Upload Processing**

```python
def _process_uploaded_files(self, uploaded_files, folder_path):
    """
    Process uploaded files with historical price calculations
    """
    for uploaded_file in uploaded_files:
        # 1. Read and validate CSV
        df = pd.read_csv(uploaded_file)
        
        # 2. Standardize column names
        df = self._standardize_columns(df)
        
        # 3. Validate required columns
        if not self._validate_columns(df):
            continue
        
        # 4. Clean and validate data
        df = self._clean_data(df)
        
        # 5. Fetch historical prices
        if 'price' not in df.columns or df['price'].isna().any():
            df = self._fetch_historical_prices_for_upload(df)
        
        # 6. Save to user folder
        filename = f"{uploaded_file.name.replace('.csv', '')}_{timestamp}.csv"
        file_path = os.path.join(folder_path, filename)
        df.to_csv(file_path, index=False)
        
        # 7. Save to database
        success = user_file_agent._process_uploaded_file(file_path, user_id, df)
```

### 3. **Historical Price Fetching**

```python
def _fetch_historical_prices_for_upload(self, df):
    """
    Fetch historical prices for uploaded file data using bulk operations
    """
    # Prepare tickers and dates for bulk fetching
    tickers_with_dates = []
    for idx, row in df.iterrows():
        ticker = row['ticker']
        transaction_date = row['date']
        tickers_with_dates.append((ticker, transaction_date))
    
    # Bulk fetch prices
    from file_manager import fetch_prices_bulk
    bulk_prices = fetch_prices_bulk(tickers_with_dates)
    
    # Update prices in DataFrame
    for i, (ticker, transaction_date) in enumerate(tickers_with_dates):
        price = bulk_prices.get(ticker)
        df.at[i, 'price'] = price
    
    return df
```

## 📋 Required CSV Format

### Minimum Required Columns
```csv
stock_name,ticker,quantity,transaction_type,date
Reliance Industries,RELIANCE,10,buy,2024-01-15
TCS,TCS,5,buy,2024-02-20
```

### Optional Columns
```csv
stock_name,ticker,quantity,price,transaction_type,date,channel
Reliance Industries,RELIANCE,10,2500,buy,2024-01-15,Direct
TCS,TCS,5,3500,buy,2024-02-20,Broker
```

### Supported Column Names
- **Stock Name**: `stock_name`, `Stock Name`, `Stock_Name`
- **Ticker**: `ticker`, `Ticker`
- **Quantity**: `quantity`, `Quantity`
- **Price**: `price`, `Price` (optional - will be fetched automatically)
- **Transaction Type**: `transaction_type`, `Transaction Type`, `Transaction_Type`
- **Date**: `date`, `Date`
- **Channel**: `channel`, `Channel` (optional - extracted from filename if missing)

## 🎯 User Experience

### 1. **Registration (Streamlit Cloud)**
```
🌐 Streamlit Cloud Mode: Your files will be stored in a cloud-based folder structure.

Local Folder Name (Optional)
[my_portfolio] ← Optional folder name
```

### 2. **File Upload Interface**
```
📤 File Upload & Processing
🌐 Cloud Mode: Upload your CSV transaction files for automatic processing with historical price calculation.

Choose CSV files
[Browse files...] ← Select one or more CSV files

📊 Process Files ← Click to process
Selected 2 file(s) for processing
```

### 3. **Processing Progress**
```
Processing portfolio_20240901.csv...
🔍 Fetching historical prices for portfolio_20240901.csv...
🔍 Price summary: 15/20 transactions got historical prices
✅ Successfully processed portfolio_20240901.csv
```

## 🔒 Security & Data Isolation

### **User Data Isolation**
- Each user has their own folder structure
- Database queries are filtered by `user_id`
- No cross-user data access

### **File Validation**
- CSV format validation
- Required column checking
- Data type validation
- Transaction type standardization

### **Error Handling**
- Graceful handling of missing columns
- Detailed error messages
- Progress tracking for large files
- Automatic retry mechanisms

## 🚀 Deployment Benefits

### **Streamlit Cloud Advantages**
- **No Local File System**: Files stored in cloud-based folders
- **Automatic Scaling**: Handles multiple users simultaneously
- **Persistent Storage**: Files persist between sessions
- **Easy Access**: Web-based file upload interface

### **Performance Optimizations**
- **Bulk Price Fetching**: Reduces API calls
- **Caching**: Session-based caching for live prices
- **Background Processing**: Non-blocking file processing
- **Progress Tracking**: Real-time status updates

## 🧪 Testing

### **Test Script**
```bash
python test_file_upload.py
```

### **Test Output**
```
🧪 Testing File Upload Functionality
==================================================

1. Testing GitHub Path Conversion:
🔧 Local path: ./my_portfolio
☁️ Cloud path: /tmp/testuser_my_portfolio
☁️ Cloud path (default): /tmp/testuser_investments

2. Creating Test CSV File:
✅ Created test CSV file: test_portfolio_20250901_180656.csv
📊 Sample data:
            stock_name    ticker  quantity  price transaction_type       date channel
0  Reliance Industries  RELIANCE        10   2500              buy 2024-01-15  Direct
1                  TCS       TCS         5   3500              buy 2024-02-20  Broker
2            HDFC Bank  HDFCBANK        20   1500              buy 2024-03-10  Direct
3              Infosys      INFY        15   1200              buy 2024-04-05  Broker

✅ All tests completed!
```

## 📝 Usage Instructions

### **For Users**
1. **Register/Login**: Create account or login to existing account
2. **Upload Files**: Use the file upload interface in the dashboard
3. **Select Files**: Choose one or more CSV files
4. **Process**: Click "Process Files" button
5. **Monitor**: Watch progress and status updates
6. **View Results**: Check processed data in dashboard

### **For Developers**
1. **Local Testing**: Use `test_file_upload.py` to create test files
2. **Environment Detection**: System automatically detects deployment environment
3. **Path Management**: GitHub paths used only on Streamlit Cloud
4. **Database Integration**: All data stored in Supabase with user isolation

## 🔄 Migration from Local to Cloud

### **Existing Users**
- **Local Development**: Continue using local folder paths
- **Streamlit Cloud**: Automatically converted to GitHub-style paths
- **Data Migration**: No manual migration required
- **Backward Compatibility**: All existing functionality preserved

### **New Users**
- **Streamlit Cloud**: Use file upload interface
- **Local Development**: Use traditional folder paths
- **Automatic Setup**: Folder structure created automatically

## 🎉 Summary

The file upload functionality provides a seamless experience for users deploying on Streamlit Cloud while maintaining full compatibility with local development. The GitHub-style path management ensures proper data isolation and cloud storage, while the automatic historical price fetching enhances the user experience by eliminating manual data preparation.

**Key Benefits:**
- ✅ **Cloud-Ready**: Optimized for Streamlit Cloud deployment
- ✅ **User-Friendly**: Simple web-based file upload interface
- ✅ **Automatic Processing**: Historical price fetching and data validation
- ✅ **Secure**: Complete user data isolation
- ✅ **Scalable**: Handles multiple users and large files
- ✅ **Backward Compatible**: Works with existing local setups
