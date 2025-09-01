# WMS-LLM Deployment Guide

## Streamlit Cloud Deployment

### Prerequisites
- GitHub account
- Supabase account with PostgreSQL database
- Streamlit Cloud account

### Step 1: Prepare Your Repository

1. **Fork this repository** to your GitHub account
2. **Ensure all files are present**:
   - `web_agent.py` (main app)
   - `database_config_supabase.py` (database config)
   - `requirements_supabase.txt` (dependencies)
   - `README.md` (documentation)
   - `.gitignore` (git ignore rules)

### Step 2: Set Up Supabase Database

1. **Create a Supabase project**
2. **Get your connection string** from:
   - Supabase Dashboard → Settings → Database → Connection string
   - Format: `postgresql://postgres:[password]@[host]:5432/postgres`

### Step 3: Deploy to Streamlit Cloud

1. **Go to [share.streamlit.io](https://share.streamlit.io)**
2. **Connect your GitHub account**
3. **Select your forked repository**
4. **Set the main file path**: `web_agent.py`
5. **Add secrets**:
   ```
   SUPABASE_URL = https://rolcoegikoeblxzqgkix.supabase.co
   SUPABASE_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvbGNvZWdpa29lYmx4enFna2l4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY1NDM2MjUsImV4cCI6MjA3MjExOTYyNX0.Vwg2hgdKNQGizJiulgTlxXkTLfy-J3vFNkX8gA_6ul4
   DATABASE_URL = postgresql://postgres:your_password@your_host:5432/postgres
   ```

### Step 4: Configure Database Tables

Run these SQL commands in your Supabase SQL editor:

```sql
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    role VARCHAR(20) DEFAULT 'user',
    folder_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    login_attempts INTEGER DEFAULT 0,
    is_locked BOOLEAN DEFAULT FALSE
);

-- Investment transactions table
CREATE TABLE IF NOT EXISTS investment_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    stock_name VARCHAR(100) NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    transaction_type VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    channel VARCHAR(50),
    sector VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Investment files table
CREATE TABLE IF NOT EXISTS investment_files (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    customer_name VARCHAR(100),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'processed'
);

-- Stock data table
CREATE TABLE IF NOT EXISTS stock_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) UNIQUE NOT NULL,
    stock_name VARCHAR(100),
    sector VARCHAR(50),
    current_price DECIMAL(10,2),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Step 5: Test Your Deployment

1. **Visit your Streamlit app URL**
2. **Register a new user**
3. **Test file upload and processing**
4. **Verify portfolio analytics work**

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Check your `DATABASE_URL` secret in Streamlit Cloud
   - Ensure Supabase database is running
   - Verify connection string format

2. **Module Import Errors**
   - Check `requirements_supabase.txt` has all dependencies
   - Ensure all Python files are in the repository

3. **File Processing Issues**
   - Verify CSV file format matches requirements
   - Check file permissions and paths

### Connection Methods

The app uses multiple fallback methods for database connection:

1. **DNS Resolution** (may fail on Streamlit Cloud)
2. **Supabase Connection Pooler** (port 6543) - **Most reliable**
3. **Hardcoded IPv4 addresses**
4. **Connection string with timeouts**
5. **Basic fallback**

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SUPABASE_URL` | Your Supabase project URL | `https://rolcoegikoeblxzqgkix.supabase.co` |
| `SUPABASE_KEY` | Your Supabase anon/public key | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `DATABASE_URL` | Supabase PostgreSQL connection string (fallback) | `postgresql://postgres:password@host:5432/postgres` |

## File Structure

```
WMS-LLM/
├── web_agent.py                 # Main Streamlit application
├── stock_data_agent.py          # Stock data management
├── user_file_reading_agent.py   # File processing agent
├── file_manager.py              # File utilities and price fetching
├── mf_price_fetcher.py          # Mutual fund price fetching
├── indstocks_api.py             # Indian stocks API integration
├── login_system.py              # User authentication
├── database_config_supabase.py  # Database configuration
├── requirements_supabase.txt    # Python dependencies
├── .gitignore                   # Git ignore rules
├── README.md                    # Project documentation
├── DEPLOYMENT.md                # This file
└── investments/                 # Sample investment files
```

## Support

If you encounter issues:
1. Check the Streamlit Cloud logs
2. Verify database connection
3. Review error messages in the app
4. Check file permissions and formats
