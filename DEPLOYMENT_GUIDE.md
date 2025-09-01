# 🤖 Investment Portfolio Agent - Deployment Guide

## Overview

This system consists of three intelligent agents that work together to provide a comprehensive investment portfolio management solution:

1. **📈 Stock Data Agent** (`stock_data_agent.py`) - Manages live stock prices and sector data
2. **📁 File Reading Agent** (`file_reading_agent.py`) - Monitors and processes investment CSV files
3. **🌐 Web Agent** (`web_agent.py`) - Provides the Streamlit web interface and coordinates other agents

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up Environment Variables
Create a `.env` file with your database credentials:
```env
DATABASE_URL=postgresql://username:password@host:port/database
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

### 3. Run the System
```bash
# Option 1: Use the new web agent (recommended)
streamlit run web_agent.py

# Option 2: Use the original app
streamlit run simple_app_supabase.py
```

## 🤖 Agent Architecture

### Stock Data Agent (`stock_data_agent.py`)
- **Purpose**: Manages live stock prices and sector information
- **Key Features**:
  - Updates live prices (overwrites, doesn't append daily data)
  - Caches data to avoid repeated API calls
  - Background updates every 1 hour
  - Multiple data sources (INDstocks, YFinance)
  - Error handling and retry logic

**Key Functions**:
```python
from stock_data_agent import get_live_price, get_sector, get_all_live_prices
live_price = get_live_price("RELIANCE")
sector = get_sector("RELIANCE")
all_prices = get_all_live_prices()
```

### File Reading Agent (`file_reading_agent.py`)
- **Purpose**: Monitors investment folder and processes CSV files
- **Key Features**:
  - Automatic file monitoring (every 30 seconds)
  - CSV parsing with multiple format support
  - Database storage with transaction tracking
  - Triggers stock data updates for new tickers
  - File change detection and reprocessing

**Key Functions**:
```python
from file_reading_agent import process_all_investment_files, get_file_processing_status
result = process_all_investment_files()
status = get_file_processing_status()
```

### Web Agent (`web_agent.py`)
- **Purpose**: Streamlit web interface that coordinates all agents
- **Key Features**:
  - Modern dashboard with real-time data
  - Agent status monitoring
  - Interactive filters (channel, sector, stock)
  - Portfolio analytics and charts
  - Agent control buttons

## 📊 Database Schema

### Stock Data Table (`stock_data`)
```sql
CREATE TABLE stock_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR UNIQUE NOT NULL,
    stock_name VARCHAR,
    sector VARCHAR,
    live_price FLOAT,
    last_updated TIMESTAMP,
    price_source VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    data_hash VARCHAR
);
```

### Investment Transactions Table (`investment_transactions`)
```sql
CREATE TABLE investment_transactions (
    id SERIAL PRIMARY KEY,
    file_id INTEGER,
    user_id INTEGER,
    channel VARCHAR,
    stock_name VARCHAR,
    ticker VARCHAR,
    sector VARCHAR,
    quantity FLOAT,
    price FLOAT,
    transaction_type VARCHAR,
    date TIMESTAMP
);
```

## 🔧 Configuration

### Stock Data Agent Configuration
```python
# In stock_data_agent.py
update_interval = 3600  # 1 hour (3600 seconds)
max_retries = 3
batch_size = 25
```

### File Reading Agent Configuration
```python
# In file_reading_agent.py
check_interval = 30  # 30 seconds
max_retries = 3
```

## 🧪 Testing

Run the test script to verify all agents work together:
```bash
python test_agents.py
```

This will test:
- Database connectivity
- Stock data agent functionality
- File reading agent functionality
- Web agent creation
- Agent integration
- Streamlit compatibility

## 📈 Performance Optimizations

### Caching Strategy
- **Stock Data**: 1-minute cache for live prices
- **Sector Data**: 1-hour cache for sector information
- **File Processing**: Hash-based change detection

### Background Processing
- Stock data updates run in background thread
- File monitoring runs in background thread
- Database operations are optimized with connection pooling

### Batch Processing
- Stock data updates: 25 stocks per batch
- File processing: Individual files with error handling
- Database operations: Batch inserts for transactions

## 🚨 Error Handling

### Stock Data Agent
- Retry logic for failed API calls
- Fallback data sources (INDstocks → YFinance)
- Error tracking and deactivation of problematic stocks

### File Reading Agent
- File validation and error reporting
- Transaction rollback on errors
- Detailed error logging

### Web Agent
- Graceful error handling in UI
- Fallback data loading
- User-friendly error messages

## 🔄 Data Flow

1. **File Upload**: User places CSV files in `investments/` folder
2. **File Processing**: File Reading Agent detects and processes files
3. **Database Storage**: Transactions stored in database
4. **Stock Data Update**: Stock Data Agent fetches live prices for new tickers
5. **Web Display**: Web Agent loads data and displays in Streamlit interface

## 📱 Streamlit Features

### Dashboard Components
- Portfolio overview with key metrics
- Interactive charts (performance, sector allocation)
- Detailed transaction table
- Real-time agent status

### Controls
- Stock data update button
- File processing button
- Filter controls (channel, sector, stock)
- Clear filters button

### Responsive Design
- Wide layout for better data visualization
- Sidebar for filters and controls
- Mobile-friendly interface

## 🛠️ Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Check `.env` file configuration
   - Verify database credentials
   - Ensure database is running

2. **Stock Data Not Updating**
   - Check internet connection
   - Verify API keys (if using paid services)
   - Check error logs in console

3. **Files Not Processing**
   - Verify CSV format
   - Check file permissions
   - Ensure required columns are present

4. **Streamlit Not Loading**
   - Check port availability
   - Verify all dependencies installed
   - Check for import errors

### Debug Mode
Enable debug logging by setting environment variable:
```bash
export DEBUG=1
```

## 🔒 Security Considerations

- Database credentials stored in environment variables
- User authentication system (optional)
- Input validation for file uploads
- SQL injection protection via SQLAlchemy ORM

## 📈 Monitoring

### Agent Status
- Real-time status in Streamlit sidebar
- Database statistics
- Cache hit rates
- Error counts

### Performance Metrics
- Data processing times
- API response times
- Database query performance
- Memory usage

## 🚀 Deployment Options

### Local Development
```bash
streamlit run web_agent.py
```

### Streamlit Cloud
1. Push code to GitHub
2. Connect repository to Streamlit Cloud
3. Set environment variables
4. Deploy

### Docker Deployment
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "web_agent.py"]
```

## 📚 API Reference

### Stock Data Agent Functions
- `get_live_price(ticker)` - Get current price for a stock
- `get_sector(ticker)` - Get sector for a stock
- `get_all_live_prices()` - Get all cached live prices
- `force_update_stock(ticker)` - Force update for a specific stock

### File Reading Agent Functions
- `process_all_investment_files()` - Process all CSV files
- `get_file_processing_status()` - Get processing status
- `reprocess_investment_file(filename)` - Reprocess specific file

### Web Agent Functions
- `WebAgent.run()` - Start the web interface
- `WebAgent.load_data_from_agents()` - Load data from all agents
- `WebAgent.render_dashboard()` - Render the main dashboard

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
