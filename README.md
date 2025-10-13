# 📊 WMS-LLM: AI-Powered Wealth Management System

An intelligent portfolio analytics platform with AI chatbot integration for managing stocks, mutual funds, and PMS/AIF investments.

## 🚀 Features

- **Portfolio Analytics Dashboard**: Real-time portfolio tracking with P&L calculations
- **Multi-Asset Support**: Stocks, Mutual Funds (MF), and Portfolio Management Schemes (PMS/AIF)
- **AI Chatbot**: Natural language queries about your portfolio
- **Automatic Price Fetching**: Live prices from multiple sources (yfinance, indstocks, mftool)
- **Historical Data Caching**: Optimized weekly/monthly price caching
- **File Upload**: CSV transaction file processing
- **User Management**: Secure login with role-based access
- **Performance Analytics**: Sector allocation, top performers, and detailed P&L analysis

## 📁 Core Files

### Main Application
- `web_agent.py` - Main Streamlit application (entry point)
- `database_config_supabase.py` - Database operations and queries
- `optimized_data_loader.py` - Fast data loading with JOINs and caching

### Price Fetching
- `unified_price_fetcher.py` - Unified price fetching for all asset types
- `indstocks_api.py` - Indian stock price fetching
- `mf_price_fetcher.py` - Mutual fund NAV fetching
- `pms_aif_fetcher.py` - PMS/AIF data fetching

### Utilities
- `smart_ticker_detector.py` - Intelligent ticker classification
- `ticker_validator.py` - Ticker validation and formatting
- `file_reading_agent.py` - CSV file processing
- `login_system.py` - User authentication

### Database Setup
- `create_tables.py` - Database schema creation
- `setup_database.py` - Initial database setup
- `setup_supabase.py` - Supabase configuration
- `ensure_stock_data_link.py` - FK relationship maintenance

## 🗄️ Database Schema

### Core Tables
- `users` - User accounts
- `user_login` - Login sessions
- `investment_transactions` - User-specific transactions (FK to users)
- `stock_data` - Shared stock metadata (ticker, name, sector, live_price)
- `historical_prices` - Shared historical prices (FK to stock_data)
- `investment_files` - Uploaded file tracking
- `pdf_documents` - PDF documents for chatbot

### Key Relationships
- `investment_transactions.user_id` → `users.id`
- `investment_transactions.ticker` → `stock_data.ticker`
- `historical_prices.ticker` → `stock_data.ticker`

## 🛠️ Installation

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/WMS-LLM.git
cd WMS-LLM
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup Supabase
1. Create a Supabase project at https://supabase.com
2. Create a `.env` file:
```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

### 4. Initialize Database
```bash
python setup_database.py
python create_tables.py
```

### 5. Create Admin User
```bash
python create_admin_user.py
```

## 🚀 Running the Application

### Local Development
```bash
streamlit run web_agent.py
```

### Streamlit Cloud Deployment
1. Push to GitHub
2. Connect to Streamlit Cloud (https://streamlit.io/cloud)
3. Deploy `web_agent.py`
4. Add secrets in Streamlit dashboard:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`

## 📊 Usage

### 1. Login/Register
- Access the application and create an account or login

### 2. Upload Transactions
- Go to "Files" page
- Upload CSV files with transaction data
- Format: `Date, Ticker, Transaction Type, Quantity, Price, Channel`

### 3. View Portfolio
- **Portfolio Overview**: High-level summary and sector allocation
- **Performance**: Overall performance metrics and top gainers/losers
- **Holdings**: Detailed holdings with current prices and P&L
- **Analytics**: Charts and graphs for portfolio analysis

### 4. AI Chatbot
- Ask questions about your portfolio in natural language
- Examples:
  - "What are my top performing stocks?"
  - "Show me my mutual fund holdings"
  - "What's my total P&L for banking sector?"

## 🔧 Configuration

### Price Fetching Strategy
1. Check database cache (historical_prices)
2. Fallback to API (yfinance, indstocks, mftool)
3. Save fetched prices to database
4. Weekly/monthly cache updates

### First-Time Setup
On first login, the system:
1. Processes ALL tickers for historical data (no limit)
2. Builds complete price history
3. Subsequent logins: incremental updates (20 ticker limit)

## 📈 Data Flow

```
User Uploads CSV → file_reading_agent.py
                 ↓
        investment_transactions (user-specific)
                 ↓
        optimized_data_loader.py (JOIN queries)
                 ↓
        stock_data + historical_prices (shared)
                 ↓
        unified_price_fetcher.py (live prices)
                 ↓
        web_agent.py (UI + calculations)
```

## 🔐 Security

- Password hashing for user accounts
- Row Level Security (RLS) in Supabase
- User-specific data isolation
- Shared stock data across users (efficiency)

## 🐛 Troubleshooting

### No P&L showing
- Ensure live prices are being fetched
- Check `stock_data.live_price` is populated
- Verify transactions have valid tickers

### Slow loading
- First login builds complete cache (normal)
- Subsequent logins use incremental updates
- Check database indexes

### Price fetching errors
- Install required packages: `pip install yfinance indstocks mftool`
- Check API rate limits
- Verify ticker format (e.g., "INFY" not "INFY.NS")

## 📚 Documentation

- `OPTIMIZATION_SUMMARY.md` - System architecture and optimizations
- `README_SUPABASE.md` - Supabase setup guide
- Sample files in `kalyan_files/` directory

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📝 License

MIT License - See LICENSE file for details

## 👥 Authors

WMS-LLM Team

## 🙏 Acknowledgments

- Streamlit for the amazing framework
- Supabase for database hosting
- Yahoo Finance, IndStocks, and MFTool for price data APIs
